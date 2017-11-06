# -*- coding: utf8 -*-

'''
ref. http://paulbourke.net/dataformats/3ds/
'''
__title__="FreeCAD Autodesk 3DS Max importer"
__author__ = "Jens M. Plonka"
__url__ = "https:#www.github.com/jmplonka/Import3DS"

import os
import traceback
import FreeCAD
import re
import Mesh
import sys
import numpy
from struct  import unpack
from math    import degrees, sqrt, sin, cos

INVALID_NAME = re.compile('^[0-9].*')

VERSION                             = 0x0002
COLOR                               = 0x0010
RGB1                                = 0x0011
RGB2                                = 0x0012
INT_PERCENT                         = 0x0030
SCALE                               = 0x0100
AMBIENT_COLOR                       = 0x2100
EDITOR                              = 0x3D3D
MESH_VERSION                        = 0x3D3E
NAMED_OBJECT                        = 0x4000
TRI_MESH_OBJ                        = 0x4100 # Represent a mesh object for shapes.
TRI_VERTEXL                         = 0x4110 # The vertex list from which vertices of a face array will be used.
TRI_VERTEXOPTIONS                   = 0x4111
FACES_DESCRIPTION                   = 0x4120
TRI_MATERIAL                        = 0x4130
TRI_MAPPINGCOORS                    = 0x4140
TRI_SMOOTH                          = 0x4150
TRI_PLACEMENT                       = 0x4160
TRI_VISIBLE                         = 0x4165
TRI_MAPPINGSTANDARD                 = 0x4170
OBJ_LIGHT                           = 0x4600
LIT_SPOT                            = 0x4610
LIT_OFF                             = 0x4620
LIT_UNKNWN01                        = 0x465A
ATTENUATED                          = 0x4625
RANGE_START                         = 0x4659
RANGE_END                           = 0x465A
MULTIPLIER                          = 0x465B
CAMERA                              = 0x4700
MAIN                                = 0x4D4D
MAT_NAME                            = 0xA000
MAT_AMBIENT_COLOR                   = 0xA010
MAT_DIFFUSE_COLOR                   = 0xA020
MAT_SPECULAR_COLOR                  = 0xA030
MAT_SHININESS_PERCENT               = 0xA040
MAT_SHININESS_STRENGTH_PERCENT      = 0xA041
MAT_TRANSPARENCY_PERCENTAGE         = 0xA050
MAT_TRANSPARENCY_FALLOFF_PERCENTAGE = 0xA052
MAT_REFLECTION_BLUR_PERCENTAGE      = 0xA053
TWO_SIDED                           = 0xA081
MAT_SELF_ILLUM_PERCENTAGE           = 0xA084
MAT_WIRESIZE                        = 0xA087
MAT_XPFALLIN                        = 0xA08A
MAT_PHONGSOFT                       = 0xA08C
RENDER_TYPE                         = 0xA100
MAT_DIFFUSE_MAP                     = 0xA200
MAT_OPACITY_MAP                     = 0xA210
MAT_REFLECTION_MAP                  = 0xA220
MAT_BUMP_MAP                        = 0xA230
MAT_BUMP_PERCENT                    = 0xA252
MAT_TEXTURE_NAME                    = 0xA300
MAT_SHININESS_MAP                   = 0xA33C
MAT_SELF_ILLUM_MAP                  = 0xA33D
MAPPING                             = 0xA351
MAT_TEXTURE_BLUR_MAP                = 0xA353
V_SCALE                             = 0xA354
U_SCALE                             = 0xA356
V_OFFSET                            = 0xA358
U_OFFSET                            = 0xA35A
MAT_ANGLE_MAP                       = 0xA35C
MATERIAL                            = 0xAFFF
KEYFRAMER                           = 0xB000
AMBIENT_LIGHT_INFO                  = 0xB001
MESH_INFO                           = 0xB002
CAMERA_INFO                         = 0xB003
CAMERA_TARGET_INFO                  = 0xB004
OMNI_LIGHT_INFO                     = 0xB005
SPOT_LIGHT_TARGET_INFO              = 0xB006
SPOT_LIGHT_INFO                     = 0xB007
FRAMES                              = 0xB008
CURRENT_FRAME                       = 0xB009
MESH_ANIM                           = 0xB00A
HIERARCHY                           = 0xB010
MESH_NAME                           = 0xB011
TRK_PIVOT                           = 0xB013
BOUNDING_BOX                        = 0xB014
TRK_POSITION                        = 0xB020
TRK_ROTATION                        = 0xB021
TRK_SCALE                           = 0xB022
HIERARCHY_INFO                      = 0xB030
DESC_MAP = { \
	AMBIENT_COLOR                       : 'Ambient Color', \
	AMBIENT_LIGHT_INFO                  : 'Ambient-Light-Info', \
	ATTENUATED                          : 'Attentuated', \
	BOUNDING_BOX                        : 'Bounding-Box', \
	CAMERA                              : 'Camera', \
	CAMERA_INFO                         : 'Camera-Info', \
	CAMERA_TARGET_INFO                  : 'Camera-Target-Info', \
	COLOR                               : 'Color', \
	CURRENT_FRAME                       : 'Current-Frame', \
	EDITOR                              : 'Editor', \
	FACES_DESCRIPTION                   : 'Faces Description', \
	FRAMES                              : 'Frames', \
	HIERARCHY                           : 'Hierarchy', \
	HIERARCHY_INFO                      : 'Hierarchy-Info', \
	INT_PERCENT                         : 'Int-Percentage', \
	KEYFRAMER                           : 'Keyframer', \
	LIT_OFF                             : 'Off-Light', \
	LIT_SPOT                            : 'Spot-Light', \
	LIT_UNKNWN01                        : 'Unknown-Light', \
	MAIN                                : 'Main 3DS', \
	MAPPING                             : 'Mapping', \
	MATERIAL                            : 'Material', \
	MAT_AMBIENT_COLOR                   : 'Material Ambient Color', \
	MAT_ANGLE_MAP                       : 'Material Angle Map', \
	MAT_BUMP_MAP                        : 'Material Bump Map', \
	MAT_BUMP_PERCENT                    : 'Material Bump Percentage', \
	MAT_DIFFUSE_COLOR                   : 'Material Diffuse Color', \
	MAT_DIFFUSE_MAP                     : 'Material Diffuse Map', \
	MAT_NAME                            : 'Material Name', \
	MAT_OPACITY_MAP                     : 'Material Opacity Map', \
	MAT_PHONGSOFT                       : 'Material Phong soft', \
	MAT_REFLECTION_BLUR_PERCENTAGE      : 'Material Reflection', \
	MAT_REFLECTION_MAP                  : 'Material Reflection Map', \
	MAT_SELF_ILLUM_PERCENTAGE           : 'Material Emissive', \
	MAT_SELF_ILLUM_MAP                  : 'Material Emissive Map', \
	MAT_SHININESS_PERCENT               : 'Material Shininess', \
	MAT_SHININESS_STRENGTH_PERCENT      : 'Material Shininess strength', \
	MAT_SHININESS_MAP                   : 'Material Shininess Map', \
	MAT_SPECULAR_COLOR                  : 'Material Specular Color', \
	MAT_TEXTURE_BLUR_MAP                : 'Material Texture Blur Map', \
	MAT_TEXTURE_NAME                    : 'Material Texture', \
	MAT_TRANSPARENCY_FALLOFF_PERCENTAGE : 'Material Transparency falloff', \
	MAT_TRANSPARENCY_PERCENTAGE         : 'Material Transparency', \
	MAT_WIRESIZE                        : 'Material Wire Size', \
	MAT_XPFALLIN                        : 'Material XP fallin', \
	MESH_ANIM                           : 'Mesh-Animation', \
	MESH_INFO                           : 'Mesh-Info', \
	MESH_NAME                           : 'Mesh-Name', \
	MESH_VERSION                        : 'Mesh-Version', \
	MULTIPLIER                          : 'Multiplier', \
	NAMED_OBJECT                        : 'Named-Object', \
	OBJ_LIGHT                           : 'Light', \
	TRI_MESH_OBJ                        : 'Triang. Mesh', \
	OMNI_LIGHT_INFO                     : 'Omni-Light-Info', \
	RANGE_END                           : 'Range stop', \
	RANGE_START                         : 'Range start', \
	RENDER_TYPE                         : 'Render Type', \
	RGB1                                : 'RGB1', \
	RGB2                                : 'RGB2', \
	SCALE                               : 'Scale', \
	SPOT_LIGHT_INFO                     : 'Spot-Light-Info', \
	SPOT_LIGHT_TARGET_INFO              : 'Target-Spot-Light-Info', \
	TRK_PIVOT                           : 'Trk. Pivot', \
	TRK_POSITION                        : 'Trk. Position', \
	TRK_ROTATION                        : 'Trk. Rotation', \
	TRK_SCALE                           : 'Trk. Scale', \
	TRI_PLACEMENT                       : 'Triang. Placement', \
	TRI_MAPPINGCOORS                    : 'Triang. Mapping-Coordinates', \
	TRI_MAPPINGSTANDARD                 : 'Triang. Mappmg (def.)', \
	TRI_MATERIAL                        : 'Triang. Material', \
	TRI_SMOOTH                          : 'Triang. Smoothing', \
	TRI_VERTEXL                         : 'Triang. Vertices', \
	TRI_VERTEXOPTIONS                   : 'Triang. Vertice Options', \
	TRI_VISIBLE                         : 'Triang. Visible', \
	TWO_SIDED                           : 'Two Sided', \
	U_OFFSET                            : 'U-Offset', \
	U_SCALE                             : 'U-Scale', \
	VERSION                             : 'Version', \
	V_OFFSET                            : 'V-Offset', \
	V_SCALE                             : 'V-Scale', \
}

