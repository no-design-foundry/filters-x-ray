import struct

def hex_to_rgba(color_hex):
    color_hex = color_hex.lstrip("#")
    return tuple(int(color_hex[i:i+2], 16) for i in (0, 2, 4)) + (255,)

def update_cpal_colors(font_path, output_path, palette_index, new_colors):
    with open(font_path, 'rb') as font_file:
        font_data = bytearray(font_file.read())

    # Locate CPAL table
    cpal_offset = locate_cpal_offset(font_data)
    if cpal_offset is None:
        print("CPAL table not found.")
        return

    # Read CPAL table header to find color records and palette offsets
    version, num_palettes, num_color_records, color_record_offset = struct.unpack_from(">HHHH", font_data, cpal_offset)
    palette_offset_array_offset = cpal_offset + 10  # Offset for palette array

    # Find the specific palette we need to modify
    if palette_index >= num_palettes:
        print(f"Palette index {palette_index} out of range (only {num_palettes} available).")
        return

    palette_offset = struct.unpack_from(">H", font_data, palette_offset_array_offset + palette_index * 2)[0]
    palette_start = cpal_offset + color_record_offset + palette_offset * 4

    # Convert hex colors to RGBA format
    new_rgba_colors = [hex_to_rgba(color) for color in new_colors]

    # Update each color in the specified palette
    for i, (r, g, b, a) in enumerate(new_rgba_colors):
        if i >= num_color_records:
            break
        color_offset = palette_start + i * 4
        font_data[color_offset:color_offset + 4] = bytes([r, g, b, a])

    with open(output_path, 'wb') as modified_font_file:
        modified_font_file.write(font_data)
    
    print(f"Updated CPAL palette colors saved to {output_path}")

def locate_cpal_offset(font_data):
    num_tables = struct.unpack_from(">H", font_data, 4)[0]
    table_offset = 12
    for _ in range(num_tables):
        table_name = font_data[table_offset:table_offset + 4].decode()
        if table_name == 'CPAL':
            return struct.unpack_from(">I", font_data, table_offset + 8)[0]
        table_offset += 16
    return None

# Example usage
font_path = "0.ttf"
output_path = "0_modified.ttf"
palette_index = 0  # Index of the palette to update

# Define colors in hex format (as strings) for the palette
new_colors = [
    "#FF5733",  # Background color
    "#33FF57",  # Outline color
    "#3357FF",  # Line color
    "#FF33FF",  # Point color
]

update_cpal_colors(font_path, output_path, palette_index, new_colors)
