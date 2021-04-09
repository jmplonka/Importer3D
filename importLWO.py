# -*- coding: utf8 -*-

__title__   = "Import LightWave Objects"
__author__  = "Ken Nign (Ken9), Jens M. Plonka (jmplonka)"
__url__     = "https://www.github.com/jmplonka/Importer3D"
'''
Imports a LWO file.
http://static.lightwave3d.com/sdk/11-6/html/filefmts/lwo2.html
'''

# Copyright (c) Ken Nign 2010
# ken@virginpi.com
#
# Loads a LightWave .lwo object file.
#
# Notes:
# NGons, polygons with more than 4 points are supported, but are
# added (as triangles) after the vertex maps have been applied.
#
# History:
# 1.4 (jmplonka) ported to FreeCAD
#
# 1.3 (Ken9) Fixed CC Edge Weight loading.
#
# 1.2 (Ken9) Added Absolute Morph and CC Edge Weight support.
#     Made edge creation safer.
# 1.0 (Ken9) First Release

import os, chunk, traceback, FreeCAD, importUtils, Part
from importUtils import getBytes, getShort, getShorts, getFloat, getFloats, newObject, newGroup, setEndianess, BIG_ENDIAN
from itertools import groupby
from triangulate import getTriangles
from struct import Struct, unpack

UNPACK_NAME  = Struct("4s").unpack_from
UNPACK_LAYER = Struct(">HH").unpack_from

V = FreeCAD.Vector
class Layer(object):
	def __init__(self):
		self.name      = ""
		self.index     = -1
		self.parentIdx = None
		self.pivot     = [0, 0, 0]
		self.pols      = []
		self.pnts      = []
		self.surf_tags = {}
		self.subds     = []

class Material(object):
	def __init__(self):
		self.name   = "Default"
		self.colr   = (1.0, 1.0, 1.0)
		self.diff   = 1.0   # Diffuse
		self.lumi   = 0.0   # Luminosity
		self.spec   = 0.0   # Specular
		self.refl   = 0.0   # Reflectivity
		self.rblr   = 0.0   # Reflection Bluring
		self.tran   = 0.0   # Transparency (the opposite of Blender's Alpha value)
		self.rind   = 1.0   # RT Transparency IOR
		self.tblr   = 0.0   # Refraction Bluring
		self.trnl   = 0.0   # Translucency
		self.glos   = 0.4   # Glossiness
		self.shrp   = 0.0   # Diffuse Sharpness
		self.smooth = False  # Surface Smoothing

def read(doc, filename):
	'''
	Read the LWO file, hand off to version specific function.
	'''
	file = open(filename, 'rb')

	try:
		setEndianess(BIG_ENDIAN)
		header, chunk_size, chunk_name = unpack(">4s1L4s", file.read(12))
		layers = {}
		surfs  = {}
		tags   = []
		# Gather the object data using the version specific handler.
		if chunk_name in (b'LWOB', b'LWLO'):
			FreeCAD.Console.PrintMessage("Importing LWO v1: %s\n" %(filename))
			readLwo1(file, filename, layers, surfs, tags)
		elif chunk_name == b'LWO2':
			FreeCAD.Console.PrintMessage("Importing LWO v2: %s\n" %(filename))
			readLwo2(file, filename, layers, surfs, tags)
		else:
			FreeCAD.Console.PrintError("Not a supported file type!")
			file.close()
			return

		file.close()

		# With the data gathered, build the object(s).
		buildObjects(doc, layers, surfs, tags)

		layers = None
		surfs.clear()
		tags = None

	except:
		FreeCAD.Console.PrintError(traceback.format_exc())
		file.close()
	return

def readLwo1(file, filename, layers, surfs, tags):
	'''
	Read version 1 file, LW < 6.
	'''
	last_pols_count = 0
	layer = None

	while True:
		try:
			rootchunk = chunk.Chunk(file)
		except EOFError:
			break

		if rootchunk.chunkname == b'SRFS':
			readTags(rootchunk.read(), tags)
		elif rootchunk.chunkname == b'LAYR':
			layer = readLayr1(rootchunk.read(), layers)
		elif rootchunk.chunkname == b'PNTS':
			if (layer is None):
				# LWOB files have no LAYR chunk to set this up.
				layer = Layer()
				layer.nam = "Layer 1"
				layer.index = len(layers)
				layers[layer.index] = layer
			readPoints(rootchunk.read(), layer)
		elif rootchunk.chunkname == b'POLS':
			last_pols_count = readPols1(rootchunk.read(), layer)
		elif rootchunk.chunkname == b'PCHS':
			last_pols_count = readPols1(rootchunk.read(), layer)
			layer.has_subds = True
		elif rootchunk.chunkname == b'PTAG':
			tag_type, = UNPACK_NAME(rootchunk.read(4))
			if tag_type == b'SURF':
				readSurfTags(rootchunk.read(), layer, last_pols_count)
			else:
				rootchunk.skip()
		elif rootchunk.chunkname == b'SURF':
			readSurf1(rootchunk.read(), surfs)
		else:
			rootchunk.skip()