def getChunkName(chunk):
	id = chunk.id
	if (chunk.name):
		return "[%s] '%s'" %(DESC_MAP.get(id, "%04X" %id), chunk.name)
	return "[%s]" % DESC_MAP.get(id, "%04X" %id)

def getData(chunk, id):
	subChunk = chunk.getSubChunk(id)
	if (subChunk): return subChunk.data
	return None

def getSplineTerms(accelerationData, chopper):
	bits = accelerationData
	spline = []
	for i in range(5):
		bits >>= i
		if ((bits & 1) == 1):
			x = chopper.getFloat()

def newObject(doc, className, name):
	if (INVALID_NAME.match(name)):
		obj = doc.addObject(className, '_' + name.encode('utf8'))
	else:
		obj = doc.addObject(className, name.encode('utf8'))
	if (obj):
		obj.Label = name
	return obj

def createGroup(doc, name):
	if (doc):
		return newObject(doc, 'App::DocumentObjectGroup', name)
	return None

def _dotchain(first, *rest):
    matrix = first
    for next in rest:
        matrix = numpy.dot(matrix, next)
    return matrix

def createKeyMatrix(track, frame=0):
	mtx = numpy.identity(4, numpy.float32)

	pvt = track.getSubChunk(TRK_PIVOT)
	if (pvt is not None): mtx = numpy.dot(mtx, pvt.getMatrix()) # pivot has not frame correlation!

	rot = track.getSubChunk(TRK_ROTATION)
	if (rot is not None): mtx = numpy.dot(mtx, rot.getMatrix(frame))

	scl = track.getSubChunk(TRK_SCALE)
	if (scl is not None): mtx = numpy.dot(mtx, scl.getMatrix(frame))

	pos = track.getSubChunk(TRK_POSITION)
	if (pos is not None): mtx = numpy.dot(mtx, pos.getMatrix(frame))

	return mtx

