from fontTools.pens.basePen import BasePen, AbstractPen
from math import atan2, cos, sin, pi
from defcon import Point, Contour, Glyph
from outline_glyph import outline_glyph

def circle(pen, center, diameter, tension=1):
    x, y = center
    radius = diameter / 2
    pen.moveTo((x, y+radius))
    pen.curveTo((x - radius * tension, y + radius), (x - radius, y + radius * tension), (x - radius, y))
    pen.curveTo((x - radius, y - radius * tension), (x - radius * tension, y - radius), (x, y - radius))
    pen.curveTo((x + radius * tension, y - radius), (x + radius, y - radius * tension), (x + radius, y))
    pen.curveTo((x + radius, y + radius * tension), (x + radius * tension, y + radius), (x, y + radius))
    pen.closePath()

def square(pen, center, size):
    x, y = center
    pen.moveTo((x - size / 2, y - size / 2))
    pen.lineTo((x + size / 2, y - size / 2))
    pen.lineTo((x + size / 2, y + size / 2))
    pen.lineTo((x - size / 2, y + size / 2))
    pen.closePath()

def line_shape(output_glyph, point_a, point_b, thickness):
    (x_a, y_a), (x_b, y_b) = point_a, point_b
    angle = atan2(y_b - y_a, x_b - x_a) + pi / 2
    x_offset = cos(angle) * thickness/2
    y_offset = sin(angle) * thickness/2

    point_objects = [Point((x_a + x_offset, y_a + y_offset), segmentType="line"),
    Point((x_b + x_offset, y_b + y_offset), segmentType="line"),
    Point((x_b - x_offset, y_b - y_offset), segmentType="line"),
    Point((x_a - x_offset, y_a - y_offset), segmentType="line")]

    contour = Contour()
    contour._points = point_objects
    output_glyph._contours.append(contour)

    # pen.moveTo(point_4)
    # pen.lineTo(point_3)
    # pen.lineTo(point_2)
    # pen.lineTo(point_1)
    # pen.closePath()


class XRayPen(AbstractPen):
    def __init__(self, handle_line_layer, handle_layer, line_width, point_size, handle_size, use_components=False, handle_component_name=None, point_component_name=None):
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
            self.handle_layer_pen.addComponent(self.handle_component_name, (1, 0, 0, 1, point[0], point[1]))
        else:
            circle(self.handle_layer_pen, point, self.handle_size, tension=.66)

    def point(self, point):
        if self.use_components:
            self.handle_layer_pen.addComponent(self.point_component_name, (1, 0, 0, 1, point[0], point[1]))
        else:
            square(self.handle_layer_pen, point, self.point_size)

    
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



def x_ray_font(font, output_font, line_width, point_size, handle_size):
    output_font.info.unitsPerEm = font.info.unitsPerEm

    handle = output_font.newGlyph("handle")
    circle(handle.getPen(), (0, 0), handle_size , tension=.55)

    point = output_font.newGlyph("point")
    square(point.getPen(), (0, 0), point_size )

    rounded_point = output_font.newGlyph("rounded_point")
    circle(rounded_point.getPen(), (0, 0), point_size, tension=.55)


    descender = font.info.descender
    ascender = max(font.info.ascender, font.info.capHeight)

    ss_glyphs = []

    o = line_width / 2
    for glyph_name in font.keys():
        if glyph_name in ["handle", "point"]:
            continue
        # if glyph_name not in [".notdef", "V", "O", "W", "L", "T", "A"]:
        #     continue
        glyph = font[glyph_name]

        bounds_glyph = output_font.newGlyph(glyph_name + "_bounds")
        bounds_glyph.width = glyph.width

        bounds_glyph_pen = bounds_glyph.getPen()
        bounds_glyph_pen.moveTo((0, descender))
        bounds_glyph_pen.lineTo((glyph.width, descender))
        bounds_glyph_pen.lineTo((glyph.width, ascender))
        bounds_glyph_pen.lineTo((0, ascender ))
        bounds_glyph_pen.closePath()

        output_glyph_handles = output_font.newGlyph(glyph_name + "_handles")
        output_glyph_handles.width = glyph.width

        output_glyph_handle_lines = output_font.newGlyph(glyph_name + "_lines")
        output_glyph_handle_lines.width = glyph.width

        output_glyph = output_font.newGlyph(glyph_name)
        glyph.draw(output_glyph.getPen())
        outline_glyph(output_glyph, o )

        inner_shape = Glyph()
        glyph.draw(inner_shape.getPen())
        outline_glyph(inner_shape, -o )
        for contour in inner_shape:
            contour.reverse()
        inner_shape.draw(output_glyph.getPen())


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
            use_components=True,
            handle_component_name="handle",
            point_component_name="point"
            )
        glyph.draw(x_ray_pen)

        rounded_point_layer = output_font.newGlyph(glyph_name + "_rounded_point")
        rounded_point_layer.width = glyph.width
        handle_layer.draw(rounded_point_layer.getPen())

        for component in rounded_point_layer.components:
            if component.baseGlyph == "point":
                component.baseGlyph = "rounded_point"

        output_font.newGlyph(glyph_name + ".rounded").width = glyph.width
        output_font.newGlyph(glyph_name + ".no-bg").width = glyph.width
        output_font.newGlyph(glyph_name + ".rounded.no-bg").width = glyph.width
        ss_glyphs.append(glyph_name)

    output_font.kerning
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
        {"\n".join([f"sub {glyph_name} by {glyph_name}.no-bg;" for glyph_name in ss_glyphs])}
        {"\n".join([f"sub {glyph_name}.rounded by {glyph_name}.rounded.no-bg;" for glyph_name in ss_glyphs])}
    }} ss02;
    """

    return output_font