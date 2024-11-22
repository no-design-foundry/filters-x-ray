from fontTools.pens.basePen import AbstractPen
from math import atan2, cos, sin, pi, sqrt
from fontTools.pens.reverseContourPen import ReverseContourPen
from ufoLib2.objects.font import Font
from ufoLib2.objects.point import Point
from ufoLib2.objects.contour import Contour
from ufoLib2.objects.glyph import Glyph
from ufoLib2.objects.component import Component
import numpy as np
from fontTools.designspaceLib import (
	DesignSpaceDocument,
	SourceDescriptor,
	AxisDescriptor,
)
from ufo2ft import compileVariableTTF

try:
	from .outline_glyph import outline_glyph
	from .normalizing_pen import NormalizingPen
	from .colorize import colorize
except ModuleNotFoundError:
	from outline_glyph import outline_glyph
	from normalizing_pen import NormalizingPen
	from colorize import colorize

def circle(layer, center, diameter, tension=1):
	x, y = center
	radius = diameter / 2
	contour = Contour()
	contour.points = [
		Point(x - radius * tension, y + radius),
		Point(x - radius, y + radius * tension),
		Point(x - radius, y, "curve"),
		Point(x - radius, y - radius * tension),
		Point(x - radius * tension, y - radius),
		Point(x, y - radius, "curve"),
		Point(x + radius * tension, y - radius),
		Point(x + radius, y - radius * tension),
		Point(x + radius, y, "curve"),
		Point(x + radius, y + radius * tension),
		Point(x + radius * tension, y + radius),
		Point(x, y + radius, "curve"),
	]
	layer.contours.append(contour)


def square(layer, center, size):
	x, y = center
	contour = Contour()
	contour.points = [
		Point(x - size / 2, y - size / 2, "line"),
		Point(x + size / 2, y - size / 2, "line"),
		Point(x + size / 2, y + size / 2, "line"),
		Point(x - size / 2, y + size / 2, "line"),
	]
	layer.contours.append(contour)

def scale_glyph(glyph, scale_factor):
	for contour in glyph:
		for point in contour:
			x, y = np.round(np.array((point.x, point.y)) * scale_factor).astype(np.int32)
			point.x = int(x)
			point.y = int(y)
	for component in glyph.components:
		*scales, x, y = component.transformation
		component.transformation = tuple(scales + [round(x * scale_factor), round(y * scale_factor)])
	glyph.width = round(glyph.width * scale_factor) 
	return glyph

def line_shape(output_glyph, point_a, point_b, thickness):
	(x_a, y_a), (x_b, y_b) = point_a, point_b
	angle = atan2(y_b - y_a, x_b - x_a) + pi / 2
	x_offset = cos(angle) * thickness / 2
	y_offset = sin(angle) * thickness / 2

	point_objects = [
		Point(x_a - x_offset, y_a - y_offset, "line"),
		Point(x_b - x_offset, y_b - y_offset, "line"),
		Point(x_b + x_offset, y_b + y_offset, "line"),
		Point(x_a + x_offset, y_a + y_offset, "line"),
	]

	contour = Contour()
	contour.points = point_objects
	output_glyph.contours.append(contour)


def normalize_angle(angle):
	"""Normalize angle to be within the range [-pi, pi)."""
	while angle < -pi:
		angle += 2 * pi
	while angle >= pi:
		angle -= 2 * pi
	return angle