def adjustPoint(pts, idx, mtx):
	return []

class AbstractChunk():
	def __init__(self, id, len):
		self.id          = id
		self.len         = len
		self.name        = None
		self.parent      = None
		self.data        = []
		self.subChunks   = {}
	def __str__(self): return "%s" % (getChunkName(self))

	def addSubChunk(self, subId, subChunk):
		if (subId not in self.subChunks):
			self.subChunks[subId] = []
		chunkStack = self.subChunks[subId]
		chunkStack.append(subChunk)
		subChunk.parent = self

	def getSubChunk(self, id):
		if (id in self.subChunks):
			chunkStack = self.subChunks[id]
			if (len(chunkStack) > 0):
				return chunkStack[len(chunkStack) - 1]
		return None

	def loadData(self, chopper): return #self.data = chopper.getChunkBytes()
	def initialize(self, chopper): return # Nothing to do here!

class PlacementChunk(AbstractChunk):
	def __init__(self, id, len): AbstractChunk.__init__(self, id, len)
	def __str__(self):
		u = self.data[0]
		v = self.data[1]
		n = self.data[2]
		return "%s: (%g,%g,%g,%g),(%g,%g,%g,%g),(%g,%g,%g,%g)" % (getChunkName(self) \
			, self.data[0x0], self.data[0x1], self.data[0x2], self.data[0x3] \
			, self.data[0x4], self.data[0x5], self.data[0x6], self.data[0x7] \
			, self.data[0x8], self.data[0x9], self.data[0xA], self.data[0xB])
	def loadData(self, chopper):
		a11 = chopper.getFloat()
		a21 = chopper.getFloat()
		a31 = chopper.getFloat()
		a12 = chopper.getFloat()
		a22 = chopper.getFloat()
		a32 = chopper.getFloat()
		a13 = chopper.getFloat()
		a23 = chopper.getFloat()
		a33 = chopper.getFloat()
		a14 = chopper.getFloat()
		a24 = chopper.getFloat()
		a34 = chopper.getFloat()
		self.data = (a11, a12, a13, a14, a21, a22, a23, a24, a31, a32, a33, a34)
	def getMatrix(self):
		return numpy.array([ \
			[self.data[0x0], self.data[0x1], self.data[0x2], self.data[0x3]], \
			[self.data[0x4], self.data[0x5], self.data[0x6], self.data[0x7]], \
			[self.data[0x8], self.data[0x9], self.data[0xA], self.data[0xB]], \
			[0, 0, 0, 1]], numpy.float32)

