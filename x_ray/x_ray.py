from fontTools.pens.basePen import BasePen, AbstractPen
from math import atan2, cos, sin, pi, hypot, sqrt
from fontTools.pens.reverseContourPen import ReverseContourPen
from ufoLib2.objects.font import Font
from ufoLib2.objects.point import Point
from ufoLib2.objects.contour import Contour
from ufoLib2.objects.glyph import Glyph
from ufoLib2.objects.anchor import Anchor
from ufoLib2.objects.component import Component
from copy import deepcopy
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
except ImportError:
	from outline_glyph import outline_glyph
	from normalizing_pen import NormalizingPen
	from colorize import colorize


def circle(layer, center, diameter, tension=1):
	x, y = center
	radius = diameter / 2
	contour = [
		{"x": x - radius * tension, "y": y + radius, "type": None},
		{"x": x - radius, "y": y + radius * tension, "type": None},
		{"x": x - radius, "y": y, "type": "curve"},
		{"x": x - radius, "y": y - radius * tension, "type": None},
		{"x": x - radius * tension, "y": y - radius, "type": None},
		{"x": x, "y": y - radius, "type": "curve"},
		{"x": x + radius * tension, "y": y - radius, "type": None},
		{"x": x + radius, "y": y - radius * tension, "type": None},
		{"x": x + radius, "y": y, "type": "curve"},
		{"x": x + radius, "y": y + radius * tension, "type": None},
		{"x": x + radius * tension, "y": y + radius, "type": None},
		{"x": x, "y": y + radius, "type": "curve"},
	]
	layer.contours.append(contour)


def square(layer, center, size):
	x, y = center
	contour = [
		{"x": x - size / 2, "y":y - size / 2, "type": "line"},
		{"x": x + size / 2, "y": y - size / 2, "type": "line"},
		{"x": x + size / 2, "y": y + size / 2, "type": "line"},
		{"x": x - size / 2, "y": y + size / 2, "type": "line"},
	]
	layer.contours.append(contour)

def scale_glyph(glyph, scale_factor):
	for contour in glyph:
		for point in contour:
			point.x = round(point.x * scale_factor)
			point.y = round(point.y * scale_factor)
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

	contour = [
		{"x": x_a + x_offset, "y": y_a + y_offset, "type": "line"},
		{"x": x_b + x_offset, "y": y_b + y_offset, "type": "line"},
		{"x": x_b - x_offset, "y": y_b - y_offset, "type": "line"},
		{"x": x_a - x_offset, "y": y_a - y_offset, "type": "line"},
	]

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
		handle_line_layer,
		handle_layer,
		line_width,
		point_size,
		handle_size,
		use_components=True,
		handle_component_name=None,
		point_component_name=None,
	):
		self.handle_line_layer = handle_line_layer
		self.handle_layer = handle_layer
		self.line_width = line_width
		self.point_size = point_size
		self.handle_size = handle_size
		self.use_components = use_components
		self.handle_component_name = handle_component_name
		self.point_component_name = point_component_name
		self.last_point = None
		pass

	def handle(self, point):
		if self.use_components:
			self.handle_layer.components.append(
				Component(self.handle_component_name, (1, 0, 0, 1, point[0], point[1]))
			)
		else:
			if self.handle_layer:
				circle(self.handle_layer, point, self.handle_size, tension=0.66)

	def point(self, point):
		if self.use_components:
			self.handle_layer.components.append(
				Component(self.point_component_name, (1, 0, 0, 1, point[0], point[1]))
			)
		else:
			if self.handle_layer:
				square(self.handle_layer, point, self.point_size)

	def moveTo(self, point):
		self.point(point)
		self.last_point = point

	def lineTo(self, point):
		self.point(point)
		self.last_point = point

	def handle_line(self, point_1, point_2):
		if self.handle_line_layer:
			line_shape(self.handle_line_layer, point_1, point_2, self.line_width)

	def curveTo(self, point_1, point_2, point_3):
		self.handle_line(self.last_point, point_1)
		self.handle_line(point_2, point_3)

		self.handle(point_1)
		self.handle(point_2)
		self.point(point_3)

		self.last_point = point_3

	def qCurveTo(self, *points):

		for point in points[:-1]:
			self.handle(point)

		last_point = points[-1]
		line_width = self.line_width / 2

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
		self.handle_line_layer.contours.append(contour)
		self.last_point = last_point
		self.point(last_point)

	def addComponent(self, glyph_name, *args, **kwargs) -> None:
		pass
		# self.handle_line_layer.components.append(Component(glyph_name, *args, **kwargs))
		# self.handle_layer.components.append(Component(glyph_name, *args, **kwargs))