def calculate_offset(p0, p1, p2, offset):

	# Calculate vectors
	v1 = (p0[0] - p1[0], p0[1] - p1[1])
	v2 = (p2[0] - p1[0], p2[1] - p1[1])

	# Normalize vectors
	v1_length = sqrt(v1[0] ** 2 + v1[1] ** 2)
	v2_length = sqrt(v2[0] ** 2 + v2[1] ** 2)

	v1_normalized = (v1[0] / v1_length, v1[1] / v1_length)
	v2_normalized = (v2[0] / v2_length, v2[1] / v2_length)

	# Check for collinearity (cross product close to zero)
	cross_product = (
		v1_normalized[0] * v2_normalized[1] - v1_normalized[1] * v2_normalized[0]
	)

	if abs(cross_product) < 1e-10:
		# Handle collinear case
		offset_x = offset * v1_normalized[1]  # Perpendicular offset direction
		offset_y = offset * v1_normalized[0]  # Perpendicular offset direction
		return (offset_x, offset_y)

	bisector = (
		v1_normalized[0] + v2_normalized[0],
		v1_normalized[1] + v2_normalized[1],
	)
	bisector_length = sqrt(bisector[0] ** 2 + bisector[1] ** 2)
	bisector_normalized = (bisector[0] / bisector_length, bisector[1] / bisector_length)

	# Calculate the angle between v1 and v2
	dot_product = (
		v1_normalized[0] * v2_normalized[0] + v1_normalized[1] * v2_normalized[1]
	)
	angle = atan2(cross_product, dot_product)
	factor = offset / sin(angle / 2)

	# Calculate offset point
	offset_x = bisector_normalized[0] * factor
	offset_y = bisector_normalized[1] * factor
	return (offset_x, offset_y)

def calculate_end_offset(p0, p1, offset):
	"""Calculate the offset point for the end of a contour."""
	v = (p1[0] - p0[0], p1[1] - p0[1])
	v_length = sqrt(v[0] ** 2 + v[1] ** 2)
	v_normalized = (v[0] / v_length, v[1] / v_length)
	offset_x = p1[0] + v_normalized[0] * offset
	offset_y = p1[1] + v_normalized[1] * offset
	return (offset_x, offset_y)


def add_offset(point, offset):
	return (point[0] + offset[0], point[1] + offset[1])


class XRayPen(AbstractPen):
	def __init__(
		self,
		layer,
		size,
		process,
		use_components=True,
	):
		self.layer = layer
		self.size = size
		self.process = process
		self.use_components = use_components
		self.handle_component_name = "handle"
		self.point_component_name = "point"
		self.last_point = None

	def handle(self, point):
		if self.process == "handles":
			if self.use_components:
				self.layer.components.append(
					Component(self.handle_component_name, (1, 0, 0, 1, point[0], point[1]))
				)
			else:
				circle(self.layer, point, self.size, tension=0.66)

	def handle_line(self, point_a, point_b):
		if self.process == "handle_lines":
			line_shape(self.layer, point_a, point_b, self.size)

	def point(self, point):
		if self.process == "points":
			if self.use_components:
				self.layer.components.append(
					Component(self.point_component_name, (1, 0, 0, 1, point[0], point[1]))
				)
			else:
				square(self.layer, point, self.size)

	def moveTo(self, point):
		self.point(point)
		self.last_point = point

	def lineTo(self, point):
		self.point(point)
		self.last_point = point

	def curveTo(self, point_1, point_2, point_3):
		self.handle_line(self.last_point, point_1)
		self.handle_line(point_2, point_3)
		self.handle(point_1)
		self.handle(point_2)
		self.point(point_3)

		self.last_point = point_3

	def qCurveTo(self, *points):
		last_point = points[-1]

		for point in points[:-1]:
			self.handle(point)
		
		if self.process == "handle_lines":
			line_width = self.size / 2

			points = [self.last_point] + list(points)
			outer_points = []
			inner_points = []
			points_len = len((points))
			for p in range(1, points_len - 1):
				prev_point = points[p - 1]
				point = points[p]
				next_point = points[p + 1]
				
				if p == 1:
					angle = atan2(prev_point[1] - point[1], prev_point[0] - point[0]) + pi / 2
					offset_inner = cos(angle) * line_width, sin(angle) * line_width
					offset_outer = cos(angle) * -line_width, sin(angle) * -line_width
					inner_points.append(add_offset(prev_point, offset_inner))
					outer_points.append(add_offset(prev_point, offset_outer))

				offset_inner = calculate_offset(prev_point, point, next_point, line_width)
				offset_outer = calculate_offset(prev_point, point, next_point, -line_width)
				outer_points.append(add_offset(point, offset_outer))
				inner_points.append(add_offset(point, offset_inner))
				
				if p == (points_len - 2):
					angle = atan2(point[1] - next_point[1], point[0] - next_point[0]) + pi / 2
					offset_inner = cos(angle) * line_width, sin(angle) * line_width
					offset_outer = cos(angle) * -line_width, sin(angle) * -line_width
					inner_points.append(add_offset(next_point, offset_inner))
					outer_points.append(add_offset(next_point, offset_outer))
			
			points = inner_points + outer_points[::-1]
			contour = Contour()
			for x, y in points:
				contour.points.append(Point(x, y, "line"))
			# print(contour)
			self.layer.contours.append(contour)
		self.last_point = last_point
		self.point(last_point)

	def addComponent(self, glyph_name, *args, **kwargs) -> None:
		self.layer.components.append(Component(glyph_name, *args, **kwargs))