class BooleanChunk(AbstractChunk):
	def __init__(self, id, len): AbstractChunk.__init__(self, id, len)
	def __str__(self): return "%s: %s" % (getChunkName(self), self.data)
	def loadData(self, chopper): self.data = chopper.getChunkBytes()


class EditorChunk(AbstractChunk):
	def __init__(self, id, len): AbstractChunk.__init__(self, id, len)

class FacesDescriptionChunk(AbstractChunk):
	def __init__(self, id, len):
		AbstractChunk.__init__(self, id, len)

	def loadData(self, chopper):
		numFaces = chopper.getUnsignedShort()
		if (self.len >= 0xF6FBF): numFaces |= 0x10000
		self.data = []

		for i in range(numFaces):
			a = chopper.getUnsignedShort()
			b = chopper.getUnsignedShort()
			c = chopper.getUnsignedShort()
			d = chopper.getUnsignedShort()
			self.data.append([a, c, b, d])

class FacesMaterialChunk(AbstractChunk):
	def __init__(self, id, len): AbstractChunk.__init__(self, id, len)
	def loadData(self, chopper):
		self.name = chopper.getString()
		numFaces  = chopper.getUnsignedShort()
		self.data = []
		for i in range(numFaces):
			self.data.append(chopper.getUnsignedShort())

class FloatChunk(AbstractChunk):
	def __init__(self, id, len): AbstractChunk.__init__(self, id, len)
	def __str__(self): return "%s: %g" % (getChunkName(self), self.data)
	def loadData(self, chopper): self.data = chopper.getFloat()

class HierarchyChunk(AbstractChunk):
	def __init__(self, id, len): AbstractChunk.__init__(self, id, len)
	def __str__(self): return "%s: 0x%X, 0x%X, %d" % (getChunkName(self), self.data[0], self.data[1], self.data[2])
	def loadData(self, chopper):
		self.name = chopper.getString()
		flag1     = chopper.getUnsignedShort()
		flag2     = chopper.getUnsignedShort()
		parentId  = chopper.getShort()
		self.data = (flag1, flag2, parentId)
	def getParentId(self): return self.data[2]

class HierarchyInfoChunk(AbstractChunk):
	def __init__(self, id, len): AbstractChunk.__init__(self, id, len)
	def __str__(self): return "%s: %s" % (getChunkName(self), self.data)
	def loadData(self, chopper): self.data = chopper.getShort()

class IntChunk(AbstractChunk):
	def __init__(self, id, len): AbstractChunk.__init__(self, id, len)
	def __str__(self): return "%s: %g" % (getChunkName(self), self.data)
	def loadData(self, chopper): self.data = chopper.getInt()

class IntPercentChunk(AbstractChunk):
	def __init__(self, id, len): AbstractChunk.__init__(self, id, len)
	def __str__(self): return "%s: %s%%" % (getChunkName(self), self.data)
	def loadData(self, chopper): self.data = chopper.getShort() * 0.01

class MainChunk(AbstractChunk):
	def __init__(self, id, len): AbstractChunk.__init__(self, id, len)

class MaterialChunk(AbstractChunk):
	def __init__(self, id, len): AbstractChunk.__init__(self, id, len)
	def initialize(self, chopper):
		self.name = getData(self, MAT_NAME)
		ambient = getData(self, MAT_AMBIENT_COLOR)
		diffuse = getData(self, MAT_DIFFUSE_COLOR)
		specular = getData(self, MAT_SPECULAR_COLOR)
		shinines = getData(self, MAT_SHININESS_PERCENT)
		transparency = getData(self, MAT_TRANSPARENCY_PERCENTAGE)
		self.data = {}
		if (ambient): self.data['ambient'] = ambient
		if (diffuse): self.data['diffuse'] = diffuse
		if (specular): self.data['specular'] = specular
		if (shinines): self.data['shinines'] = shinines
		if (transparency): self.data['transparency'] = transparency
		chopper.materials[self.name] = self.data