def duplicate_components(glyph_source, glyph_destination, suffix):
	for component in glyph_source.components:
		glyph_destination.components.append(Component(component.baseGlyph + suffix, component.transformation))

def copy_data_from_glyph(glyph_source, glyph_destination, exclude=[]):
	glyph_destination.width = glyph_source.width
	glyph_destination.unicodes = glyph_source.unicodes
	glyph_destination.anchors = glyph_source.anchors
	glyph_destination.components = glyph_source.components
	if "contours" not in exclude:
		glyph_destination.contours = glyph_source.contours

def get_segments(points):
	if not len(points):
		return []
	segments = [[]]
	lastWasOffCurve = False
	for point in points:
		segments[-1].append(point)
		if point["type"] is not None:
			segments.append([])
		lastWasOffCurve = point["type"] is None
	if len(segments[-1]) == 0:
		del segments[-1]
	if lastWasOffCurve:
		if len(segments) != 1:
			lastSegment = segments[-1]
			segment = segments.pop(0)
			lastSegment.extend(segment)
	elif segments[0][-1]["type"] != "move":
		segment = segments.pop(0)
		segments.append(segment)
	return segments

class PerformanceGlyph():
	def __init__(self, glyph=None, name=None, width=0, unicodes=[]):
		self.unicodes = glyph.unicodes if glyph else unicodes
		self.width = glyph.width if glyph else width
		self.name = glyph.name if glyph else name
		self.contours = []
		self.anchors = []
		self.components = []
		if glyph:
			for contour in glyph.contours:
				points = []
				for point in contour.points:
					points.append({
						"x": point.x,
						"y": point.y,
						"type": point.type,
					})
				self.contours.append(points)

			for anchor in glyph.anchors:
				self.anchors.append({
					"x": anchor.x,
					"y": anchor.y,
					"name": anchor.name,
				})

			for component in glyph.components:
				self.components.append({
					"baseGlyph": component.baseGlyph,
					"transformation": component.transformation,
				})

	def copy(self):
		copied = PerformanceGlyph(name=self.name, width=self.width, unicodes=self.unicodes)
		copied.contours = deepcopy(self.contours)
		copied.anchors = self.anchors
		copied.components = self.components
		return copied

	def draw(self, pen):
		for contour in self:
			segments = get_segments(contour)
			for s, segment in enumerate(segments):
				segment_type = segment[-1]["type"]
				segment_points = [(point["x"], point["y"]) for point in segment]
				if s == 0:
					pen.moveTo(segment_points[0])
				if segment_type == "line":
					pen.lineTo(*segment_points)
				elif segment_type == "curve":
					pen.curveTo(*segment_points)
				else:
					raise NotImplementedError(f"Unsupported segment type: {segment_type}")
			pen.endPath()


	def __iter__(self):
		for contour in self.contours:
			yield contour

	def to_glyph(self):
		glyph = Glyph()
		for contour in self.contours:
			contour_object = Contour()
			for point in contour:
				contour_object.points.append(Point(point["x"], point["y"], point["type"]))
			glyph.contours.append(contour_object)
		for anchor in self.anchors:
			glyph.appendAnchor(Anchor(anchor["name"], (anchor["x"], anchor["y"])))
		for component in self.components:
			glyph.appendComponent(Component(component["baseGlyph"], component["transformation"]))
		glyph.width = self.width
		return glyph


	

