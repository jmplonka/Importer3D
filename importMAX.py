# -*- coding: utf8 -*-

__title__  = "FreeCAD Autodesk 3DS Max importer"
__author__ = "Jens M. Plonka"
__url__    = "https://www.github.com/jmplonka/Importer3D"

import FreeCAD, triangulate, numpy, zlib, sys, traceback
from importUtils import missingDependency, canImport, newObject, getByte, getShorts, getShort, getInts, getInt, getLong, getFloats, getFloat
from math        import degrees

try:
	import olefile
except:
	missingDependency("olefile", "http://www.decalage.info/python/olefileio", "olefile")

import struct

DEBUG         = False # Dump chunk content to console?

CLS_DATA      = []
CONFIG        = []
DLL_DIR_LIST  = []
CLS_DIR3_LIST = []
VID_PST_QUE   = []
SCENE_LIST    = []

class AbstractChunk():
	def __init__(self, type, size, level, number):
		self.number   = number
		self.type     = type
		self.level    = level
		self.parent   = None
		self.previous = None
		self.next     = None
		self.size     = size
		self.unknown  = True
		self.format   = None
		self.data     = None
		self.resolved = False
	def __str__(self):
		if (self.unknown == True):
			return "%s[%4x] %04X: %s" %("  "*self.level, self.number, self.type, ":".join("%02x"%(ord(c)) for c in self.data))
		return "%s[%4x] %04X: %s=%s" %("  "*self.level, self.number, self.type, self.format, self.data)

class ByteArrayChunk(AbstractChunk):
	def __init__(self, type, data, level, number): AbstractChunk.__init__(self, type, data, level, number)
	def set(self, data, name, format, start, end):
		try:
			self.data = struct.unpack(format, data[start:end])
			self.format = name
			self.unknown = False
		except Exception as e:
			self.data = data
	def setStr16(self, data):
		try:
			self.data = data.decode('UTF-16LE')
			self.format = "Str16"
			self.unknown = False
		except:
			self.data = data
	def setLStr16(self, data):
		try:
			l, o = getInt(data, 0)
			self.data = data[o:o+l*2].decode('utf-16-le')
			if (self.data[-1] == b'\0'): self.data = self.data[0:-1]
			self.format = "LStr16"
			self.unknown = False
		except:
			self.data = data
	def setData(self, data):
		if (self.type == 0x0340): self.setStr16(data)
		elif (self.type == 0x0456): self.setStr16(data)
		elif (self.type == 0x0962): self.setStr16(data)
		elif (self.type == 0x2034): self.set(data, "int[]", '<' + 'I'*(len(data)/4), 0, len(data))
		elif (self.type == 0x2035): self.set(data, "int{}", '<' + 'I'*(len(data)/4), 0, len(data))
		elif (self.type == 0x2501): self.set(data, "float[]", '<' + 'f'*(len(data)/4), 0, len(data))
		elif (self.type == 0x2503): self.set(data, "float[]", '<' + 'f'*(len(data)/4), 0, len(data))
		elif (self.type == 0x2504): self.set(data, "float[]", '<' + 'f'*(len(data)/4), 0, len(data))
		elif (self.type == 0x2505): self.set(data, "float[]", '<' + 'f'*(len(data)/4), 0, len(data))
		elif (self.type == 0x2510): self.set(data, "struct", '<' + 'f'*((len(data)/4) - 1) + 'i', 0, len(data))
		elif (self.type == 0x2511): self.set(data, "float[]", '<' + 'f'*(len(data)/4), 0, len(data))
		elif (self.type == 0x4001): self.setStr16(data)
		else:
			self.unknown = True
			self.data = data
		try:
			if (DEBUG): FreeCAD.Console.PrintMessage("%s\n" %(self))
		except Exception as e:
			self.format = None
			self.unknown = True
			self.data =  ":".join("%02x"%(ord(c)) for c in data)
			if (DEBUG): FreeCAD.Console.PrintMessage("%s\n" %(self))

class ClsDir3Chunk(ByteArrayChunk):
	def __init__(self, type, data, level, number):
		AbstractChunk.__init__(self, type, data, level, number)
		self.dll = None
	def setData(self, data):
		if (self.type == 0x2042): self.setStr16(data) # ClsName
		elif (self.type == 0x2060): self.set(data, "struct", '<IQI', 0, 16) # DllIndex, ID, SuperID
		else:
			self.unknown = False
			self.data =  ":".join("%02x"%(ord(c)) for c in data)
		try:
			if (DEBUG): FreeCAD.Console.PrintMessage("%s\n" %(self))
		except:
			self.format = None
			self.unknown = False
			self.data =  data
			if (DEBUG): FreeCAD.Console.PrintMessage("%s\n" %(self))

