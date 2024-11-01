import struct
from io import BytesIO

def load_font_data(font_path):
    with open(font_path, 'rb') as f:
        return f.read()

def get_table_offset(font_data, tag):
    num_tables = struct.unpack('>H', font_data[4:6])[0]
    for i in range(num_tables):
        offset = 12 + i * 16
        table_tag, _, table_offset, _ = struct.unpack('>4sLLL', font_data[offset:offset+16])
        if table_tag.decode() == tag:
            return table_offset
    raise ValueError(f"Table {tag} not found in font.")

def read_cpal_table(font_data, cpal_offset):
    stream = BytesIO(font_data)
    stream.seek(cpal_offset)
    version, num_palette_entries, num_palettes, num_colors, color_offset = struct.unpack('>HHHHL', stream.read(12))

    colors = []
    stream.seek(cpal_offset + color_offset)
    for _ in range(num_colors):
        b, g, r, a = struct.unpack('BBBB', stream.read(4))
        colors.append({'r': r, 'g': g, 'b': b, 'a': a / 255.0})
    
    palette_indices = []
    stream.seek(cpal_offset + 12)
    for _ in range(num_palettes):
        palette_indices.append(struct.unpack('>H', stream.read(2))[0])

    palettes = []
    for palette_start in palette_indices:
        palette = colors[palette_start:palette_start + num_palette_entries]
        palettes.append(palette)
    
    return palettes, version, num_palette_entries

def update_palette_colors(font_data, cpal_offset, new_palettes, num_palette_entries):
    stream = BytesIO(font_data)
    
    colors_per_palette = num_palette_entries
    color_offset = cpal_offset + 12 + len(new_palettes) * 2

    stream.seek(color_offset)
    for palette in new_palettes:
        for color in palette[:colors_per_palette]:
            print(color)
            stream.write(struct.pack('BBBB', *color))
    
    return stream.getvalue()

def save_modified_font(new_font_data, output_path):
    """Save the modified font data to a new file."""
    with open(output_path, 'wb') as f:
        f.write(new_font_data)

font_path = '0.ttf'
font_data = load_font_data(font_path)
cpal_offset = get_table_offset(font_data, 'CPAL')
palettes, version, num_palette_entries = read_cpal_table(font_data, cpal_offset)

new_palettes = [[
    (0, 0, 255, 255),
    (0, 255, 0, 255),
    (255, 0, 0, 255),
    (0, 125, 255, 255),
]]


new_font_data = update_palette_colors(font_data, cpal_offset, new_palettes, num_palette_entries)

output_path = '0_modified.ttf'
save_modified_font(new_font_data, output_path)