class MeshInfoChunk(AbstractChunk):
	def __init__(self, id, len): AbstractChunk.__init__(self, id, len)
	def initialize(self, chopper):
		hi = self.getSubChunk(HIERARCHY_INFO) # build up tree!
		hrx = self.getSubChunk(HIERARCHY)
		FreeCAD.Console.PrintMessage("Adding '%s'\n" %(hrx.name))
		frm = getData(self.parent, CURRENT_FRAME)
		mtx = createKeyMatrix(self, frm)
		parent = chopper.keyMatrix.get(hrx.getParentId())
		if (parent is not None):
			prnMtx = parent.matrix
			if (prntMtx): mtx = mtx.dot(prnMtx)
		self.matrix = mtx
		chopper.keyMatrix[hi.data] = self
		nObj = chopper.namedObjectes.get(hrx.name)
		if (nObj):
			mObj = nObj.getSubChunk(TRI_MESH_OBJ)
			if (mObj):
				pts = getData(mObj, TRI_VERTEXL)          # the 3D-point coordinates         => Vertex3ListChunk
				dsc = mObj.getSubChunk(FACES_DESCRIPTION) # the 3D object faces              => FacesDescriptionChunk
				if (dsc):
					obj = newObject(chopper.tg, "Mesh::Feature", hrx.name)
					mat = dsc.getSubChunk(TRI_MATERIAL)

					plc = mObj.getSubChunk(TRI_PLACEMENT) # the 3D object faces              => PlacementChunk
					mshMtx = plc.getMatrix()
					mtx = numpy.dot(mshMtx, mtx)

					# translate the points according to the transformation matrix
					pt = numpy.ones((len(pts), 4), numpy.float32)
					pt[:,:3] = pts
					tpt = numpy.transpose(numpy.dot(mtx, numpy.transpose(pt)))

					data = []
					for idx in dsc.data:
						data.append([tpt[idx[0]], tpt[idx[1]], tpt[idx[2]]])

					obj.Mesh = Mesh.Mesh(data)
					obj.ViewObject.Lighting = "Two side"
					chopper.adjustMaterial(obj, mat)

class NamedObjectChunk(AbstractChunk):
	def __init__(self, id, len): AbstractChunk.__init__(self, id, len)
	def loadData(self, chopper): self.name = chopper.getString()
	def initialize(self, chopper): chopper.namedObjectes[self.name] = self

class NTriObjectChunk(AbstractChunk):
	def __init__(self, id, len): AbstractChunk.__init__(self, id, len)

class PercentageChunk(AbstractChunk):
	INT   = 0x30
	FLOAT = 0x31
	def __init__(self, id, len): AbstractChunk.__init__(self, id, len)
	def __str__(self): return "%s: %s%%" %(getChunkName(self), self.data)
	def loadData(self, chopper):
		percentageType = chopper.getUnsignedShort()
		percentageLength = chopper.getInt()

		if (percentageType == PercentageChunk.INT):
			self.data = chopper.getUnsignedShort() * 0.01
		elif (percentageType == PercentageChunk.FLOAT):
			self.percentage = chopper.getFloat() * 0.01

class PercentageIntChunk(AbstractChunk):
	def __init__(self, id, len): AbstractChunk.__init__(self, id, len)
	def __str__(self): return "%s: %s%%" %(getChunkName(self), self.data)
	def loadData(self, chopper): self.data = chopper.getUnsignedShort() * 0.01

class Rgb1Chunk(AbstractChunk):
	FLOAT_COLOR       = 0x0010
	BYTE_COLOR        = 0x0011
	BYTE_COLOR_GAMMA  = 0x0012
	FLOAT_COLOR_GAMMA = 0x0013
	def __init__(self, id, len): AbstractChunk.__init__(self, id, len)
	def __str__(self): return "%s: R=%g,G=%g,B=%g" %(getChunkName(self), self.data[0], self.data[1], self.data[2])
	def loadData(self, chopper):
		colorType = chopper.getUnsignedShort() # SubChunkId represents Color type.
		l = chopper.getInt()     # skip length.
		a = 1.0
		if (colorType == Rgb1Chunk.BYTE_COLOR):
			r = chopper.getUnsignedByte() / 255.0
			g = chopper.getUnsignedByte() / 255.0
			b = chopper.getUnsignedByte() / 255.0
		elif (colorType == Rgb1Chunk.BYTE_COLOR_GAMMA):
			r = chopper.getUnsignedByte() / 255.0
			g = chopper.getUnsignedByte() / 255.0
			b = chopper.getUnsignedByte() / 255.0
			a = chopper.getUnsignedByte() / 255.0
		elif (colorType == Rgb1Chunk.FLOAT_COLOR):
			r = chopper.getFloat()
			g = chopper.getFloat()
			b = chopper.getFloat()
		elif (colorType == Rgb1Chunk.FLOAT_COLOR_GAMMA):
			r = chopper.getFloat()
			g = chopper.getFloat()
			b = chopper.getFloat()
			a = chopper.getFloat()
		else:
			FreeCAD.PrintError("Only RGB colors are enabled! Color type = %X, len = %d" %(colorType, self.len))
			r = l / 32767.0
			g = chopper.getInt() / 32767.0
			b = chopper.getUnsignedShort() / 32767.0
		self.data = (r, g, b, a)