class DllDirChunk(ByteArrayChunk):
	def __init__(self, type, data, level, number): AbstractChunk.__init__(self, type, data, level, number)
	def setData(self, data):
		if (self.type == 0x2039): self.setStr16(data)
		elif (self.type == 0x2037): self.setStr16(data)
		try:
			if (DEBUG): FreeCAD.Console.PrintMessage("%s\n" %(self))
		except:
			self.format = None
			self.unknown = False
			self.data =  ":".join("%02x"%(ord(c)) for c in data)
			if (DEBUG): FreeCAD.Console.PrintMessage("%s\n" %(self))

class ContainerChunk(AbstractChunk):
	def __init__(self, type, data, level, number, primitiveReader=ByteArrayChunk):
		AbstractChunk.__init__(self, type, data, level, number)
		self.primitiveReader = primitiveReader
	def __str__(self):
		if (self.unknown == True):
			return "%s[%4x] %04X" %("  "*self.level, self.number, self.type)
		return "%s[%4x] %04X: %s" %("  "*self.level, self.number, self.type, self.format)
	def getFirst(self, type):
		for child in self.children:
			if (child.type == type): return child
		return None
	def setData(self, data):
		previous = None
		next     = None
		reader   = ChunkReader()
		if (DEBUG): FreeCAD.Console.PrintMessage("%s\n" %(self))
		self.children  = reader.getChunks(data, self.level + 1, ContainerChunk, self.primitiveReader)

class SceneChunk(ContainerChunk):
	def __init__(self, type, data, level, number, primitiveReader=ByteArrayChunk):
		AbstractChunk.__init__(self, type, data, level, number)
		self.primitiveReader = primitiveReader
		self.matrix = None
	def __str__(self):
		if (self.unknown == True):
			return "%s[%4x] %s" %("  "*self.level, self.number, getClsName(self))
		return "%s[%4x] %s: %s" %("  "*self.level, self.number, getClsName(self), self.format)
	def setData(self, data):
		previous       = None
		next           = None
		if (DEBUG): FreeCAD.Console.PrintMessage("%s\n" %(self))
		reader        = ChunkReader()
		self.children = reader.getChunks(data, self.level + 1, SceneChunk, ByteArrayChunk)

class ChunkReader():
	def __init__(self, name = None): self.name = name

	def getChunks(self, data, level, containerReader, primitiveReader):
		chunks = []
		offset = 0

		if (level == 0):
			t, o = getShort(data, 0)
			l, o = getInt(data, o)
			if (t == 0x8B1F):
				t, o = getInt(data, o)
				if (t == 0x0B000000):
					data = zlib.decompress(data, zlib.MAX_WBITS|32)

		if (level==0):
			progressbar = FreeCAD.Base.ProgressIndicator()
			progressbar.start("  reading '%s'..."%self.name, len(data))
		while offset < len(data):
			old = offset
			offset, chunk = self.getNextChunk(data, offset, level, len(chunks), containerReader, primitiveReader)
			if (level==0):
				for i in xrange(offset - old):
					progressbar.next()
			chunks.append(chunk)

		if (level==0): progressbar.stop()

		return chunks

	def getNextChunk(self, data, offset, level, number, containerReader, primitiveReader):
		header = 6
		typ, siz, = struct.unpack("<Hi", data[offset:offset+header])
		chunkSize = siz & 0x7FFFFFFF
		if (siz == 0):
			siz, dummy = getLong(data, offset+6)
			header = 14
			chunkSize = siz & 0x7FFFFFFFFFFFFFFF
		if (siz < 0):
			chunk = containerReader(typ, chunkSize, level, number, primitiveReader)
		else:
			chunk = primitiveReader(typ, chunkSize, level, number)
		chunkData = data[offset + header:offset + chunkSize]
		chunk.setData(chunkData)
		return offset + chunkSize, chunk

class PointNi3s():
	def __init__(self):
		self.points = None
		self.flags  = 0
		self.fH     = 0
		self.f1     = 0
		self.f2     = 0
		self.fA     = []
	def __str__(self):
		return "[%s] - %X, %X, %X, [%s]" %('/'.join("%d" %p for p in self.points), self.fH, self.f1, self.f2, ','.join("%X" %f for f in self.fA))