def x_ray_master(font, output_font, outline_width, line_width, point_size, handle_size):
	output_font.info.unitsPerEm = font.info.unitsPerEm

	handle = PerformanceGlyph(name="handle")
	circle(handle, (0, 0), handle_size, tension=0.55)
	handle.to_glyph(output_font)

	point = PerformanceGlyph(name="point")
	square(point, (0, 0), point_size)
	point.to_glyph(output_font)

	descender = font.info.descender
	ascender = max(font.info.ascender, font.info.capHeight)

	ss_glyphs = []
	
	for glyph_name in font.keys():
		if glyph_name in ["handle", "point"]:
			continue
		input_glyph = font[glyph_name]

		glyph = PerformanceGlyph(font[glyph_name])

		normalized_glyph = Glyph()
		normalizing_pen = NormalizingPen(normalized_glyph.getPen())
		input_glyph.draw(normalizing_pen)
		normalized_glyph = PerformanceGlyph(normalized_glyph)

		handle_line_layer = PerformanceGlyph(name=f"{glyph.name}_lines")
		handle_layer = PerformanceGlyph(name=f"{glyph.name}_handles")

		x_ray_pen = XRayPen(
			handle_line_layer,
			handle_layer,
			line_width=line_width,
			point_size=point_size,
			handle_size=handle_size,
			use_components=False,
			handle_component_name="handle",
			point_component_name="point",
		)
		glyph.draw(x_ray_pen)

		default_glyph = glyph.copy()
		default_glyph.to_glyph(output_font)

		handle_line_layer.to_glyph(output_font)
		handle_layer.to_glyph(output_font)

		outlined_glyph = PerformanceGlyph(name=f"{glyph.name}_outlined", width=glyph.width, unicodes=glyph.unicodes)

		outlined_glyph_inner = normalized_glyph.copy()
		outlined_glyph_outer = normalized_glyph.copy()

		outline_glyph(outlined_glyph_inner, -outline_width)
		outline_glyph(outlined_glyph_outer, outline_width)

		outlined_glyph.contours = outlined_glyph_inner.contours + outlined_glyph_outer.contours
		outlined_glyph.to_glyph(output_font)

		# output_glyph.contours.extend(handle_line_layer.contours + handle_layer.contours + outlined_glyph.contours) 


	for pair in font.kerning:
		output_font.kerning[pair] = font.kerning[pair]
		for gn_index, glyph_name in enumerate(pair):
			if glyph_name in ss_glyphs:
				for suffix in [".bounds", ".filled", ".bounds.filled"]:
					new_pair = list(pair)
					new_pair[gn_index] = glyph_name + suffix
					output_font.kerning[tuple(new_pair)] = font.kerning[pair]
		if pair[0] in ss_glyphs and pair[1] in ss_glyphs:
			for suffix in [".bounds", ".filled", ".bounds.filled"]:
				new_pair = [pair[0] + suffix, pair[1] + suffix]
				output_font.kerning[tuple(new_pair)] = font.kerning[pair]

	output_font.features.text = f"""
	feature ss01 {{
		featureNames {{
			name "Glyph's Bounding Box";
		}};
		{" ".join([f"sub {glyph_name} by {glyph_name}.bounds;" for glyph_name in ss_glyphs])}
	}} ss01;

	feature ss02 {{
		featureNames {{
			name "Filled Glyph";
		}};
		{" ".join([f"sub {glyph_name} by {glyph_name}.filled;" for glyph_name in ss_glyphs])}
		{" ".join([f"sub {glyph_name}.bounds by {glyph_name}.bounds.filled;" for glyph_name in ss_glyphs])}
	}} ss02;
	"""

	return output_font