def readLwo2(file, filename, layers, surfs, tags):
	'''
	Read version 2 file, LW 6+.
	'''
	last_pols_count = 0
	layer = None

	while True:
		try:
			rootchunk = chunk.Chunk(file)
		except EOFError:
			break

		if rootchunk.chunkname == b'TAGS':
			readTags(rootchunk.read(), tags)
		elif rootchunk.chunkname == b'BBOX':
			rootchunk.skip()
		elif rootchunk.chunkname == b'LAYR':
			layer = readLayr2(rootchunk.read(), layers)
		elif rootchunk.chunkname == b'PNTS':
			readPoints(rootchunk.read(), layer)
		elif rootchunk.chunkname == b'POLS':
			sub_type = rootchunk.read(4)
			# PTCH is LW's Subpatches, SUBD is CatmullClark.
			if (sub_type in (b'FACE', b'PTCH', b'SUBD')):
				last_pols_count = readPols2(rootchunk.read(), layer)
				if sub_type == b'FACE':
					layer.has_subds = True
				rootchunk.skip()
		elif rootchunk.chunkname == b'PTAG':
			sub_type, = UNPACK_NAME(rootchunk.read(4))
			if sub_type == b'SURF':
				readSurfTags(rootchunk.read(), layer, last_pols_count)
			else:
				rootchunk.skip()
		elif rootchunk.chunkname == b'SURF':
			readSurf2(rootchunk.read(), surfs)
		else:
			rootchunk.skip()

def readString(raw_name):
	'''
	Parse a zero-padded string.
	'''
	i = raw_name.find(b'\0')
	name_len = i + 1
	if name_len % 2 == 1:   # Test for oddness.
		name_len += 1

	name = ""
	if i > 0:
		# Some plugins put non-text strings in the tags chunk.
		name = raw_name[0:i].decode("utf-8", "ignore")

	return name, name_len

def readVX(pointdata):
	'''
	Read a variable-length index.
	'''
	if pointdata[0] != 255:
		return pointdata[0] * 256 + pointdata[1], 2
	return pointdata[1]*65536 + pointdata[2]*256 + pointdata[3], 4

def readTags(tag_bytes, objTags):
	'''
	Read the object's Tags chunk.
	'''
	offset    = 0
	chunk_len = len(tag_bytes)

	while offset < chunk_len:
		tag, tag_len = readString(tag_bytes[offset:])
		offset += tag_len
		objTags.append(tag)

def readLayr1(layr_bytes, layers):
	'''
	Read the object's layer data.
	'''
	layer = Layer()
	layer.index, flags = UNPACK_LAYER(layr_bytes[0:4])
#	FreeCAD.Console.PrintMessage("Reading Object Layer %d:\n" %(layer.index))

	offset = 4
	layr_name, name_len = readString(layr_bytes[offset:])
	offset += name_len

	if name_len > 2 and layr_name != 'noname':
		layer.name = layr_name
	else:
		layer.name = "Layer %d" % layer.index

	layers[layer.index] = layer
	return layer

def readLayr2(layr_bytes, layers):
	'''
	Read the object's layer data.
	'''
	layer = Layer()
	layer.index, flags = UNPACK_LAYER(layr_bytes[0:4])
#	FreeCAD.Console.PrintMessage("Reading Object Layer %d:\n" %(layer.index))

	offset = 4
	pivot, offset = getFloats(layr_bytes, offset, 3)
	layer.pivot = (pivot[0], pivot[1], pivot[2])
	layr_name, name_len = readString(layr_bytes[offset:])
	offset += name_len

	if name_len > 2 and layr_name != 'noname':
		layer.name = layr_name
	else:
		layer.name = "Layer %d" % layer.index

	if len(layr_bytes) == offset+2:
		parentIdx, offset = getShort(layr_bytes, offset)
		parent = layers.get(parentIdx)
		parent.subds.append(layer)

	layers[layer.index] = layer
	return layer

def readPoints(pnt_bytes, layer):
	'''
	Read the layer's points.
	'''
#	FreeCAD.Console.PrintMessage("  Reading Layer Points\n")
	offset = 0
	chunk_len = len(pnt_bytes)

	while offset < chunk_len:
		pnts, offset = getFloats(pnt_bytes, offset, 3)
		# Re-order the points so that the mesh has the right pitch,
		# the pivot already has the correct order.
		pnts = [pnts[0] - layer.pivot[0],\
			   pnts[2] - layer.pivot[1],\
			   pnts[1] - layer.pivot[2]]
		layer.pnts.append(pnts)

