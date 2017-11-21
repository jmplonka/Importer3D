from itertools import chain
from math      import fabs
import numpy   as np

# Ported from https://github.com/bjorkegeek/polytri

def loopedPairs(iterable):
	'''
	list(loopedPairs([1,2,3])) => [(1, 2), (2, 3), (3, 1)]
	'''
	iterable = iter(iterable)
	first = last = next(iterable)
	for x in iterable:
		yield last, x
		last = x
	yield (last, first)

def nearlyZero(v, rTol = 1e-6, aTol = 1e-9):
	'''
	nearlyZero(0)                               => True
	nearlyZero(.1)                              => False
	nearlyZero(1E-10)                           => True
	nearlyZero(np.array([0, 0, 0]))             => True
	nearlyZero(np.array([1E-10, 1E-10, 1E-10])) => True
	nearlyZero(np.array([1E-10, 1E-10, 7]))     => False
	'''
	if isinstance(v, (float, int)):
		return fabs(v) > rTol
	return np.allclose(v, np.zeros(np.shape(v), np.float32), rTol, aTol)

def calculateNormal(polygon):
	'''
	Returns polygon normal vector for 3d polygon
	'''
	n = np.array([0, 0, 0], np.float32)
	for p1, p2 in loopedPairs(polygon):
		m = np.subtract(p2, p1)
		p = np.add(p2, p1)
		n[0] += m[1] * p[2]
		n[1] += m[2] * p[0]
		n[2] += m[0] * p[1]
	if nearlyZero(n):
		raise ValueError("No normal found")
	else:
		return n

def loppedSlice(seq, start, count):
	'''
	list(loppedSlice([1,2,3],0,3)) => [1, 2, 3]
	list(loppedSlice([1,2,3],1,2)) => [3, 1]
	'''
	l = len(seq)
	for i in range(start, start + count):
		yield seq[i % l]

def loppedSliceInv(seq, start, count):
	'''
	list(loppedSliceInv([1,2,3,4],0,3)) => [4]
	list(loppedSliceInv([1,2,3,4],1,3)) => [1]
	list(loppedSliceInv([1,2,3,4],2,3)) => [2]
	list(loppedSliceInv([1,2,3,4],3,3)) => [3]
	'''
	if start + count > len(seq):
		return seq[start + count - len(seq): start]
	else:
		return chain(seq[:start], seq[start + count:])

def anyPointInTriangle(triangle, points):
	a, b, c = triangle
	s = b - a
	t = c - a

	stk = [s, t, np.cross(s, t)]
	mtx = np.linalg.inv(np.vstack(stk).transpose())[:2]

	for p in points:
		ps, pt = np.dot(mtx, p - a)
		if ps >= 0 and pt >= 0 and ps + pt <= 1:
			return True
	return False

def getTriangles(ngon):
	'''
	Converts a polygon to a set of triangles that cover the same area.
	  * Convex and non-convex polygons are supported.
	  * Clockwise and counter-clockwise winding supported.
	  * Polygon vertices must all be within a single plane
	  * Inverted polygons are NOT supported
	  * Polygons with holes (multi-wires) are NOT supported.

	Args:
	    ngon: A sequence of vertices making up the singe wire polygon, with each vertex
		      described as a 3D point.
			  The ngon is implicitly closed: a polygon with N sides should have N vertices.
	Returns:
		a generator of triangles, each specified in the same format as the input polygon
	'''
	polygon = [np.array(x, np.float32) for x in ngon]

	normal = calculateNormal(polygon)
	i = 0
	while len(polygon) > 2:
		if i >= len(polygon):
			raise ValueError("Triangulation failed")
		(a, b, c) = loppedSlice(polygon, i, 3)
		if ((a == b).all() or (b == c).all()):
			# Duplicate vertex, just skip
			del polygon[(i + 1) % len(polygon)]
		else:
			x = np.cross(c - b, b - a)
			dot = np.dot(normal, x)
			yld = False
			if dot > 1E-12:
				triangle = (a, b, c)
				if not anyPointInTriangle(triangle, loppedSliceInv(polygon, i, 3)):
					del polygon[(i + 1) % len(polygon)]
					yield triangle
					i = 0
					yld = True
			if not yld:
				i += 1
