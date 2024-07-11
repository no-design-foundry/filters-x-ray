from typing import Tuple
from defcon import Font
from fontTools.pens.basePen import BasePen, AbstractPen
from fontTools.designspaceLib import DesignSpaceDocument
from fontTools.ttLib import TTFont, newTable
from math import atan2, cos, sin, pi
from ufo2ft import compileOTF, compileTTF

font = Font("font_2.ufo")

def circle(pen, center, radius, tension=1):
    x, y = center
    pen.moveTo((x, y+radius))
    pen.curveTo((x - radius * tension, y + radius), (x - radius, y + radius * tension), (x - radius, y))
    pen.curveTo((x - radius, y - radius * tension), (x - radius * tension, y - radius), (x, y - radius))
    pen.curveTo((x + radius * tension, y - radius), (x + radius, y - radius * tension), (x + radius, y))
    pen.curveTo((x + radius, y + radius * tension), (x + radius * tension, y + radius), (x, y + radius))
    pen.closePath()

def line_shape(pen, point_a, point_b, thickness):
    (x_a, y_a), (x_b, y_b) = point_a, point_b
    angle = atan2(y_b - y_a, x_b - x_a) + pi / 2
    x_offset = cos(angle) * thickness
    y_offset = sin(angle) * thickness

    point_1 = (x_a + x_offset, y_a + y_offset)
    point_2 = (x_b + x_offset, y_b + y_offset)
    point_3 = (x_b - x_offset, y_b - y_offset)
    point_4 = (x_a - x_offset, y_a - y_offset)

    pen.moveTo(point_4)
    pen.lineTo(point_3)
    pen.lineTo(point_2)
    pen.lineTo(point_1)
    pen.closePath()


class XRayPen(AbstractPen):
    def __init__(self, handle_line_layer, handle_layer, line_width, point_size, handle_size):
        self.handle_line_layer = handle_line_layer
        self.handle_layer = handle_layer
        self.line_width = line_width
        self.point_size = point_size
        self.handle_size = handle_size
        self.last_point = None
        pass
        
    def handle(self, point):
        circle(self.handle_layer, point, self.handle_size, tension=.5)

    def point(self, point):
        circle(self.handle_layer, point, self.point_size, tension=.8)

    
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
        line_shape(self.handle_line_layer, self.last_point, points[0], self.line_width)
        for from_point, to_point in zip(points[1:], points):
            line_shape(self.handle_line_layer, from_point, to_point, self.line_width)
        for point in points[:-1]:
            self.handle(point)
        self.point(points[-1])
        self.last_point = points[-1]

    def addComponent(self, *args, **kwargs) -> None:
        self.handle_line_layer.addComponent(*args, **kwargs)
        self.handle_layer.addComponent(*args, **kwargs)

output_font = Font()
output_font.info.unitsPerEm = font.info.unitsPerEm
scale_factor = output_font.info.unitsPerEm / 1000

for glyph_name in font.keys():
    glyph = font[glyph_name]

    output_glyph_handles = output_font.newGlyph(glyph_name + "_handles")
    output_glyph_handles.width = glyph.width

    output_glyph_handle_lines = output_font.newGlyph(glyph_name + "_lines")
    output_glyph_handle_lines.width = glyph.width

    output_glyph = output_font.newGlyph(glyph_name)
    glyph.draw(output_glyph.getPen())
    output_glyph.width = glyph.width
    output_glyph.unicodes = glyph.unicodes

    handle_line_layer = output_glyph_handle_lines.getPen()
    handle_layer = output_glyph_handles.getPen()
    x_ray_pen = XRayPen(handle_line_layer, handle_layer, line_width=2 * scale_factor, point_size=20 * scale_factor, handle_size=10 * scale_factor)
    glyph.draw(x_ray_pen)

compiled = compileOTF(output_font)
compiled.save("output.otf")
compiled = compileTTF(output_font)
compiled.save("output.ttf")