class Material():
	def __init__(self):
		self.data = {}
	def set(self, name, value): self.data[name] = value
	def get(self, name, default=None):
		value = None
		if (name in self.data): value = self.data[name]
		if (value is None): return default
		return value

def getNode(index):
	global SCENE_LIST
	if (index < len(SCENE_LIST[0].children)):
		return SCENE_LIST[0].children[index]
	return None

def getNodeParent(node):
	parent = None
	if (node):
		chunk = node.getFirst(0x0960)
		if (chunk is not None):
			idx, offset = getInt(chunk.data, 0)
			parent = getNode(idx)
			if (parent is None):
				FreeCAD.Console.PrintError("parent index %X < %X!\n" %(idx, len(SCENE_LIST)))
	return parent

def getNodeName(node):
	if (node):
		name = node.getFirst(0x0962)
		if (name): return name.data
	return None

def getDll(container):
	global DLL_DIR_LIST
	idx = container.getFirst(0x2060).data[0]
	if (idx < len(DLL_DIR_LIST)):
		return DLL_DIR_LIST[idx]
	return None

def getClass(chunk):
	global CLS_DIR3_LIST
	if (chunk.type < len(CLS_DIR3_LIST)):
		return CLS_DIR3_LIST[chunk.type]
	return None

def getGUID(chunk):
	cls = getClass(chunk)
	if (cls): return cls.getFirst(0x2060).data[1]
	return chunk.type

def getSuperId(chunk):
	cls = getClass(chunk)
	if (cls): return cls.getFirst(0x2060).data[2]
	return None

def getClsName(chunk):
	cls = getClass(chunk)
	if (cls):
		try:
			return "'%s'" %(cls.getFirst(0x2042).data)
		except:
			return "'%s'" %(repr(cls.getFirst(0x2042).data))
	return u"%04X" %(chunk.type)

def getReferences(chunk):
	references = []
	refs = chunk.getFirst(0x2034)
	if (refs):
		references = [getNode(idx) for idx in refs.data]
	return references

def getTypedRefernces(chunk):
	references = {}
	refs = chunk.getFirst(0x2035)
	if (refs):
		type = refs.data[0]
		offset = 1
		while offset < len(refs.data):
			key = refs.data[offset]
			offset += 1
			idx = refs.data[offset]
			offset += 1
			references[key] = getNode(idx)
	return references

def readChunks(ole, name, fileName, containerReader=ContainerChunk, primitiveReader=ByteArrayChunk):
	with ole.openstream(name) as file:
		scene = file.read()
#		with open(fileName, 'wb') as file:
#			file.write(scene)
		reader = ChunkReader(name)
		return reader.getChunks(scene, 0, containerReader, primitiveReader)

def readClassData(ole, fileName):
	global CLS_DATA
	CLS_DATA = readChunks(ole, 'ClassData', fileName+'.ClsDat.bin')

def readClassDirectory3(ole, fileName):
	global CLS_DIR3_LIST
	CLS_DIR3_LIST = readChunks(ole, 'ClassDirectory3', fileName+'.ClsDir3.bin', ContainerChunk, ClsDir3Chunk)
	for clsDir in CLS_DIR3_LIST:
		clsDir.dll = getDll(clsDir)

def readConfig(ole, fileName):
	global CONFIG
	CONFIG = readChunks(ole, 'Config', fileName+'.Cnf.bin')

def readDllDirectory(ole, fileName):
	global DLL_DIR_LIST
	DLL_DIR_LIST = readChunks(ole, 'DllDirectory', fileName+'.DllDir.bin', ContainerChunk, DllDirChunk)

def readVideoPostQueue(ole, fileName):
	global VID_PST_QUE
	VID_PST_QUE = readChunks(ole, 'VideoPostQueue', fileName+'.VidPstQue.bin')

def getPoint(float, default = 0.0):
	uid = getGUID(float)
	if (uid == 0x2007): # Bezier-Float
		f = float.getFirst(0x7127)
		if (f):
			try:
				return f.getFirst(0x2501).data[0]
			except:
				FreeCAD.Console.PrintWarning("SyntaxError: %s - assuming 0.0!\n" %(float))
		return default
	if (uid == 0x71F11549498702E7): # Float Wire
		f = getReferences(float)[0]
		return getPoint(f)
	else:
		FreeCAD.Console.PrintError("Unknown float type 0x%04X=%s!\n" %(uid, float))
		return default

