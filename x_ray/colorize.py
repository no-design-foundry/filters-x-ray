from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables.C_O_L_R_ import LayerRecord
from fontTools.ttLib.tables.C_P_A_L_ import Color
from fontTools.colorLib import builder

# Load the font
def hex_to_Color(value):
    value = value.lstrip("#")
    r, g, b, *a = tuple(int(value[i:i + 2], 16) for i in range(0, len(value), 2))
    print(r, g, b, a)
    return Color(red=r, green=g, blue=b, alpha=a[0] if a else 255)

def colorize(tt_font, glyph_order, outline_color, line_color, point_color, background_color="#0000000F"):
# Create and populate the CPAL table
    cpal = newTable('CPAL')
    cpal.version = 0
    cpal.numPaletteEntries = 4
    cpal.palettes = [
        [
            hex_to_Color(background_color),
            hex_to_Color(outline_color),
            hex_to_Color(line_color),
            hex_to_Color(point_color),
        ],  # Palette 1
    ]
    tt_font['CPAL'] = cpal

    # Create and populate the COLR table

    color_layer_lists = {}
    suffixes = [(0, "_bounds"), (1, "_outlined"), (2, "_lines"), (3, "_handles")]
    filled_suffixes = [(0, "_bounds"), (1, ".filled"), (2, "_lines"), (3, "_handles")]
    rounded_suffixes = [(0, "_bounds"), (1, "_outlined"), (2, "_lines"), (3, "_rounded_point")]
    no_bg_suffixes = [(1, "_outlined"), (2, "_lines"), (3, "_handles")]
    rounded_no_bg_suffixes = [(1, "_outlined"), (2, "_lines"), (3, "_rounded_point")]

    for glyph_name in glyph_order:
        if glyph_name.endswith(".no-bg") or glyph_name.endswith(".rounded"):
            continue
        if glyph_name.endswith("_lines") or glyph_name.endswith("_handles") or glyph_name.endswith("_bounds") or glyph_name.endswith("_rounded_point"):
            continue
        if glyph_name in ["handle", "point", "rounded_point"]:
            continue
        color_layer_lists[glyph_name] = [(glyph_name + suffix, index) for index, suffix in suffixes]
        color_layer_lists[f"{glyph_name}.filled"] = [(glyph_name + suffix, index) for index, suffix in filled_suffixes]
        color_layer_lists[f"{glyph_name}.rounded"] = [(glyph_name + suffix, index) for index, suffix in rounded_suffixes]
        color_layer_lists[f"{glyph_name}.no-bg"] = [(glyph_name + suffix, index) for index, suffix in no_bg_suffixes]
        color_layer_lists[f"{glyph_name}.rounded.no-bg"] = [(glyph_name + suffix, index) for index, suffix in rounded_no_bg_suffixes]


    colr = builder.buildCOLR(color_layer_lists)


    tt_font['COLR'] = colr

    # Save the modified font