def readPols1(pols, layer):
	'''
	Read the polygons, each one is just a list of point indexes.
	But it also includes the surface index (sid).
	'''
#	FreeCAD.Console.PrintMessage("  Reading Layer Polygons\n")
	pol_bytes = bytearray(pols)
	offset = 0
	chunk_len = len(pol_bytes)
	old_pols_count = len(layer.pols)
	poly = 0

	while offset < chunk_len:
		pnts_count, offset = getShort(pol_bytes, offset)
		all_face_pnts, offset = getShorts(pol_bytes, offset, pnts_count)
		layer.pols.append(all_face_pnts)
		sid, offset = getShort(pol_bytes, offset)
		sid = abs(sid) - 1
		if sid not in layer.surf_tags:
			layer.surf_tags[sid] = []
		layer.surf_tags[sid].append(poly)
		poly += 1

	return len(layer.pols) - old_pols_count

def readPols2(pols, layer):
	'''
	Read the layer's polygons, each one is just a list of point indexes.
	'''
#	FreeCAD.Console.PrintMessage("  Reading Layer Polygons\n")
	offset = 0
	pol_bytes = bytearray(pols)
	chunk_len = len(pol_bytes)
	old_pols_count = len(layer.pols)

	while offset < chunk_len:
		pnts_count, offset = getShort(pol_bytes, offset)
		all_face_pnts = []
		for j in range(pnts_count):
			face_pnt, data_size = readVX(pol_bytes[offset:offset+4])
			offset += data_size
			all_face_pnts.append(face_pnt)

		layer.pols.append(all_face_pnts)

	return len(layer.pols) - old_pols_count

def readSurfTags(tags, layer, last_pols_count):
	'''
	Read the list of PolyIDs and tag indexes.
	'''
#	FreeCAD.Console.PrintMessage("  Reading Layer Surface Assignments\n")
	offset = 0
	tag_bytes = bytearray(tags)
	chunk_len = len(tag_bytes)
	# Read in the PolyID/Surface Index pairs.
	abs_pid = len(layer.pols) - last_pols_count
	while offset < chunk_len:
		pid, pid_len = readVX(tag_bytes[offset:offset+4])
		offset += pid_len
		sid, offset = getShort(tag_bytes, offset)
		if sid not in layer.surf_tags:
			layer.surf_tags[sid] = []
		layer.surf_tags[sid].append(pid + abs_pid)

def readSurf1(surf_bytes, objMaterials):
	'''
	Read the object's surface data.
	'''
#	if len(objMaterials) == 0:
#		FreeCAD.Console.PrintMessage("Reading Object Surfaces\n")

	surf = Material()
	name, name_len = readString(surf_bytes)
	if len(name) != 0:
		surf.name = name

	offset = name_len
	chunk_len = len(surf_bytes)
	while offset < chunk_len:
		subchunk_name, = UNPACK_NAME(surf_bytes[offset:offset+4])
		offset += 4
		subchunk_len, offset = getShort(surf_bytes, offset)

		# Now test which subchunk it is.
		if subchunk_name == b'COLR':
			color, dummy= getBytes(surf_bytes, offset, 4)
			surf.colr = (color[0] / 255.0, color[1] / 255.0, color[2] / 255.0)
		elif subchunk_name == b'DIFF':
			surf.diff, dummy = getShort(surf_bytes, offset)
			surf.diff /= 256.0	# Yes, 256 not 255.
		elif subchunk_name == b'LUMI':
			surf.lumi, dummy = getShort(surf_bytes, offset)
			surf.lumi /= 256.0
		elif subchunk_name == b'SPEC':
			surf.spec, dummy = getShort(surf_bytes, offset)
			surf.spec /= 256.0
		elif subchunk_name == b'REFL':
			surf.refl, dummy = getShort(surf_bytes, offset)
			surf.refl /= 256.0
		elif subchunk_name == b'TRAN':
			surf.tran, dummy = getShort(surf_bytes, offset)
			surf.tran /= 256.0
		elif subchunk_name == b'RIND':
			surf.rind, dummy = getShort(surf_bytes, offset)
		elif subchunk_name == b'GLOS':
			surf.glos, dummy = getShort(surf_bytes, offset)
		elif subchunk_name == b'SMAN':
			s_angle, dummy = getFloat(surf_bytes, offset)
			if s_angle > 0.0:
				surf.smooth = True
		# skip remaining bytes of sub-chunk...
		offset += subchunk_len

	objMaterials[surf.name] = surf