def getPoint3D(chunk, default=0.0):
	floats = []
	if (chunk):
		refs = getReferences(chunk)
		for float in refs:
			f = getPoint(float, default)
			if (f is not None):
				floats.append(f)
	return floats

def getPosition(pos):
	mtx = numpy.identity(4, numpy.float32)
	if (pos):
		uid = getGUID(pos)
		if (uid == 0xFFEE238A118F7E02): # => Position XYZ
			pos = getPoint3D(pos)
		elif (uid == 0x0000000000442312): # => TCB Position
			pos = pos.getFirst(0x2503).data
		elif (uid == 0x0000000000002008): # => Bezier Position
			pos = pos.getFirst(0x2503).data
		else:
			pos = None
			FreeCAD.Console.PrintError("Unknown position 0x%04X=%s!\n" %(uid, pos))
		if (pos):
			mtx[0,3] = pos[0]
			mtx[1,3] = pos[1]
			mtx[2,3] = pos[2]
	return mtx

def getRotation(pos):
	r = None
	mtx = numpy.identity(4, numpy.float32)
	if (pos):
		uid = getGUID(pos)
		if (uid == 0x2012): # => Euler XYZ
			rot = getPoint3D(pos)
			r = FreeCAD.Rotation(degrees(rot[2]), degrees(rot[1]), degrees(rot[0]))
		elif (uid == 0x0000000000442313): #'TCB Rotation'
			rot = pos.getFirst(0x2504).data
			r = FreeCAD.Rotation(rot[0], rot[1], rot[2], rot[3])
		elif (uid == 0x000000004B4B1003): #'Rotation List'
			refs = getReferences(pos)
			if (len(refs) > 3):
				return getRotation(refs[0])
		elif (uid == 0x3A90416731381913): #'Rotation Wire'
			return getRotation(getReferences(pos)[0])
		else:
			FreeCAD.Console.PrintError("Unknown rotation 0x%04X=%s!\n" %(uid, pos))
		if (r):
			m = FreeCAD.Placement(FreeCAD.Vector(), r).toMatrix()
			mtx = numpy.array([
				[m.A11, m.A12, m.A13, m.A14],
				[m.A21, m.A22, m.A23, m.A24],
				[m.A31, m.A32, m.A33, m.A34],
				[m.A41, m.A42, m.A43, m.A44]], numpy.float32)

	return mtx

def getScale(pos):
	mtx = numpy.identity(4, numpy.float32)
	if (pos):
		uid = getGUID(pos)
		if (uid == 0x2010): # => Bezier Scale
			scale = pos.getFirst(0x2501)
			if (scale is None): scale = pos.getFirst(0x2505)
			pos = scale.data
		elif (uid == 0x0000000000442315): # 'TCB Zoom'
			scale = pos.getFirst(0x2501)
			if (scale is None): scale = pos.getFirst(0x2505)
			pos = scale.data
		elif (uid == 0xFEEE238B118F7C01): # 'ScaleXYZ'
			pos = getPoint3D(pos, 1.0)
		else:
			FreeCAD.Console.PrintError("Unknown scale 0x%04X=%s!\n" %(uid, pos))
			return mtx
		mtx[0,0] = pos[0]
		mtx[1,1] = pos[1]
		mtx[2,2] = pos[2]
	return mtx

def createMatrix(prc):
	mtx = numpy.identity(4, numpy.float32)

	uid = getGUID(prc)
	scl = None
	rot = None
	pos = None
	if (uid == 0x2005): # Position/Rotation/Scale
		pos = getPosition(getReferences(prc)[0])
		rot = getRotation(getReferences(prc)[1])
		scl = getScale(getReferences(prc)[2])
	elif (uid == 0x9154) : # BipSlave Control
		bipedSubAnim = getReferences(prc)[2]
		refs = getReferences(bipedSubAnim)
		scl = getScale(getReferences(refs[1])[0])
		rot = getRotation(getReferences(refs[2])[0])
		pos = getPosition(getReferences(refs[3])[0])

	if (pos is not None):
		mtx = numpy.dot(mtx, pos)
	if (rot is not None):
		mtx = numpy.dot(mtx, rot)
	if (scl is not None):
		mtx = numpy.dot(mtx, scl)

	return mtx

def getProperty(properties, idx):
	for child in properties.children:
		if (child.type == 0x100E):
			if (getShort(child.data, 0)[0] == idx): return child
	return None

