from fontTools.pens.basePen import BasePen, AbstractPen
from math import atan2, cos, sin, pi, hypot, sqrt
from defcon import Point, Contour, Glyph, Component
from .outline_glyph import outline_glyph
from fontTools.designspaceLib import (
	DesignSpaceDocument,
	SourceDescriptor,
	AxisDescriptor,
)
from defcon import Font
from ufo2ft import compileVariableTTF
from .colorize import colorize


def circle(layer, center, diameter, tension=1):
	x, y = center
	radius = diameter / 2
	contour = Contour()
	contour._points = [
		Point((x - radius * tension, y + radius)),
		Point((x - radius, y + radius * tension)),
		Point((x - radius, y), "curve"),
		Point((x - radius, y - radius * tension)),
		Point((x - radius * tension, y - radius)),
		Point((x, y - radius), "curve"),
		Point((x + radius * tension, y - radius)),
		Point((x + radius, y - radius * tension)),
		Point((x + radius, y), "curve"),
		Point((x + radius, y + radius * tension)),
		Point((x + radius * tension, y + radius)),
		Point((x, y + radius), "curve"),
	]
	layer._contours.append(contour)


def square(layer, center, size):
	x, y = center
	contour = Contour()
	contour._points = [
		Point((x - size / 2, y - size / 2), "line"),
		Point((x + size / 2, y - size / 2), "line"),
		Point((x + size / 2, y + size / 2), "line"),
		Point((x - size / 2, y + size / 2), "line"),
	]
	layer._contours.append(contour)

def scale_glyph(glyph, scale_factor):
	for contour in glyph:
		for point in contour:
			point.x = round(point.x * scale_factor)
			point.y = round(point.y * scale_factor)
	glyph.width = round(glyph.width * scale_factor) 
	return glyph

def line_shape(output_glyph, point_a, point_b, thickness):
	(x_a, y_a), (x_b, y_b) = point_a, point_b
	angle = atan2(y_b - y_a, x_b - x_a) + pi / 2
	x_offset = cos(angle) * thickness / 2
	y_offset = sin(angle) * thickness / 2

	point_objects = [
		Point((x_a + x_offset, y_a + y_offset), segmentType="line"),
		Point((x_b + x_offset, y_b + y_offset), segmentType="line"),
		Point((x_b - x_offset, y_b - y_offset), segmentType="line"),
		Point((x_a - x_offset, y_a - y_offset), segmentType="line"),
	]

	contour = Contour()
	contour._points = point_objects
	output_glyph._contours.append(contour)


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
		offset_x = p1[0] - offset * v1_normalized[1]  # Perpendicular offset direction
		offset_y = p1[1] + offset * v1_normalized[0]  # Perpendicular offset direction
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
		use_components=False,
		handle_component_name=None,
		point_component_name=None,
	):
		self.handle_line_layer = handle_line_layer
		self.handle_layer = handle_layer
		self.handle_line_layer_pen = handle_line_layer.getPen()
		self.handle_layer_pen = handle_layer.getPen()
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
			self.handle_layer_pen.addComponent(
				self.handle_component_name, (1, 0, 0, 1, point[0], point[1])
			)
		else:
			circle(self.handle_layer, point, self.handle_size, tension=0.66)

	def point(self, point):
		if self.use_components:
			self.handle_layer_pen.addComponent(
				self.point_component_name, (1, 0, 0, 1, point[0], point[1])
			)
		else:
			square(self.handle_layer, point, self.point_size)

	def moveTo(self, point):
		self.point(point)
		self.last_point = point

	def lineTo(self, point):
		self.point(point)
		self.last_point = point

	def curveTo(self, point_1, point_2, point_3):
		line_shape(self.handle_line_layer, self.last_point, point_1, self.line_width)
		line_shape(self.handle_line_layer, point_2, point_3, self.line_width)

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
		for p in range(1, len(points) - 1):
			prev_point = points[p - 1]
			point = points[p]
			next_point = points[p + 1]

			offset_inner = calculate_offset(prev_point, point, next_point, line_width)
			offset_outer = calculate_offset(prev_point, point, next_point, -line_width)

			if p == 1:
				outer_points.append(add_offset(prev_point, offset_outer))
				inner_points.append(add_offset(prev_point, offset_inner))
			outer_points.append(add_offset(point, offset_outer))
			inner_points.append(add_offset(point, offset_inner))
			if p == len(points) - 2:
				outer_points.append(add_offset(next_point, offset_outer))
				inner_points.append(add_offset(next_point, offset_inner))

		points = outer_points + inner_points[::-1]
		contour = Contour()
		for point in points:
			contour._points.append(Point(point, segmentType="line"))
		# print(contour)
		self.handle_line_layer._contours.append(contour)
		self.last_point = last_point
		self.point(last_point)

	def addComponent(self, glyph_name, transformation, **kwargs) -> None:
		self.handle_line_layer.appendComponent(glyph_name)
		self.handle_layer.appendComponent(glyph_name)