def x_ray(font, outline_color="#0000FF", line_color="#00FF00", point_color="#FF0000"):
	
	new_upm = 16_384
	scale_factor = new_upm / font.info.unitsPerEm
	drawing_scale_factor = scale_factor * (font.info.unitsPerEm / 1000)
	for glyph in font:
		scale_glyph(glyph, scale_factor)
	font.info.unitsPerEm = new_upm
	font.info.ascender *= scale_factor
	font.info.descender *= scale_factor
	font.info.capHeight *= scale_factor
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


	
	# line width, point size, handle size
	glyphs = {}
	normalized_glyphs = {}
	outlined_glyphs = {}
	point_glyphs = {}
	handle_glyphs = {}

	for glyph in font:
		glyphs[glyph.name] =  PerformanceGlyph(glyph)
		normalized_glyph = Glyph()
		normalizing_pen = NormalizingPen(normalized_glyph.getPen())
		glyph.draw(normalizing_pen)
		normalized_glyphs[glyph.name] = PerformanceGlyph(normalized_glyph)
	
	for glyph_name in font.keys():
		for outline_width in [axis_outline.minimum, axis_outline.maximum]:
			outlined_glyph_inner = normalized_glyphs[glyph_name].copy()
			
			reversed_contours = []
			for contour in outlined_glyph_inner.contours:
				reversed_contour = contour[1:][::-1] + [contour[0]]
				reversed_contours.append(reversed_contour)
			outlined_glyph_inner.contours = reversed_contours

			outlined_glyph_outer = normalized_glyphs[glyph_name].copy()
			outline_glyph(outlined_glyph_inner, -outline_width)
			outline_glyph(outlined_glyph_outer, outline_width)
			output_glyph = PerformanceGlyph(name=f"{glyph_name}_outlined", width=glyph.width, unicodes=glyph.unicodes)
			output_glyph.contours = outlined_glyph_inner.contours + outlined_glyph_outer.contours
			outlined_glyphs.setdefault(outline_width, {})[glyph_name] = output_glyph


		for point_size in [axis_point.minimum, axis_point.maximum]:
			glyph = glyphs[glyph_name].copy()
			point_layer = PerformanceGlyph(name=f"{glyph_name}_lines")
			x_ray_pen = XRayPen(
				None,
				point_layer,
				line_width=axis_line.minimum * drawing_scale_factor,
				point_size=point_size * drawing_scale_factor,
				handle_size=axis_handle.minimum * drawing_scale_factor,
				use_components=False,
				handle_component_name="handle",
				point_component_name="point",
			)
			glyph.draw(x_ray_pen)
			point_glyphs.setdefault(point_size, {})[glyph_name] = point_layer

		for handle_size in [axis_handle.minimum, axis_handle.maximum]:
			glyph = glyphs[glyph_name].copy()
			handle_layer = PerformanceGlyph(name=f"{glyph_name}_handles")
			x_ray_pen = XRayPen(
				handle_layer,
				None,
				line_width=axis_line.minimum * drawing_scale_factor,
				point_size=axis_point.minimum * drawing_scale_factor,
				handle_size=handle_size * drawing_scale_factor,
				use_components=False,
				handle_component_name="handle",
				point_component_name="point",
			)
			glyph.draw(x_ray_pen)
			handle_glyphs.setdefault(handle_size, {})[glyph_name] = handle_layer
	
	for dictionary in [outlined_glyphs, point_glyphs, handle_glyphs]:
		for key in dictionary.keys():
			for key_2 in dictionary[key].keys():
				dictionary[key][key_2] = dictionary[key][key_2].to_glyph()

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

					for glyph_name in font.keys():
						# outlined_glyphs[outline_width][glyph_name].to_glyph(master)
						# handle_glyphs[handle_size][glyph_name].to_glyph(master)
						# point_glyphs[point_size][glyph_name].to_glyph(master)
						copy_data_from_glyph(outlined_glyphs[outline_width][glyph_name], master.newGlyph(glyph_name + "_outlined"))
						copy_data_from_glyph(handle_glyphs[handle_size][glyph_name], master.newGlyph(glyph_name + "_handles"))
						copy_data_from_glyph(point_glyphs[point_size][glyph_name], master.newGlyph(glyph_name + "_lines"))
						copy_data_from_glyph(font[glyph_name], master.newGlyph(glyph_name), exclude=["contours"])
						master.newGlyph(glyph_name + ".filled")
						master.newGlyph(glyph_name + ".bounds")
						master.newGlyph(glyph_name + "_bounds")
						master.newGlyph(glyph_name + ".bounds.filled")


					source = SourceDescriptor()
					source.font = master
					source.location = dict(
						outline_width=outline_width,
						line_width=line_width,
						point_size=point_size,
						handle_size=handle_size,
					)
					doc.addSource(source)

	# quit()
	# for s, source in enumerate(doc.sources):
	# 	source.font.save(f"/Users/js/Desktop/exports 2/ufo/debug/{s}.ufo")
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


# normalized_glyph = Glyph()
# normalizing_pen = NormalizingPen(normalized_glyph.getPen())
# glyph.draw(normalizing_pen)
# glyph.clearContours()
# normalized_glyph.draw(glyph.getPen())