def getColorMax(colors, idx):
	prp = getProperty(colors, idx)
	if (prp is not None):
		c, o = getFloats(prp.data, 15, 3)
		return (c[0], c[1], c[2])
	return None

def getFloatMax(colors, idx):
	prp = getProperty(colors, idx)
	if (prp is not None):
		f, o = getFloat(prp.data, 15)
		return f
	return None

def getMatStandard(refs):
	material = None
	try:
		colors = refs[2]
		parameters = getReferences(colors)[0] # ParameterBlock2
		material = Material()
		material.set('ambient',  getColorMax(parameters, 0x00))
		material.set('diffuse',  getColorMax(parameters, 0x01))
		material.set('specular', getColorMax(parameters, 0x02))
		material.set('emissive', getColorMax(parameters, 0x08))
		material.set('shinines', getFloatMax(parameters, 0x0A))
		transparency = refs[4] # ParameterBlock2
		material.set('transparency', getFloatMax(transparency, 0x02))
	except:
		FreeCAD.Console.PrintError(traceback.format_exc())
		FreeCAD.Console.PrintError('\n')
	return material

def getMatVRay(vry):
	material = Material()
	try:
		material.set('diffuse',  getColorMax(vry, 0x01))
		material.set('ambient',  getColorMax(vry, 0x02))
		material.set('specular', getColorMax(vry, 0x05))
#		material.set('emissive', getColorMax(vry, 0x05))
#		material.set('shinines', getFloatMax(vry, 0x0B))
#		material.set('transparency', getFloatMax(vry, 0x02))
	except:
		FreeCAD.Console.PrintError(traceback.format_exc())
		FreeCAD.Console.PrintError('\n')
	return material

def getMatArchDesign(ad):
	material = Material()
	try:
		material.set('diffuse',  getColorMax(ad, 0x1A))
#		material.set('ambient',  getColorMax(ad, 0x02))
#		material.set('specular', getColorMax(ad, 0x05))
#		material.set('emissive', getColorMax(ad, 0x05))
#		material.set('shinines', getFloatMax(ad, 0x0B))
#		material.set('transparency', getFloatMax(ad, 0x02))
	except:
		FreeCAD.Console.PrintError(traceback.format_exc())
		FreeCAD.Console.PrintError('\n')
	return material

def adjustMaterial(obj, mat):
	material = None
	if (mat is not None):
		uid = getGUID(mat)

		if (uid == 0x0002): # 'Standard'
			refs = getReferences(mat)
			material = getMatStandard(refs)
		elif (uid == 0x0000000000000200): # 'Multi/Sub-Object'
			refs = getReferences(mat)
			material = adjustMaterial(obj, refs[-1])
		elif (uid == 0x7034695C37BF3F2F): # 'VRayMtl'
			refs = getTypedRefernces(mat)
			material = getMatVRay(refs[1])
		elif (uid == 0x4A16365470B05735): # 'Arch & Design'
			refs = getReferences(mat)
			material = getMatArchDesign(refs[0])
		else:
			FreeCAD.Console.PrintWarning("Unknown material GUID=%016X (%s) - skipped\n!" %(uid, getClsName(mat)))

		if (obj is not None) and (material is not None):
			obj.ViewObject.ShapeMaterial.AmbientColor  = material.get('ambient',  (0,0,0))
			obj.ViewObject.ShapeMaterial.DiffuseColor  = material.get('diffuse',  (0.8,0.8,0.8))
			#obj.ViewObject.ShapeMaterial.EmissiveColor = material.get('emissive', (0,0,0))
			obj.ViewObject.ShapeMaterial.SpecularColor = material.get('specular', (0,0,0))
			obj.ViewObject.ShapeMaterial.Shininess     = material.get('shinines', 0.2)
			obj.ViewObject.ShapeMaterial.Transparency  = material.get('transparency', 0.0)

def createShape3d(doc, pts, indices,  shape, key, prc, mat):
	name = shape.getFirst(0x0962).data
	cnt = len(pts)
	if (cnt > 0):
		if (key is not None): name = "%s_%d" %(name, key)

		mtx = createMatrix(prc)
		# translate the points according to the transformation matrix
		pt = numpy.ones((cnt, 4), numpy.float32)
		pt[:,:3] = pts
		tpt = numpy.transpose(numpy.dot(mtx, numpy.transpose(pt)))
		data = []
		for pol in indices:
			if (len(pol) > 2): # skip points and lines!
				try:
					ngon = [tpt[idx][0:3] for idx in pol]
					for triangle in triangulate.getTriangles(ngon):
						data.append(triangle)
				except:
					pass

		if (len(data) > 0):
			obj = newObject(doc, name, data)
			adjustMaterial(obj, mat)
			return True
	FreeCAD.Console.PrintWarning("no faces ... ")
	return True

