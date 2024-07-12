from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables.C_O_L_R_ import LayerRecord
from fontTools.ttLib.tables.C_P_A_L_ import Color
from fontTools.colorLib import builder

# Load the font
def colorize(tt_font):
# Create and populate the CPAL table
    cpal = newTable('CPAL')
    cpal.version = 0
    cpal.numPaletteEntries = 4
    cpal.palettes = [
        [
            Color(red=0, green=0, blue=0, alpha=20),
            Color(red=0, green=0, blue=0, alpha=255),
            Color(red=255, green=0, blue=20, alpha=255),
            Color(red=0, green=0, blue=0, alpha=255)
        ],  # Palette 1
    ]
    tt_font['CPAL'] = cpal

    # Create and populate the COLR table

    color_layer_lists = {}
    suffixes = [(0, "_bounds"), (1, ""), (2, "_lines"), (3, "_handles")]
    rounded_suffixes = [(0, "_bounds"), (1, ""), (2, "_lines"), (3, "_rounded_point")]
    no_bg_suffixes = [(1, ""), (2, "_lines"), (3, "_handles")]
    rounded_no_bg_suffixes = [(1, ""), (2, "_lines"), (3, "_rounded_point")]

    for glyph_name in tt_font.getGlyphOrder():
        if glyph_name.endswith(".no-bg") or glyph_name.endswith(".rounded"):
            continue
        if glyph_name.endswith("_lines") or glyph_name.endswith("_handles") or glyph_name.endswith("_bounds") or glyph_name.endswith("_rounded_point"):
            continue
        if glyph_name in ["handle", "point", "rounded_point"]:
            continue
        color_layer_lists[glyph_name] = [(glyph_name + suffix, index) for index, suffix in suffixes]
        color_layer_lists[f"{glyph_name}.rounded"] = [(glyph_name + suffix, index) for index, suffix in rounded_suffixes]
        color_layer_lists[f"{glyph_name}.no-bg"] = [(glyph_name + suffix, index) for index, suffix in no_bg_suffixes]
        color_layer_lists[f"{glyph_name}.rounded.no-bg"] = [(glyph_name + suffix, index) for index, suffix in rounded_no_bg_suffixes]


    colr = builder.buildCOLR(color_layer_lists)


    tt_font['COLR'] = colr

    # Save the modified font