class Rgb2Chunk(AbstractChunk):
	def __init__(self, id, len): AbstractChunk.__init__(self, id, len)
	def __str__(self): return "%s: %s" % (getChunkName(self), self.data)
	def loadData(self, chopper):
		rgb = bytearray(chopper.getChunkBytes())
		self.data = (rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0)

class TrkPivotChunk(AbstractChunk):
	def __init__(self, id, len): AbstractChunk.__init__(self, id, len)
	def __str__(self): return "%s: (%g,%g,%g)" % (getChunkName(self), self.data[0], self.data[1], self.data[2])
	def loadData(self, chopper): self.data = chopper.getPoint3f()
	def getMatrix(self):
		mtx = numpy.identity(4, numpy.float32)
		mtx[0,3] = -self.data[0]
		mtx[1,3] = -self.data[1]
		mtx[2,3] = -self.data[2]
		return mtx

class TrkPositionChunk(AbstractChunk):
	USE_TENSION    = 0x01
	USE_CONTINUITY = 0x02
	USE_BIAS       = 0x04
	USE_EASE_TO    = 0x08
	USE_EASE_FROM  = 0x10

	def __init__(self, id, len): AbstractChunk.__init__(self, id, len)
	def __str__(self): return "%s: %s" % (getChunkName(self), self.data)
	def loadData(self, chopper):
		self.flags   = chopper.getUnsignedShort()
		self.unused1 = chopper.getInt()
		self.unused1 = chopper.getInt()
		numKeys = chopper.getInt()
		self.data    = []
		for i in range(numKeys):
			frm = chopper.getInt()
			flg = chopper.getUnsignedShort()
			tcb = {}
			if (flg & TrkPositionChunk.USE_TENSION):    tcb['tens']      = chopper.getFloat()
			if (flg & TrkPositionChunk.USE_CONTINUITY): tcb['cont']      = chopper.getFloat()
			if (flg & TrkPositionChunk.USE_BIAS):       tcb['bias']      = chopper.getFloat()
			if (flg & TrkPositionChunk.USE_EASE_TO):    tcb['ease_to']   = chopper.getFloat()
			if (flg & TrkPositionChunk.USE_EASE_FROM):  tcb['ease_from'] = chopper.getFloat()
			pnt = chopper.getPoint3f()
			self.data.append([frm, tcb, pnt])
	def getMatrix(self, frame = 0):
		mtx = numpy.identity(4,numpy.float32)
		pos = self.data[frame][2]
		mtx[0,3] = -pos[0]
		mtx[1,3] = -pos[1]
		mtx[2,3] = -pos[2]
		return mtx

class TrkRotationChunk(AbstractChunk):
	def __init__(self, id, len):
		AbstractChunk.__init__(self, id, len)
		self.flags = 0
	def __str__(self): return "%s: %X, %s" % (getChunkName(self), self.flags, self.data)
	def loadData(self, chopper):
		self.flags = chopper.getUnsignedShort()
		self.data = []
		unused1 = chopper.getInt()
		unused2 = chopper.getInt()
		numKeys = chopper.getInt()
		for i in range(numKeys):
			frm = chopper.getInt()
			acd = chopper.getUnsignedShort()
			spt = getSplineTerms(acd, chopper)
			ang = chopper.getFloat()
			pnt = chopper.getPoint3f()
			self.data.append([frm, acd, spt, ang, pnt])
	def getMatrix(self, frame = 0):
		mtx = numpy.identity(4,numpy.float32)
		rot = self.data[frame]
		angle = rot[3]
		if abs(angle) > 0.0001:
			v = numpy.array((rot[4][0], rot[4][1], rot[4][2]), numpy.float32)
			u = v / sqrt(numpy.dot(v, v))
			s = numpy.array(((  0  , -u[2],  u[1]),
							 ( u[2],   0  , -u[0]),
							 (-u[1],  u[0],   0  )), numpy.float32)
			p = numpy.outer(u, u)
			i = numpy.identity(3, numpy.float32)
			m = p + cos(angle)*(i-p) + sin(angle)*s
			mtx[0:3, 0:3] = m
		return mtx