def calcCoordinates(data):
	l, o = getInt(data, 0)
	cnt = len(data) / 16
	p = numpy.zeros((cnt, 3), numpy.float32)
	i = 0
	while o < len(data):
		w, o = getInt(data, o)
		f, o = getFloats(data, o, 3)
		p[i:0:3] = f
		i += 1
	return p

def calcCoordinatesI(data):
	l, o = getInt(data, 0)
	cnt = len(data) / 12
	p = numpy.zeros((cnt, 3), numpy.float32)
	i = 0
	while (o < len(data)):
		f, o = getFloats(data, o, 3)
		p[i:0:3] = f
		i += 1
	return p

def getNGons4i(points):
	vertex = {}

	for point in points:
		ngon = point.points
		key  = point.fH
		if (key not in vertex):
			vertex[key] = []
		vertex[key].append(ngon)

	return vertex

def getNGons5i(data):
	count, o = getInt(data, 0)
	ngons = []
	while count > 0:
		p, o = getInts(data, o, 3)
		o += 8
		ngons.append(p)
		count -= 1
	return ngons

def getNGons6i(data):
	cnt, o = getInt(data, 0)
	list = []
	while (o < len(data)):
		l, o = getInts(data, o, 6)
		i = 5
		while ((i > 3) and (l[i] < 0)):
			i -= 1
		if (i>2): list.append(l[1:i])
	return list

def getNGonsNi(polys):
	vertex = []
	o = 0
	while (o < len(polys)):
		num = polys[o]
		o += 1
		ngon = []
		k = 0
		while (k < num):
			p = points[polys[o]][1]
			ngon.append(p)
			o += 1
			k += 1
		vertex.append(ngon)
	return vertex

def getNGonsInts(chunk):
	o = 0
	list = []
	data = chunk.data
	while (o < len(data)):
		cnt, o = getInt(data, o)
		points, o = getInts(data, o, cnt)
		list.append(points)
	return list

def calcPointNi3s(chunk):
	data = chunk.data
	cnt, o = getInt(data, 0)
	list = []
	try:
		while (o < len(data)):
			p = PointNi3s()

			l, o = getInt(data, o)
			p.points, o = getInts(data, o, l)
			p.flags, o= getShort(data, o)

			if ((p.flags & 0x01) != 0): p.f1, o = getInt(data, o)
			if ((p.flags & 0x08) != 0): p.fH, o = getShort(data, o)
			if ((p.flags & 0x10) != 0): p.f2, o = getInt(data, o)
			if ((p.flags & 0x20) != 0): p.fA, o = getInts(data, o, 2 * (l - 3))

			if (len(p.points) > 0):
				list.append(p)
	except Exception as e:
		FreeCAD.Console.PrintError(traceback.format_exc())
		FreeCAD.Console.PrintError('\n')
		FreeCAD.Console.PrintError("%s: o = %d\n" %(e, o))
		raise e
	return list

def createEditablePoly(doc, shape, msh, mat, mtx):
	FreeCAD.Console.PrintMessage("building 'Editible Poly' ... ")
	ply = msh.getFirst(0x08FE)
	indexList   = [] # texture groups
	coordListI  = [] # texture coordinates
	indicesList = [] # texture indices
	point3i     = None
	point4i     = None
	point6i     = None
	pointNi     = None
	coords      = None
	created = False

	if (ply):
		for child in ply.children:
			if (child.type == 0x0100):   coords = calcCoordinates(child.data)# #, n x (g=uint16,x=float16,y=float16,z=float16)
			elif (child.type == 0x0108): point6i = child.data
#			elif (child.type == 0x010A): point3i = child.data
			elif (child.type == 0x011A): point4i = calcPointNi3s(child)# comparable with 0x012B!!
#			elif (child.type == 0x0120): pass # Number of groups+1
#			elif (child.type == 0x0124): indexList.append(getInt(child.data, 0)[0])
#			elif (child.type == 0x0128): coordListI.append(calcCoordinatesI(child.data))
#			elif (child.type == 0x012B): indicesList.append(getNGonsInts(child))
#			elif (child.type == 0x0130): pass # always 0
#			elif (child.type == 0x0140): pass # always 0x40
#			elif (child.type == 0x0150): pass
#			elif (child.type == 0x0200): pass
#			elif (child.type == 0x0210): pass # n, i * 1.0
#			elif (child.type == 0x0240): pass
#			elif (child.type == 0x0250): pass
			elif (child.type == 0x0310): pointNi = child.data