def x_ray_master(font, output_font, outline_width, line_width, point_size, handle_size):
	output_font.info.unitsPerEm = font.info.unitsPerEm

	handle = output_font.newGlyph("handle")
	circle(handle, (0, 0), handle_size, tension=0.55)

	point = output_font.newGlyph("point")
	square(point, (0, 0), point_size)

	rounded_point = output_font.newGlyph("rounded_point")
	circle(rounded_point, (0, 0), point_size, tension=0.55)

	descender = font.info.descender
	ascender = max(font.info.ascender, font.info.capHeight)

	ss_glyphs = []
	
	for glyph_name in font.keys():
		if glyph_name in ["handle", "point"]:
			continue
		glyph = font[glyph_name]

		bounds_glyph = output_font.newGlyph(glyph_name + "_bounds")
		bounds_glyph.width = glyph.width

		bounds_glyph_pen = bounds_glyph.getPen()
		bounds_glyph_pen.moveTo((0, descender))
		bounds_glyph_pen.lineTo((glyph.width, descender))
		bounds_glyph_pen.lineTo((glyph.width, ascender))
		bounds_glyph_pen.lineTo((0, ascender))
		bounds_glyph_pen.closePath()

		output_glyph_handles = output_font.newGlyph(glyph_name + "_handles")
		output_glyph_handles.width = glyph.width

		output_glyph_handle_lines = output_font.newGlyph(glyph_name + "_lines")
		output_glyph_handle_lines.width = glyph.width

		output_glyph = output_font.newGlyph(glyph_name)

		outlined_glyph = output_font.newGlyph(glyph_name + "_outlined")
		
		glyph.draw(outlined_glyph.getPen())
		outline_glyph(outlined_glyph, -outline_width/2)

		inner_shape = Glyph()
		glyph.draw(inner_shape.getPen())
		outline_glyph(inner_shape, outline_width/2)
		for contour in inner_shape:
			contour.reverse()
		inner_shape.draw(outlined_glyph.getPen())

		filled_glyph = output_font.newGlyph(glyph_name + ".filled")
		glyph.draw(filled_glyph.getPen())
		filled_glyph.width = glyph.width

		output_glyph.width = glyph.width
		output_glyph.unicodes = glyph.unicodes

		handle_line_layer = output_glyph_handle_lines
		handle_layer = output_glyph_handles

		x_ray_pen = XRayPen(
			handle_line_layer,
			handle_layer,
			line_width=line_width,
			point_size=point_size,
			handle_size=handle_size,
			use_components=not True,
			handle_component_name="handle",
			point_component_name="point",
		)
		glyph.draw(x_ray_pen)

		rounded_point_layer = output_font.newGlyph(glyph_name + "_rounded_point")
		rounded_point_layer.width = glyph.width
		handle_layer.draw(rounded_point_layer.getPen())

		for component in rounded_point_layer.components:
			if component.baseGlyph == "point":
				component.baseGlyph = "rounded_point"

		output_glyph._contours.extend(handle_line_layer._contours + handle_layer._contours + outlined_glyph._contours) 

		output_font.newGlyph(glyph_name + ".rounded").width = glyph.width
		output_font.newGlyph(glyph_name + ".no-bg").width = glyph.width
		output_font.newGlyph(glyph_name + ".rounded.no-bg").width = glyph.width

		ss_glyphs.append(glyph_name)

	for pair in font.kerning:
		output_font.kerning[pair] = font.kerning[pair]
		for gn_index, glyph_name in enumerate(pair):
			if glyph_name in ss_glyphs:
				for suffix in [".rounded", ".no-bg", ".rounded.no-bg"]:
					new_pair = list(pair)
					new_pair[gn_index] = glyph_name + suffix
					output_font.kerning[tuple(new_pair)] = font.kerning[pair]
		if pair[0] in ss_glyphs and pair[1] in ss_glyphs:
			for suffix in [".rounded", ".no-bg", ".rounded.no-bg"]:
				new_pair = [pair[0] + suffix, pair[1] + suffix]
				output_font.kerning[tuple(new_pair)] = font.kerning[pair]

	output_font.features.text = f"""
	feature ss01 {{
		{"\n".join([f"sub {glyph_name} by {glyph_name}.rounded;" for glyph_name in ss_glyphs])}
	}} ss01;

	feature ss02 {{
		{"\n".join([f"sub {glyph_name} by {glyph_name}.filled;" for glyph_name in ss_glyphs])}
	}} ss02;

	"""

	return output_font


def x_ray(font, outline_color="#000000", line_color="#000000", point_color="#000000"):
	
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
	doc.addAxis(axis_outline)

	axis_line = AxisDescriptor()
	axis_line.minimum = 1
	axis_line.maximum = 20
	axis_line.default = axis_line.minimum
	axis_line.name = "line_width"
	axis_line.tag = "LINE"
	doc.addAxis(axis_line)

	axis_point = AxisDescriptor()
	axis_point.minimum = 10
	axis_point.maximum = 40
	axis_point.default = axis_point.minimum
	axis_point.name = "point_size"
	axis_point.tag = "POIN"
	doc.addAxis(axis_point)

	axis_handle = AxisDescriptor()
	axis_handle.minimum = 10
	axis_handle.maximum = 40
	axis_handle.default = axis_handle.minimum
	axis_handle.name = "handle_size"
	axis_handle.tag = "HAND"
	doc.addAxis(axis_handle)

	# line width, point size, handle size
	for outline_width in [axis_outline.minimum, axis_outline.maximum]:
		for line_width in [axis_line.minimum, axis_line.maximum]:
			for point_size in [axis_point.minimum, axis_point.maximum]:
				for handle_size in [axis_handle.minimum, axis_handle.maximum]:
					source = SourceDescriptor()
					source.font = x_ray_master(
						font,
						Font(),
						outline_width * drawing_scale_factor,
						line_width * drawing_scale_factor,
						point_size * drawing_scale_factor,
						handle_size * drawing_scale_factor
					)
					source.location = dict(
						outline_width=outline_width,
						line_width=line_width,
						point_size=point_size,
						handle_size=handle_size,
					)
					doc.addSource(source)

	compiled = compileVariableTTF(doc, optimizeGvar=False)
	colorize(compiled, font.keys(), outline_color=outline_color, line_color=line_color, point_color=point_color)
	compiled.save("variable.ttf")
	return compiled
