import numpy as np
from fontTools.misc.bezierTools import splitCubicAtT, lineLineIntersections
import numpy as np
from math import sqrt

def bezier_extrema(P0, P1, P2, P3):
	P0x, P0y = P0
	P1x, P1y = P1
	P2x, P2y = P2
	P3x, P3y = P3

	ax = -3*P0x + 9*P1x - 9*P2x + 3*P3x
	bx = 6*P0x - 12*P1x + 6*P2x
	cx = -3*P0x + 3*P1x

	ay = -3*P0y + 9*P1y - 9*P2y + 3*P3y
	by = 6*P0y - 12*P1y + 6*P2y
	cy = -3*P0y + 3*P1y

	extrema_x = np.roots([ax, bx, cx])
	extrema_y = np.roots([ay, by, cy])

	valid_t_x = [t.real for t in extrema_x if t.imag == 0 and 0 <= t.real <= 1]
	valid_t_y = [t.real for t in extrema_y if t.imag == 0 and 0 <= t.real <= 1]

	times = sorted(set(filter(lambda x: 0 < round(x, 10) < 1, valid_t_x + valid_t_y)))
	
	return times

def distance_between_points(p1, p2):
	return sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)

def extend_handle(point, target_point, distance=10):
	"""Extend a zero-length handle in the direction of the tangent."""
	vector_x = target_point[0] - point[0]
	vector_y = target_point[1] - point[1]
	length = sqrt(vector_x ** 2 + vector_y ** 2)
	
	# Normalize vector
	if length == 0:
		return point  # Skip if the points are the same
	
	vector_x /= length
	vector_y /= length
	
	# Extend handle in the direction of the vector (tangent)
	return [point[0] + vector_x * distance, point[1] + vector_y * distance]

class NormalizingPen:
	def __init__(self, other_pen, zero_handles_distance_fix=10):
		self.last_point = None
		self.other_pen = other_pen
		self.zero_handles_distance_fix = zero_handles_distance_fix
		
	def moveTo(self, point):
		self.last_point = point
		self.other_pen.moveTo(point)
	
	def lineTo(self, point):
		self.last_point = point
		self.other_pen.lineTo(point)
		
	def curveTo(self, *points):
		points = list(points)
		extrema = bezier_extrema(self.last_point, *points)

		try:
			handle_intersections = lineLineIntersections(self.last_point, points[0], *points[1:])
		except ZeroDivisionError:
			handle_intersections = []
		
		if self.last_point == points[0]:
			points[0] = extend_handle(self.last_point, points[1], self.zero_handles_distance_fix)

		if points[1] == points[2]:
			points[1] = extend_handle(points[2], points[0], self.zero_handles_distance_fix)

		if extrema:
			splits = splitCubicAtT(self.last_point, *points, *extrema)
			for split in splits:
				rounded_points = list(map(lambda point:(round(point[0]),round(point[1])), split[1:]))                
				self.other_pen.curveTo(*rounded_points)
		elif handle_intersections and any([-.1 <= intersection.t1 <= 1.1 and -.1 <= intersection.t2 <= 1.1 for intersection in handle_intersections]):
			splits = splitCubicAtT(self.last_point, *points, .5)
			for split in splits:
				rounded_points = list(map(lambda point:(round(point[0]),round(point[1])), split[1:]))                
				self.other_pen.curveTo(*rounded_points)
		else:
			self.other_pen.curveTo(*points)

		self.last_point = points[-1]

	def qCurveTo(self, *points):
		self.other_pen.qCurveTo(*points)
		self.last_point = points[-1]
		
	def closePath(self):
		self.other_pen.closePath()
   