def duplicate_components(glyph_destination, suffix):
	for component in glyph_destination.components:
		if component.baseGlyph not in ["handle", "point"]:
			component.baseGlyph += suffix


def add_features(font, output_font):
	glyph_names = list(font.keys())
	for pair in font.kerning:
		output_font.kerning[pair] = font.kerning[pair]
		for gn_index, glyph_name in enumerate(pair):
			if glyph_name in glyph_names:
				for suffix in [".bounds", ".filled", ".bounds.filled"]:
					new_pair = list(pair)
					new_pair[gn_index] = glyph_name + suffix
					output_font.kerning[tuple(new_pair)] = font.kerning[pair]
		if pair[0] in glyph_names and pair[1] in glyph_names:
			for suffix in [".bounds", ".filled", ".bounds.filled"]:
				new_pair = [pair[0] + suffix, pair[1] + suffix]
				output_font.kerning[tuple(new_pair)] = font.kerning[pair]

	output_font.features.text = f"""
	feature ss01 {{
		featureNames {{
			name "Glyph's Bounding Box";
		}};
		{" ".join([f"sub {glyph_name} by {glyph_name}.bounds;" for glyph_name in glyph_names])}
	}} ss01;

	feature ss02 {{
		featureNames {{
			name "Filled Glyph";
		}};
		{" ".join([f"sub {glyph_name} by {glyph_name}.filled;" for glyph_name in glyph_names])}
		{" ".join([f"sub {glyph_name}.bounds by {glyph_name}.bounds.filled;" for glyph_name in glyph_names])}
	}} ss02;
	"""

def copy_data_from_glyph(source, destination, exclude=[]):
	destination.copyDataFromGlyph(source)
	if "unicodes" in exclude:
		destination.unicodes = []
	if "contours" not in exclude:
		destination.contours = []
		destination.contours = source.contours
	return destination


def process_outline(glyph, outline_width):
	outlined_glyph_inner = copy_data_from_glyph(glyph.copy(), Glyph())
	outlined_glyph_outer = copy_data_from_glyph(glyph.copy(), Glyph())
	outline_glyph(outlined_glyph_inner, -outline_width/2)
	outline_glyph(outlined_glyph_outer, outline_width/2)
	output_glyph = Glyph()
	reverse_contour_pen = ReverseContourPen(output_glyph.getPen())
	outlined_glyph_inner.draw(reverse_contour_pen)
	outlined_glyph_outer.draw(output_glyph.getPen())
	return output_glyph

def process_point(glyph, point_size):
	point_layer = Glyph()
	x_ray_pen = XRayPen(
		point_layer,
		size=point_size,
		process="points",
		use_components=True
	)
	glyph.draw(x_ray_pen)
	return point_layer


def process_handle(glyph, handle_size):
	handle_layer = Glyph()
	x_ray_pen = XRayPen(
		handle_layer,
		size=handle_size,
		process="handles",
		use_components=True
	)
	glyph.draw(x_ray_pen)
	return handle_layer

def process_line(glyph, line_width):
	handle_line_layer = Glyph()
	x_ray_pen = XRayPen(
		handle_line_layer,
		size=line_width,
		process="handle_lines",
		use_components=True
	)
	glyph.draw(x_ray_pen)
	return handle_line_layer