#		if (len(indexList) > 0):
#			FreeCAD.Console.PrintMessage(" %s " %(str(indexList)))
#			for i in xrange(len(indexList)):
#				created |= createShape3d(doc, coords, indicesList[i],  shape, indexList[i], mtx, mat)
#		elif (point4i is not None):
		if (point4i is not None):
			vertex = getNGons4i(point4i)
			if (len(vertex) > 0):
				for key, ngons in vertex.items():
					created |= createShape3d(doc, coords, ngons, shape, key, mtx, mat)
			else:
				created = True
				FreeCAD.Console.PrintWarning("no faces ... ")
		elif (point6i is not None):
			ngons = getNGons6i(point6i)
			created = createShape3d(doc, coords, ngons, shape, None, mtx, mat)
		elif (pointNi is not None):
			ngons = getNGonsNi(pointNi)
			created = createShape3d(doc, coords, ngons, shape, None, mtx, mat)
		else:
			FreeCAD.Console.PrintError("hugh? - no data found for %s?!?" %(ply))
	return created

def getArrayPoint3f(values):
	v = []
	if len(values) >= 4:
		count, offset = getInt(values, 0)
		while (count > 0):
			floats, offset = getFloats(values, offset, 3)
			v.append(floats)
			count -= 1
	return v

def createEditableMesh(doc, shape, msh, mat, mtx):
	FreeCAD.Console.PrintMessage("building 'Editable Mesh' ... ")
	ply = msh.getFirst(0x08FE)
	created = False

	if (ply):
		vertexChunk = ply.getFirst(0x0914)
		indexChunk = ply.getFirst(0x0912)
		coords = getArrayPoint3f(vertexChunk.data)
		ngons = getNGons5i(indexChunk.data)
		created = createShape3d(doc, coords, ngons,  shape, None, mtx, mat)

	return created

def getMtxMshMatLyr(shape):
	refs = getTypedRefernces(shape)
	if (refs):
		mtx = refs.get(0, None)
		msh = refs.get(1, None)
		mat = refs.get(3, None)
		lyr = refs.get(6, None)
	else:
		refs = getReferences(shape)
		mtx = refs[0]
		msh = refs[1]
		mat = refs[3]
		lyr = refs[6]
	return mtx, msh, mat, lyr

def createShell(doc, shape, shell, mat, mtx):
	refs = getReferences(shell)
	msh = refs[-1]
	created, uid = createMesh(doc, shape, msh, mtx, mat)
	if (not created):
		FreeCAD.Console.PrintError("hugh? %016X: %s - " %(uid, getClsName(msh)))
	return created

def createSkippable(doc, shape, msh, mat, mtx, type):
	# skip creating skippable!
	FreeCAD.Console.PrintMessage("skipping %s ... " % type)
	return True