class TrkScaleChunk(AbstractChunk):
	def __init__(self, id, len):
		AbstractChunk.__init__(self, id, len)
		self.flags = 0
	def __str__(self): return "%s: %X, %s" % (getChunkName(self), self.flags, self.data)
	def loadData(self, chopper):
		self.flags = chopper.getUnsignedShort()
		unused1 = chopper.getInt()
		unused2 = chopper.getInt()
		numKeys = chopper.getInt()
		self.data = []
		for i in range(numKeys):
			frm = chopper.getInt()
			acd = chopper.getUnsignedShort()
			pnt = chopper.getPoint3f()
			self.data.append([frm, acd, pnt])
	def getMatrix(self, frame = 0):
		mtx = numpy.identity(4,numpy.float32)
		scl = self.data[frame][2]
		mtx[0,0] = 1.0 / scl[0]
		mtx[1,1] = 1.0 / scl[1]
		mtx[2,2] = 1.0 / scl[2]
		return mtx

class SkipChunk(AbstractChunk):
	def __init__(self, id, len): AbstractChunk.__init__(self, id, len)
	def __str__(self): return "%s: 0x%04X, %d Bytes" % (getChunkName(self), self.id, self.len)
	def loadData(self, chopper): self.data = chopper.getChunkBytes()

class StringChunk(AbstractChunk):
	def __init__(self, id, len): AbstractChunk.__init__(self, id, len)
	def __str__(self): return "%s: '%s'" % (getChunkName(self), self.data)
	def loadData(self, chopper): self.data = chopper.getString()

class Vertex2ListChunk(AbstractChunk):
	def __init__(self, id, len): AbstractChunk.__init__(self, id, len)
	def loadData(self, chopper):
		count = (self.len - 2) / 8
		numVertices = chopper.getUnsignedShort()
		self.data = []
		for i in range(count): self.data.append(chopper.getPoint2f())

class Vertex3ListChunk(AbstractChunk):
	def __init__(self, id, len): AbstractChunk.__init__(self, id, len)
	def loadData(self, chopper):
		count = (self.len - 2) / 12
		numVertices = chopper.getUnsignedShort()
		self.data = []
		for i in range(count): self.data.append(chopper.getPoint3f())

