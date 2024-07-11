from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables.C_O_L_R_ import LayerRecord
from fontTools.ttLib.tables.C_P_A_L_ import Color
from fontTools.colorLib import builder

# Load the font
font = TTFont("output.ttf")

# Create and populate the CPAL table
cpal = newTable('CPAL')
cpal.version = 0
cpal.numPaletteEntries = 3
cpal.palettes = [
    [Color(red=0, green=0, blue=0, alpha=100), Color(red=100, green=100, blue=100, alpha=255), Color(red=0, green=0, blue=0, alpha=255)],  # Palette 1
    [Color(red=0, green=0, blue=0, alpha=100), Color(red=0, green=0, blue=255, alpha=255), Color(red=255, green=255, blue=0, alpha=255)]  # Palette 2
]
font['CPAL'] = cpal

# Create and populate the COLR table

color_layer_lists = {}

for glyph_name in font.getGlyphOrder():
    if glyph_name.endswith("_lines") or glyph_name.endswith("_handles"):
        continue
    color_layer_lists[glyph_name] = [(glyph_name, 0), (glyph_name + "_lines", 1), (glyph_name + "_handles", 2)]


colr = builder.buildCOLR(color_layer_lists)


font['COLR'] = colr

# Save the modified font
font.save("color_font.ttf")