def createMesh(doc, shape, msh, mtx, mat):
	created = False
	uid = getGUID(msh)
	if (uid == 0x0E44F10B3):
		created = createEditableMesh(doc, shape, msh, mat, mtx)
	elif (uid == 0x192F60981BF8338D):
		created = createEditablePoly(doc, shape, msh, mat, mtx)
	elif (uid == 0x0000000000002032):
		created = createShell(doc, shape, msh, mat, mtx)
	elif (uid == 0x0000000000002033):
		created = createShell(doc, shape, msh, mat, mtx)
	elif (uid == 0x0000000000000011): # Sphere
		created = createSkippable(doc, shape, msh, mat, mtx, 'Sphere')
	elif (uid == 0x0000000000001002): # Camera
		created = createSkippable(doc, shape, msh, mat, mtx, 'Camera')
	elif (uid == 0x0000000000001011): # Omni
		created = createSkippable(doc, shape, msh, mat, mtx, 'Omni')
	elif (uid == 0x0000000000001020): # Camera.Target
		created = createSkippable(doc, shape, msh, mat, mtx, 'Camera Target')
	elif (uid == 0x0000000000001040): # Line
		created = createSkippable(doc, shape, msh, mat, mtx, 'Line')
	elif (uid == 0x0000000000002013): # Point
		created = createSkippable(doc, shape, msh, mat, mtx, 'Point')
	elif (uid == 0x0000000000009125): # Biped Object
		created = createSkippable(doc, shape, msh, mat, mtx, 'Biped Object')
	elif (uid == 0x0000000000876234): # Dummy
		created = createSkippable(doc, shape, msh, mat, mtx, 'Dummy')
	elif (uid == 0x12A822FB76A11646): # CV Surface
		created = createSkippable(doc, shape, msh, mat, mtx, 'CV Surface')
	elif (uid == 0x1EB3430074F93B07): # Particle View
		created = createSkippable(doc, shape, msh, mat, mtx, 'Particle View')
	elif (uid == 0x2ECCA84028BF6E8D): # Bone
		created = createSkippable(doc, shape, msh, mat, mtx, 'Bone')
	elif (uid == 0x4E9B599047DB14EF): # Slider
		created = createSkippable(doc, shape, msh, mat, mtx, 'Slider')
	elif (uid == 0x3BDB0E0C628140F6): # VRayPlane
		created = createSkippable(doc, shape, msh, mat, mtx, 'VRayPlane')
	elif (uid == 0x05622B0D69011E82): # Compass
		created = createSkippable(doc, shape, msh, mat, mtx, 'Compass')
	elif (uid == 0x5FD602DF3C5575A1): # VRayLight
		created = createSkippable(doc, shape, msh, mat, mtx, 'VRayLight')
	elif (uid == 0x522E47057BF61478): # Sky
		created = createSkippable(doc, shape, msh, mat, mtx, 'Sky')

	return created, uid

def createObject(doc, shape):
	parent = getNodeParent(shape)
	shape.parent = parent
	name = getNodeName(shape)
	mtx, msh, mat, lyr = getMtxMshMatLyr(shape)
	while ((parent is not None) and (getGUID(parent) != 0x0002)):
		name = "%s/%s" %(getNodeName(parent), name)
		prnMtx = parent.matrix
		if (prnMtx): mtx = mtx.dot(prnMtx)
		parent = getNodeParent(parent)

	FreeCAD.Console.PrintMessage("  found Object '%s'... "%(name))
	created = False

	created, uid = createMesh(doc, shape, msh, mtx, mat)

	if (not created):
		if (uid is None):
			FreeCAD.Console.PrintWarning("skipped unknown object %s!\n" %(uid, msh))
		else:
			FreeCAD.Console.PrintWarning("skipped object %016X=%s!\n" %(uid, msh))
	else:
		FreeCAD.Console.PrintMessage("DONE!\n")

def makeScene(doc, parent, level = 0):
	if (level==0):
		progressbar = FreeCAD.Base.ProgressIndicator()
		progressbar.start("  building objects ...", len(parent.children))
	for scene in parent.children:
		if (level==0): progressbar.next()

		if (isinstance(scene, SceneChunk)):
			if ((getGUID(scene) == 0x0001) and (getSuperId(scene) == 0x0001)):
				try:
					createObject(doc, scene)
				except Exception as e:
					FreeCAD.Console.PrintError(traceback.format_exc())
	if (level==0): progressbar.stop()

def readScene(doc, ole, fileName):
	global SCENE_LIST
	SCENE_LIST = readChunks(ole, 'Scene', fileName+'.Scn.bin', containerReader=SceneChunk)

	makeScene(doc, SCENE_LIST[0], 0)

def read(doc, fileName):
	if (olefile.isOleFile(fileName)):
		ole = olefile.OleFileIO(fileName)
		if (DEBUG): FreeCAD.Console.PrintMessage("==== ClassData       ===\n")
		readClassData(ole, fileName)
		if (DEBUG): FreeCAD.Console.PrintMessage("==== Config          ===\n")
		readConfig(ole, fileName)
		if (DEBUG): FreeCAD.Console.PrintMessage("==== DllDirectory    ===\n")
		readDllDirectory(ole, fileName)
		if (DEBUG): FreeCAD.Console.PrintMessage("==== ClassDirectory3 ===\n")
		readClassDirectory3(ole, fileName)
		if (DEBUG): FreeCAD.Console.PrintMessage("==== VideoPostQueue  ===\n")
		readVideoPostQueue(ole, fileName)
		if (DEBUG): FreeCAD.Console.PrintMessage("==== Scene           ===\n")
		readScene(doc, ole, fileName)
	else:
		FreeCAD.Console.PrintError("File seems to be no 3D Studio Max file!")