def readSurf2(surf_bytes, objMaterials):
	'''
	Read the object's surface data.
	'''
	surf = Material()
	name, name_len = readString(surf_bytes)
	if len(name) != 0:
		surf.name = name

	# We have to read this, but we won't use it...yet.
	s_name, s_name_len = readString(surf_bytes[name_len:])
	offset = name_len + s_name_len
	chunk_len = len(surf_bytes)
	while offset < chunk_len:
		subchunk_name, = UNPACK_NAME(surf_bytes[offset:offset+4])
		offset += 4
		subchunk_len, offset = getShort(surf_bytes, offset)

		# Now test which subchunk it is.
		if subchunk_name == b'COLR':
			c, dummy = getFloats(surf_bytes, offset, 3)
			surf.colr = tuple(c)
		elif subchunk_name == b'DIFF': surf.diff, dummy = getFloat(surf_bytes, offset)
		elif subchunk_name == b'LUMI': surf.lumi, dummy = getFloat(surf_bytes, offset)
		elif subchunk_name == b'SPEC': surf.spec, dummy = getFloat(surf_bytes, offset)
		elif subchunk_name == b'REFL': surf.refl, dummy = getFloat(surf_bytes, offset)
		elif subchunk_name == b'TRAN': surf.tran, dummy = getFloat(surf_bytes, offset)
		elif subchunk_name == b'RIND': surf.rind, dummy = getFloat(surf_bytes, offset)
		elif subchunk_name == b'GLOS': surf.glos, dummy = getFloat(surf_bytes, offset)
		elif subchunk_name == b'RBLR': surf.rblr, dummy = getFloat(surf_bytes, offset)
		elif subchunk_name == b'TBLR': surf.tblr, dummy = getFloat(surf_bytes, offset)
		elif subchunk_name == b'TRNL': surf.trnl, dummy = getFloat(surf_bytes, offset)
		elif subchunk_name == b'SHRP': surf.shrp, dummy = getFloat(surf_bytes, offset)
		elif subchunk_name == b'SMAN':
			s_angle, offset = getFloat(surf_bytes, offset)
			if s_angle > 0.0: surf.smooth = True

		offset += subchunk_len

	objMaterials[surf.name] = surf

def buildObject(doc, parent, layer, objMaterials, objTags):
	FreeCAD.Console.PrintMessage("Building mesh '%s'...\n" %(layer.name))
	data = []
	mfacets = []
	if (layer.pols):
		for pol in layer.pols:
			ngon = [layer.pnts[idx] for idx in pol]
			points = [V(k) for k in ngon]
			points.append(points[0])
			if len(ngon) > 2:
				wire = Part.makePolygon(points)
				plane = wire.findPlane(0.00001)
				points2 =  [plane.projectPoint(p) for p in points]
				wire = Part.makePolygon(points2)
				try:
					face = Part.Face(wire)
					tris = face.tessellate(0.1)
					for tri in tris[1]:
						data.append([tris[0][i] for i in tri])
				except Exception as e:
					Part.show(wire)
					FreeCAD.Console.PrintWarning("   skipping polygon (%s): %s\n"%(e, ngon))

	me = newObject(doc, layer.name, data)
	me.Placement.Base = FreeCAD.Vector(layer.pivot)

	# Create the Material Slots and assign the MatIndex to the correct faces.
	for surf_key in layer.surf_tags:
		if objTags[surf_key] in objMaterials:
			material = objMaterials[objTags[surf_key]]
#			me.ViewObject.ShapeMaterial.AmbientColor  =
			me.ViewObject.ShapeMaterial.DiffuseColor  = material.colr
#			me.ViewObject.ShapeMaterial.EmissiveColor =
#			me.ViewObject.ShapeMaterial.SpecularColor =
			me.ViewObject.ShapeMaterial.Shininess     = material.lumi
			me.ViewObject.ShapeMaterial.Transparency  = material.trnl

	# Clear out the dictionaries for this layer.
	layer.surf_tags.clear()
	if (len(layer.subds) == 0):
		if (parent is not None):
			parent.Shapes.append(me)
	else:
		group = newGroup(doc, layer.name)
		group.Shapes.append(me)
		if (parent is not None):
			parent.Shapes.append(group)
		for child in layer.subds:
			buildObject(doc, group, child, objMaterials, objTags)

def buildObjects(doc, layers, objMaterials, objTags):
	'''
	Using the gathered data, create the objects.
	'''
	for key,layer in layers.items():
		if (layer.parentIdx is None):
			buildObject(doc, None, layer, objMaterials, objTags)
	FreeCAD.Console.PrintMessage("Done Importing LWO File\n")