class Importer:
	def __init__(self, doc, filename):
		self.constructors = {}
		self.constructors[AMBIENT_COLOR] = Rgb1Chunk
		self.constructors[COLOR] = Rgb1Chunk
		self.constructors[EDITOR] = EditorChunk
		self.constructors[FACES_DESCRIPTION] = FacesDescriptionChunk
		self.constructors[HIERARCHY] = HierarchyChunk
		self.constructors[HIERARCHY_INFO] = HierarchyInfoChunk
		self.constructors[INT_PERCENT] = IntPercentChunk
		self.constructors[MAIN] = MainChunk
		self.constructors[MATERIAL] = MaterialChunk
		self.constructors[MAT_AMBIENT_COLOR] = Rgb1Chunk
		self.constructors[MAT_BUMP_PERCENT] = PercentageIntChunk
		self.constructors[MAT_DIFFUSE_COLOR] = Rgb1Chunk
		self.constructors[MAT_NAME] = StringChunk
		self.constructors[MAT_REFLECTION_BLUR_PERCENTAGE] = PercentageChunk
		self.constructors[MAT_SHININESS_PERCENT] = PercentageChunk
		self.constructors[MAT_SHININESS_STRENGTH_PERCENT] = PercentageChunk
		self.constructors[MAT_SPECULAR_COLOR] = Rgb1Chunk
		self.constructors[MAT_TEXTURE_NAME] = StringChunk
		self.constructors[MAT_TRANSPARENCY_FALLOFF_PERCENTAGE] = PercentageChunk
		self.constructors[MAT_TRANSPARENCY_PERCENTAGE] = PercentageChunk
		self.constructors[MAT_SELF_ILLUM_PERCENTAGE] = PercentageChunk
		self.constructors[MAT_WIRESIZE] = FloatChunk
		self.constructors[MESH_INFO] = MeshInfoChunk
		self.constructors[MESH_NAME] = StringChunk
		self.constructors[MULTIPLIER] = FloatChunk
		self.constructors[NAMED_OBJECT] = NamedObjectChunk
		self.constructors[TRI_MESH_OBJ] = NTriObjectChunk
		self.constructors[RANGE_END] = FloatChunk
		self.constructors[RANGE_START] = FloatChunk
		self.constructors[RGB1] = Rgb1Chunk
		self.constructors[RGB2] = Rgb2Chunk
		self.constructors[SCALE] = FloatChunk
		self.constructors[TRK_PIVOT] = TrkPivotChunk
		self.constructors[TRK_SCALE] = TrkScaleChunk
		self.constructors[TRK_ROTATION] = TrkRotationChunk
		self.constructors[TRK_POSITION] = TrkPositionChunk
		self.constructors[TRI_PLACEMENT] = PlacementChunk
		self.constructors[TRI_MAPPINGCOORS] = Vertex2ListChunk
		self.constructors[TRI_MATERIAL] = FacesMaterialChunk
		self.constructors[TRI_VERTEXL] = Vertex3ListChunk
		self.constructors[KEYFRAMER] = AbstractChunk
		self.constructors[CURRENT_FRAME] = IntChunk

		self.end = os.path.getsize(filename)
		self.file = open(filename, 'rb')
		self.limit = self.end
		self.tg = doc
		self.currentGroup = doc
		self.materials = {}
		self.namedObjectes = {}
		self.keyMatrix = {}

	def close(self): self.file.close()

	def getUnsignedByte(self):      return ord(self.file.read(1))
	def getUnsignedShort(self):     return unpack('<H', self.file.read(2))[0]
	def getShort(self):             return unpack('<h', self.file.read(2))[0]
	def getInt(self):		        return unpack('<L', self.file.read(4))[0]
	def getFloat(self):             return unpack('<f', self.file.read(4))[0]
	def getPoint2f(self):           return unpack('<ff', self.file.read(8))
	def getPoint3f(self):           return unpack('<fff', self.file.read(12))

	def getChunkId2(self):	        return self.getUnsignedShort()
	def getChunkLen4(self):	        return self.getInt()
	def getString(self):
		buff = []
		b = self.file.read(1)
		while (ord(b) != 0):
			buff.append(b)
			b = 0
			if (self.file.tell() < self.limit):
				b = self.file.read(1)
		return ''.join(buff).encode('UTF-8')

	def createChunk(self, id, len):
		if (id in self.constructors):
			return self.constructors[id](id, len)
		return SkipChunk(id, len)

	def hasRemaining(self):
		pos = self.file.tell()
		return (pos < self.end) and (pos < self.limit)

	def getChunkBytes(self):
		return self.file.read(self.limit - self.file.tell())

	def loadSubChunks(self, parentChunk, parentChunkLen, level = 0):
		posStart = self.file.tell()

		while (self.hasRemaining()):
			try:
				chunkId = self.getChunkId2()
				chunkLen = self.getChunkLen4() - 6;
				chunk = self.createChunk(chunkId, chunkLen);

				finishedPosition = self.file.tell() + chunkLen;
				previousLimit = self.limit
				self.limit = finishedPosition

				if ((chunk is not None) and (chunk.len != 0)):
					parentChunk.addSubChunk(chunkId, chunk)
					chunk.loadData(self)
					#FreeCAD.Console.PrintMessage("%sadded %s\n" %((level + 1) * '  ', chunk))
					try:
						if (self.hasRemaining()):
							self.loadSubChunks(chunk, chunkLen, level + 1)
						chunk.initialize(self)
					except:
						FreeCAD.Console.PrintError(traceback.format_exc())
						FreeCAD.Console.PrintError("%s - Trying to continue\n" %(chunk))
			except Exception as e:
				self.limit = posStart + parentChunkLen
				self.file.seek(self.limit)
				FreeCAD.Console.PrintError(traceback.format_exc())
				raise BaseException(" tried to read too much data from the buffer. Trying to recover.\n", e)
			self.limit = previousLimit

	def adjustMaterial(self, obj, mat):
		if ((obj is not None) and (mat is not None)):
			material = self.materials.get(mat.name)
			if (material):
				obj.ViewObject.ShapeMaterial.AmbientColor  = material.get('ambient',  (0,0,0))
				obj.ViewObject.ShapeMaterial.DiffuseColor  = material.get('diffuse',  (0.8,0.8,0.8))
				#obj.ViewObject.ShapeMaterial.EmissiveColor = material.get('emissive', (0,0,0))
				obj.ViewObject.ShapeMaterial.SpecularColor = material.get('specular', (0,0,0))
				obj.ViewObject.ShapeMaterial.Shininess     = material.get('shinines', 0.2)
				obj.ViewObject.ShapeMaterial.Transparency  = material.get('transparency', 0.0)
			else:
				FreeCAD.Console.PrintError("Can't find material '%s'!\n" %(name))
