import math

def calculate_offset(points, offset):
	p0, p1, p2 = points

	# Calculate vectors
	v1 = (p0.x - p1.x, p0.y - p1.y)
	v2 = (p2.x - p1.x, p2.y - p1.y)

	# Normalize vectors
	v1_length = math.sqrt(v1[0]**2 + v1[1]**2)
	v2_length = math.sqrt(v2[0]**2 + v2[1]**2)
	
	v1_normalized = (v1[0] / v1_length, v1[1] / v1_length)
	v2_normalized = (v2[0] / v2_length, v2[1] / v2_length)
	
	# Check for collinearity (cross product close to zero)
	cross_product = v1_normalized[0] * v2_normalized[1] - v1_normalized[1] * v2_normalized[0]
	
	if abs(cross_product) < 1e-10:
		# Handle collinear case
		return (p1.x - offset * v1_normalized[1], p1.y + offset * v1_normalized[0])
	
	bisector = (v1_normalized[0] + v2_normalized[0], v1_normalized[1] + v2_normalized[1])
	bisector_length = math.sqrt(bisector[0]**2 + bisector[1]**2)
	bisector_normalized = (bisector[0] / bisector_length, bisector[1] / bisector_length)
	
	# Calculate the angle between v1 and v2
	dot_product = v1_normalized[0] * v2_normalized[0] + v1_normalized[1] * v2_normalized[1]
	angle = math.atan2(cross_product, dot_product)
	factor = offset / math.sin(angle / 2)

	return (p1.x + bisector_normalized[0] * factor, p1.y + bisector_normalized[1] * factor)


def get_simple_offsets(coordinates, offset):
	num_points = len(coordinates)
	offset_points = []
	for i in range(num_points):
		try:
			points = [
				coordinates[i - 1],
				coordinates[i],
				coordinates[(i + 1) % num_points]
			]
			(offset_x, offset_y) = calculate_offset(points, offset)
		except ZeroDivisionError:
			direction_is_back = True
			if set([
					coordinates[i].x,
					coordinates[i].y,
					coordinates[(i + 1) % num_points].x,
					coordinates[(i + 1) % num_points].y
				]) == 3:
				direction_is_back = False
			for point_offset in range(2, num_points):
				if direction_is_back:
					points = [
						coordinates[i - point_offset],
						coordinates[i],
						coordinates[(i + 1) % num_points]
					]
				else:
					points = [
						coordinates[i - 1],
						coordinates[i],
						coordinates[(i + point_offset) % num_points]
					]
				try:
					(offset_x, offset_y) = calculate_offset(points, offset)
					break
				except ZeroDivisionError:
					pass
		
		try:
			offset_points.append((offset_x, offset_y))
		except NameError:
			print("Couldn't find offset")
			offset_points.append((0, 0))

	return offset_points


def outline_glyph(glyph, offset_distance):
	for contour in glyph:
		offset = get_simple_offsets(contour, offset_distance)
		for p, point in enumerate(contour):
			x, y = offset[p]
			point.x = int(x)
			point.y = int(y)


