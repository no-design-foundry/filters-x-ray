import math


import math

def calculate_offset(coordinates, i, offset, num_points, first_point_offset=1):
    p0 = coordinates[i - first_point_offset]
    p1 = coordinates[i]
    p2 = coordinates[(i + 1) % num_points]

    # Calculate vectors
    v1 = (p0[0] - p1[0], p0[1] - p1[1])
    v2 = (p2[0] - p1[0], p2[1] - p1[1])

    # Normalize vectors
    v1_length = math.sqrt(v1[0]**2 + v1[1]**2)
    v2_length = math.sqrt(v2[0]**2 + v2[1]**2)
    
    v1_normalized = (v1[0] / v1_length, v1[1] / v1_length)
    v2_normalized = (v2[0] / v2_length, v2[1] / v2_length)
    
    # Check for collinearity (cross product close to zero)
    cross_product = v1_normalized[0] * v2_normalized[1] - v1_normalized[1] * v2_normalized[0]
    
    if abs(cross_product) < 1e-10:
        # Handle collinear case
        offset_x = p1[0] - offset * v1_normalized[1]  # Perpendicular offset direction
        offset_y = p1[1] + offset * v1_normalized[0]  # Perpendicular offset direction
        return (offset_x, offset_y)
    
    bisector = (v1_normalized[0] + v2_normalized[0], v1_normalized[1] + v2_normalized[1])
    bisector_length = math.sqrt(bisector[0]**2 + bisector[1]**2)
    bisector_normalized = (bisector[0] / bisector_length, bisector[1] / bisector_length)
    
    # Calculate the angle between v1 and v2
    dot_product = v1_normalized[0] * v2_normalized[0] + v1_normalized[1] * v2_normalized[1]
    angle = math.atan2(cross_product, dot_product)
    factor = offset / math.sin(angle / 2)

    # Calculate offset point
    offset_x = p1[0] + bisector_normalized[0] * factor
    offset_y = p1[1] + bisector_normalized[1] * factor
    return (offset_x, offset_y)


def get_simple_offsets(coordinates, offset):
    num_points = len(coordinates)
    offset_points = []
    for i in range(num_points):
        try:   
            (offset_x, offset_y) = calculate_offset(coordinates, i, offset, num_points)
        except ZeroDivisionError:
            for first_point_offset in range(2, num_points):
                try:
                    (offset_x, offset_y) = calculate_offset(coordinates, i, offset, num_points, first_point_offset)
                    break
                except ZeroDivisionError:
                    pass

        offset_points.append((offset_x, offset_y))

    return offset_points


def outline_glyph(glyph, offset_distance):
    for contour in glyph:
        contour_points = [(point.x, point.y) for point in contour]
        offset = get_simple_offsets(contour_points, offset_distance)
        for p, point in enumerate(contour):
            x, y = offset[p]
            point.x = int(x)
            point.y = int(y)