def x_ray(font, outline_color="#0000FF", line_color="#00FF00", point_color="#FF0000"):
	y_min = font.info.descender
	y_max = font.info.ascender 
	for glyph in font:
		try:
			bounds = glyph.getBounds()
			if bounds:
				y_min = min(y_min, bounds[1])
				y_max = max(y_max, bounds[3])
		except TypeError:
			pass
	
	new_upm = 16_384/2 # for extremely wide fonts like Zapfino must be smaller 16384
	scale_factor = new_upm / font.info.unitsPerEm

	drawing_scale_factor = scale_factor * (font.info.unitsPerEm / 1000)
	for glyph in font:
		scale_glyph(glyph, scale_factor)
	font.info.unitsPerEm = new_upm
	font.info.ascender *= scale_factor
	font.info.descender *= scale_factor
	font.info.xHeight *= scale_factor
	for key in font.kerning.keys():
		font.kerning[key] *= scale_factor

	doc = DesignSpaceDocument()

	axis_outline = AxisDescriptor()
	axis_outline.minimum = 1
	axis_outline.maximum = 20
	axis_outline.default = axis_outline.minimum
	axis_outline.name = "outline_width"
	axis_outline.tag = "OTLN"
	axis_outline.labelNames = dict(en="Outline width")
	doc.addAxis(axis_outline)

	axis_line = AxisDescriptor()
	axis_line.minimum = 1
	axis_line.maximum = 20
	axis_line.default = axis_line.minimum
	axis_line.name = "line_width"
	axis_line.tag = "LINE"
	axis_line.labelNames = dict(en="Line width")
	doc.addAxis(axis_line)

	axis_point = AxisDescriptor()
	axis_point.minimum = 10
	axis_point.maximum = 40
	axis_point.default = axis_point.minimum
	axis_point.name = "point_size"
	axis_point.tag = "POIN"
	axis_point.labelNames = dict(en="Point size")
	doc.addAxis(axis_point)

	axis_handle = AxisDescriptor()
	axis_handle.minimum = 10
	axis_handle.maximum = 40
	axis_handle.default = axis_handle.minimum
	axis_handle.name = "handle_size"
	axis_handle.tag = "HAND"
	axis_handle.labelNames = dict(en="Handle size")
	doc.addAxis(axis_handle)


	normalized_glyphs = {}
	outlined_glyphs = {}
	point_glyphs = {}
	handle_glyphs = {}
	handle_line_glyphs = {}


	for glyph in font:
		normalized_glyph = Glyph()
		normalizing_pen = NormalizingPen(normalized_glyph.getPen(), zero_handles_distance_fix=10*drawing_scale_factor)
		glyph.draw(normalizing_pen)
		normalized_glyphs[glyph.name] = normalized_glyph

	for glyph_name in font.keys():
		glyph = font[glyph_name]
		normalized_glyph = normalized_glyphs[glyph_name]
		for outline_width in [axis_outline.minimum, axis_outline.maximum]:
			output_glyph = process_outline(normalized_glyph, outline_width * drawing_scale_factor)
			outlined_glyphs.setdefault(outline_width, {})[glyph_name] = output_glyph

		for point_size in [axis_point.minimum, axis_point.maximum]:
			output_glyph = process_point(glyph, point_size * drawing_scale_factor)
			point_glyphs.setdefault(point_size, {})[glyph_name] = output_glyph

		for handle_size in [axis_handle.minimum, axis_handle.maximum]:
			output_glyph = process_handle(glyph, handle_size * drawing_scale_factor)
			handle_glyphs.setdefault(handle_size, {})[glyph_name] = output_glyph

		for line_width in [axis_line.minimum, axis_line.maximum]:
			output_glyph = process_line(glyph, line_width * drawing_scale_factor)
			handle_line_glyphs.setdefault(line_width, {})[glyph_name] = output_glyph

	for point_size in [axis_point.minimum, axis_point.maximum]:
		for handle_size in [axis_handle.minimum, axis_handle.maximum]:
			for outline_width in [axis_outline.minimum, axis_outline.maximum]:
				for line_width in [axis_line.minimum, axis_line.maximum]:
					master = Font()
					master.info.unitsPerEm = new_upm
					master.info.ascender = font.info.ascender
					master.info.descender = font.info.descender
					master.info.capHeight = font.info.capHeight
					master.info.xHeight = font.info.xHeight

					add_features(font, master)

					for glyph_name in font.keys():
						copy_data_from_glyph(outlined_glyphs[outline_width][glyph_name], master.newGlyph(glyph_name + "_outlined"), exclude=["unicodes"])
						copy_data_from_glyph(point_glyphs[point_size][glyph_name], master.newGlyph(glyph_name + "_points"), exclude=["unicodes"])
						copy_data_from_glyph(handle_glyphs[handle_size][glyph_name], master.newGlyph(glyph_name + "_handles"), exclude=["unicodes"])
						copy_data_from_glyph(handle_line_glyphs[line_width][glyph_name], master.newGlyph(glyph_name + "_lines"), exclude=["unicodes"])
						copy_data_from_glyph(font[glyph_name], master.newGlyph(glyph_name), exclude=["contours"])
						copy_data_from_glyph(font[glyph_name], master.newGlyph(glyph_name + "_filled"), exclude=["unicodes"])
						
						filled = master.newGlyph(glyph_name + ".filled")
						filled.width = font[glyph_name].width
						for suffix in ["_filled", "_lines", "_points", "_handles"]:
							filled.components.append(Component(glyph_name + suffix, (1, 0, 0, 1, 0, 0)))

						for suffix in ["_lines", "_outlined", "_points", "_handles"]:
							duplicate_components(master[glyph_name + suffix], suffix)

						master.newGlyph(glyph_name + ".bounds").width = font[glyph_name].width
						bounds_pen = master.newGlyph(glyph_name + "_bounds").getPen()
						bounds_pen.moveTo((0, font.info.descender))
						bounds_pen.lineTo((0, font.info.ascender))
						bounds_pen.lineTo((font[glyph_name].width, font.info.ascender))
						bounds_pen.lineTo((font[glyph_name].width, font.info.descender))
						bounds_pen.closePath()
						master.newGlyph(glyph_name + ".bounds.filled").width = font[glyph_name].width

						default_glyph = master[glyph_name]
						default_glyph.contours = []
						default_glyph.components = []
						for suffix in ["_lines", "_outlined"]:
							default_glyph.contours += master[glyph_name + suffix].contours[::1]
						for suffix in ["_handles", "_points"]:
							master[glyph_name].components += master[glyph_name + suffix].components[::1]

					square(master.newGlyph("point"), (0, 0), point_size * drawing_scale_factor)
					circle(master.newGlyph("handle"), (0, 0), handle_size * drawing_scale_factor, tension=0.66)

					source = SourceDescriptor()
					source.font = master
					source.location = dict(
						outline_width=outline_width,
						line_width=line_width,
						point_size=point_size,
						handle_size=handle_size,
					)
					doc.addSource(source)

	compiled = compileVariableTTF(doc, optimizeGvar=False)
	colorize(compiled, font.keys(), outline_color=outline_color, line_color=line_color, point_color=point_color)
	return compiled


def main():
	from pathlib import Path
	import argparse

	parser = argparse.ArgumentParser(description="X-ray fonts")
	parser.add_argument("ufo", type=Font.open, help="Path to the input font file.")
	parser.add_argument("--glyph_names", nargs="+", help="List of glyph names to process.")
	args = parser.parse_args()
	
	ufo = args.ufo
	ufo_path = Path(ufo.path)
	
	x_rayed_ufo = x_ray(ufo)
	output_file_name = f"{ufo_path.stem}_x_rayed.ttf"
	x_rayed_ufo.save(ufo_path.parent/output_file_name)

if __name__ == "__main__":
	from datetime import datetime
	import cProfile
	import pstats
	start = datetime.now()
	# profiler = cProfile.Profile()
	# profiler.enable()
	main()
	# profiler.disable()
	# stats = pstats.Stats(profiler)
	# stats.sort_stats(pstats.SortKey.TIME)
	# stats.print_stats(10)
	print((datetime.now() - start).total_seconds())