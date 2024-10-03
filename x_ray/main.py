from defcon import Font
from x_ray import x_ray_font
from ufo2ft import compileVariableTTF
from fontTools.designspaceLib import DesignSpaceDocument, SourceDescriptor, AxisDescriptor
from colorize import colorize
from defcon.objects.base import BaseObject

BaseObject.addObserver = lambda *args, **kwargs: None
BaseObject.postNotification = lambda *args, **kwargs: None
BaseObject.removeObserver = lambda *args, **kwargs: None
BaseObject.beginSelfNotificationObservation = lambda *args, **kwargs: None
BaseObject.endSelfContourNotificationObservation = lambda *args, **kwargs: None
BaseObject.dirty = lambda : None
BaseObject.dispatcher = None

def scale_glyph(glyph, scale_factor):
    for contour in glyph:
        for point in contour:
            point.x *= scale_factor
            point.y *= scale_factor
    glyph.width *= scale_factor
    return glyph

def main(font, scale_factor):
    doc = DesignSpaceDocument()

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
    for line_width in [axis_line.minimum, axis_line.maximum]:
        for point_size in [axis_point.minimum, axis_point.maximum]:
            for handle_size in [axis_handle.minimum, axis_handle.maximum]:
                source = SourceDescriptor()
                source.font = x_ray_font(font, Font(), line_width * scale_factor, point_size * scale_factor, handle_size * scale_factor)
                source.location = dict(line_width=line_width, point_size=point_size, handle_size=handle_size)
                doc.addSource(source)


    compiled = compileVariableTTF(doc, optimizeGvar=False)
    colorize(compiled)
    compiled.save("variable.ttf")


if __name__ == "__main__":
    font = Font("./arial_full.ufo")
    new_upm =  16_384
    scale_factor = new_upm / font.info.unitsPerEm
    for glyph in font:
        scale_glyph(glyph, scale_factor)
    font.info.unitsPerEm = new_upm
    font.info.ascender *= scale_factor
    font.info.descender *= scale_factor
    font.info.capHeight *= scale_factor
    font.info.xHeight *= scale_factor
    for key in font.kerning.keys():
        font.kerning[key] *= scale_factor
    
    import cProfile, pstats
    from datetime import datetime
    PROFILE = not True

    
    if PROFILE:
        profiler = cProfile.Profile()
        profiler.enable()
    start = datetime.now()
    main(font, scale_factor = font.info.unitsPerEm / 1000)
    print((datetime.now() - start).total_seconds())
    if PROFILE:
        profiler.disable()
        # stats = pstats.Stats(profiler).strip_dirs().sort_stats('tottime')  # sort by cumulative time spent in function
        stats = pstats.Stats(profiler).sort_stats('tottime')  # sort by cumulative time spent in function
        stats.print_stats(50)  




