# -*- coding: utf8 -*-

__title__  = "FreeCAD Maya file importer"
__author__ = "Jens M. Plonka"

import sys, struct, FreeCAD, numpy, uuid, triangulate
from importUtils import newObject

ALIGNMENT = {
	'FORM': 2, 'CAT ': 2, 'LIST': 2, 'PROP': 2, # => 16Bit
	'FOR4': 4, 'CAT4': 4, 'LIS4': 4, 'PRO4': 4, # => 32Bit
	'FOR8': 8, 'CAT8': 8, 'LIS8': 8, 'PRO8': 8, # => 64Bit
}

DEBUG         = False # Dump chunk content to console?

KNOWN_METHODS = {
	'VERS': 'readString', # Version
	'UVER': 'readString', #
	'CREA': 'readCreate',
	'MADE': 'readString',
	'CHNG': 'readString',
	'ICON': 'readString',
	'INFO': 'readString',
	'OBJN': 'readString',
	'INCL': 'readString',
	'PLUG': 'readPlugin', # required Plugin
	'LUNI': 'readString', # Length Unit
	'TUNI': 'readString', # Time Unit
	'AUNI': 'readString', # Angle Unit
	'FINF': 'readString', # File Information
	'STR ': 'readStrAtr',
	'SLCT': 'readString',
	'DBLE': 'readDblAtr',
	'CMP#': 'readComponent',
	'FLGS': 'readFlgs',
	'CMPD': 'readCmpd',
	'CWFL': 'readConnect',
	'DBL3': 'read3dAtr',
	'FLT2': 'read2fAtr',
	'FLT3': 'read3fAtr',
	'ATTR': 'readAttrib',
	'MESH': 'readMesh',
	}

TRANSLATE = {
	b'\x00\x10\x2E\x55': 'MRIS', #mentalrayIblShape
	b'\x00\x10\xA8\x5E': 'MMTX', #mia_material_x
}

class Container():
	def __init__(self, type, id, pos, size, level):
		self.type     = type
		self.id       = id
		self.pos      = pos
		self.size     = size
		self.level    = level
		self.children = []
		self.branches = {}
		self.matrix   = None
		self.parent   = None

	def __str__(self):
		return "%s%s:%s" % ("  "*self.level, self.id, self.type)

	def getProperty(self, name):
		for child in self.children:
			if (child.name == name): return child
		return None

	def getPropertyId(self, id):
		for child in self.children:
			if (child.id == id): return child
		return None

	def getPosition(self):
		pos = self.getProperty('t') # translation
		if (pos):
			mtx = numpy.identity(4, numpy.float32)
			mtx[0,3] = pos.data[0]
			mtx[1,3] = pos.data[1]
			mtx[2,3] = pos.data[2]
			return mtx
		return  None

	def getRotation(self):
		rot = self.getProperty('r') # rotation

	def getScale(self):
		scl = self.getProperty('s') # scale
		if (scl):
			mtx = numpy.identity(4, numpy.float32)
			mtx[0,0] = scl.data[0]
			mtx[1,1] = scl.data[1]
			mtx[2,2] = scl.data[2]
			return mtx
		return None

	def getMatrix(self):
		if (self.matrix is None):
			pos = self.getPosition()
			rot = self.getRotation()
			scl = self.getScale()
			self.matrix = numpy.identity(4, numpy.float32)
			if (pos is not None): self.matrix = numpy.dot(self.matrix, pos)
			if (rot is not None): self.matrix = numpy.dot(self.matrix, rot)
			if (scl is not None): self.matrix = numpy.dot(self.matrix, scl)
			if (self.parent is not None):
				mtx = self.parent.getMatrix()
				self.matrix = numpy.dot(self.matrix, mtx)
		return self.matrix

class Chunk():
	def __init__(self, id, pos, size, level, data):
		self.id       = id
		self.pos      = pos
		self.size     = size
		self.level    = level
		self.children = []
		self.name     = None
		self.data     = None

	def __str__(self):
		n = self.id if (self.name is None) else self.name
		d = " at %X (%d bytes)" %(self.pos, self.size) if (self.data is None) else " = %s" %(str(self.data))
		return "%s%s%s" % ("  "*self.level, n, d)

class ReaderMB():
	def __init__(self, data):
		self.data       = data
		self.pos        = 0
		self.current    = None
		self.containers = {}
		self.alignment  = 4
		self.progress   = None

	def _get(self, fmt, size):
		end = self.pos + size
		value, = struct.unpack('>' + fmt, self.data[self.pos:end])
		self.pos = end
		self.update()
		return value

	def _gets(self, fmt, size, count):
		end = self.pos + (count * size)
		values = struct.unpack('>' + fmt*count, self.data[self.pos:end])
		self.pos = end
		self.update()
		return values

	def readLong(self):   return self._get('q', 8)
	def readFloat(self):  return self._get('f', 4)
	def readDouble(self): return self._get('d', 8)
	def readInt(self):    return self._get('i', 4)
	def readUInt(self):   return self._get('I', 4)
	def readShort(self):  return self._get('h', 2)
	def readUShort(self): return self._get('H', 2)
	def readByte(self):   return self._get('B', 1)

	def readLongs(self, count):   return self._gets('q', 8, count)
	def readFloats(self, count):  return self._gets('f', 4, count)
	def readDoubles(self, count): return self._gets('d', 8, count)
	def readInts(self, count):    return self._gets('i', 4, count)
	def readShorts(self, count):  return self._gets('h', 2, count)
	def readUShorts(self, count): return self._gets('H', 2, count)
	def readBytes(self, count):   return self._gets('B', 1, count)

	def readTypeID(self):
		typeID = self.data[self.pos: self.pos + 4]
		self.pos += 4
		typeID = TRANSLATE.get(typeID, typeID)
		return typeID

	def readSize(self):
		if (self.alignment == 2): return self.readUShort()
		if (self.alignment == 8):
			self.readInt()
			return self.readLong()
		return self.readInt()

	def readUID(self):
		data = self.data[self.pos:self.pos+16]
		a = struct.unpack('<IHHHHHH', data)
		return "{%08X-%04X-%04X-%04X-%04X%04X%04X}" %(a[0], a[2], a[1], a[4], a[3], a[6], a[5])

	def readString(self, chunk):
		chunk.name = chunk.id
		chunk.data = self.data[chunk.pos: chunk.pos+chunk.size].encode('utf8')
		self.pos = chunk.pos + chunk.size

	def readCreate(self, chunk):
		self.readConnect(chunk)
		self.current.name = chunk.name
		self.containers[chunk.name] = self.current
		path = chunk.data[0]
		if (path is not None):
			names = path.split('|')
			parent = self.containers.get(names[-1])
			if (parent is not None):
				parent.branches[chunk.data[0]] = self.current
				self.current.parent = parent
			else:
				self.current.parent = None

	def readConnect(self, chunk):
		magic = self.readByte()
		chunk.name = self.readNullTerminated()
		path = None
		if (magic == 0x05 or magic == 0x04):
			path = self.readNullTerminated()
		uid = self.readUID()
		self.pos += 0x10
		chunk.data = (path, uid)

	def readNullTerminated(self):
		start = self.pos
		while (self.data[self.pos] != '\0'):
			self.pos += 1

		end = self.pos if (self.pos < len(self.data)) else len(self.data)
		string = self.data[start:end]
		self.pos += 1
		self.update()
		return string

	def readAttributeInfo(self):
		name = self.readNullTerminated()
		mystery = self.readByte()
		return name, mystery

	def readStrAtr(self, chunk):
		chunk.name, mystery = self.readAttributeInfo()
		chunk.data = self.readNullTerminated()

	def readDblAtr(self, chunk):
		chunk.name, mystery = self.readAttributeInfo()
		count = getElementCount(chunk.name)
		chunk.data = self.readDoubles(count)
		if (count == 1): chunk.data = chunk.data[0]

	def readCmpd(self, chunk):
		chunk.name, mystery = self.readAttributeInfo()
		chunk.data = self.readDoubles(3)

	def readFlgs(self, chunk):
		chunk.name, mystery = self.readAttributeInfo()
		count = getElementCount(chunk.name)
		value = self.readInts(count)
		value = value[0] if (count == 1) else value
		chunk.data = value

	def readComponent(self, chunk):
		self.readFlgs(chunk)
		type = self.readTypeID()
		if (type == 'CMDF'):
			data = (self.readInt(), self.readInt(), self.readInt())
		elif (type == 'CLAT'):
			data = self.readInts(7)
		else:
			raise Exception("Unknow attribute type '%s'!" %(type))
		chunk.data = (chunk.data, type, data)

	def readPlugin(self, chunk):
		chunk.name = self.readNullTerminated()
		version    = self.readNullTerminated()
		options    = self.readNullTerminated()
		end = chunk.pos + chunk.size
		properties = {}
		while (self.pos < end):
			name = self.readNullTerminated()
			properties[name] = self.readInt()
		chunk.data = (version, options, properties)

	def readAttrib(self, chunk):
		chunk.name, mystery = self.readAttributeInfo()
		srt  = self.readUShort()
		ints1 = self.readInts(2)
		sn   = self.readNullTerminated()
		ln   = self.readNullTerminated()
		i    = self.readInt()
		typ  = self.readTypeID()
		value = None
		if (typ == 'DBLE'):
			value = self.readDouble()
		chunk.data = (srt, ints1, sn, ln, i, value)

	def read2fAtr(self, chunk):
		chunk.name, mystery = self.readAttributeInfo()
		count = getElementCount(chunk.name)
		chunk.data = self.readFloats(2*count)

	def read3fAtr(self, chunk):
		chunk.name, mystery = self.readAttributeInfo()
		count = getElementCount(chunk.name)
		chunk.data = self.readFloats(3*count)

	def read3dAtr(self, chunk):
		chunk.name, mystery = self.readAttributeInfo()
		count = getElementCount(chunk.name)
		chunk.data = self.readDoubles(3*count)

	def readFloatCount(self):
		cnt = self.readInt()
		return self.readFloats(cnt)

	def readFloat3Count(self):
		cnt = self.readInt()
		values = self.readFloats(cnt)
		return numpy.reshape(values, (cnt/3, 3))

	def readIntCount(self):
		cnt = self.readInt()
		return self.readInts(cnt)

	def readShort4Count(self):
		cnt = self.readInt()
		return self.readShorts(2 * cnt)

	def readShort2Count(self):
		cnt = self.readInt()
		return self.readShorts(2 * cnt)

	def readMesh(self, chunk):
		chunk.name, mystery = self.readAttributeInfo()
		vt   = self.readFloat3Count()# Vertex coordinates (x1, y1, z1, x2, y2, z2, ...)
		ed   = self.readShort4Count()# Edges (f1, i1, f2, i2, i3) <=> f_i: 0x8000 -> new Edge
		fc   = self.readShort2Count()# n x (Flg, EdgeIndex) Flag: 0x8000 -> reverse edge direction, 0x6000 -> end of N-Gon
		lst4 = self.readFloatCount() #
		lst5 = self.readInts(3)
		map  = self.readNullTerminated()
		lst6 = self.readFloatCount() # Texture coordinates (x1, y1, x2, y2, ...)
		lst7 = self.readIntCount()   # Texture indices     (t1, t2, t3, ...)
		lst8 = self.readInts(3)
		chunk.data = (map, vt, ed, fc, lst4, lst5, lst6, lst7, lst8)

	def readUnknown(self, chunk):
		chunk.data = None

	def readNext(self, level = 0):
		next = None
		if (self.pos < len(self.data)):
			type = self.readTypeID()
			if (type in ALIGNMENT.keys()):
				self.alignment = ALIGNMENT[type]
				size = self.readSize()
				id   = self.readTypeID()
				next = Container(type, id, self.pos, size, level)
				self.current = next
				if (DEBUG): print next
				self.analyseContainer(next)
			else:
				size = self.readSize()
				next = Chunk(type, self.pos, size, level, self.data[self.pos: self.pos+size])
				method = ReaderMB.__dict__.get(KNOWN_METHODS.get(type), ReaderMB.readUnknown)
				pos = self.pos
				method(self, next)
				if (self.pos < pos+size):
					if (DEBUG): print "%s - Bytes not read: %s"%(type, ":".join(["%02X" %(ord(c)) for c in self.data[self.pos:pos+size]]))
				self.pos = pos + size
				if (size % self.alignment):
					self.pos += self.alignment - (size % self.alignment) # add padding bytes due to alignment
				if (DEBUG): print next
		return next

	def analyseContainer(self, container):
		while (self.pos < (container.pos + container.size - 4)):
			next = self.readNext(container.level + 1)
			container.children.append(next)
			if (next is None): break

	def start(self, msg, cnt):
		self.progress = FreeCAD.Base.ProgressIndicator()
		self.progress.start("%s ..." %(msg), cnt)
		self.procressValue = 0

	def update(self):
		if (self.progress):
			i = self.pos - self.procressValue
			self.procressValue = self.pos
			while (i>0):
				self.progress.next()
				i -= 1

	def stop(self):
		if (self.progress is not None):
			self.progress.stop()
		self.progress = None

def getElementCount(name):
	lbracket = name.rfind("[")
	if lbracket != -1:
		rbracket = name.rfind("]")
		if rbracket != -1 and lbracket < rbracket:
			slicestr = name[lbracket + 1:rbracket]
			bounds = slicestr.split(":")
			if len(bounds) > 1:
				return int(bounds[1]) - int(bounds[0]) + 1
	return 1

def getIndices(msh):
	values = msh.data[2]
	ed = numpy.reshape(values, (len(values)/4, 4))
	values = msh.data[3]
	fc = numpy.reshape(values, (len(values)/2, 2))
	indices = []
	i = 0
	ngon = []
	while (i < len(fc)):
		flg = fc[i][0]
		idx = fc[i][1]
		f2 = fc[i][0]
		e2 = fc[i][1]
		e = ed[idx]
		if (flg & 0x8000 != 0): # inverse line direction?
			ngon.append(e[3])
		else:
			ngon.append(e[1])
		if (flg & 0x6000 != 0): # Reached end of face?
			indices.append(ngon)
			ngon = []
		i += 1
	return indices

def createObject(doc, dmsh):
	FreeCAD.Console.PrintMessage("Adding '%s' " %(dmsh.name))
	xfrm = dmsh.parent
	mtx = xfrm.getMatrix()
	msh = dmsh.getPropertyId('MESH')
	if (msh is not None):
		vt = msh.data[1]
		indices = getIndices(msh)
		cnt = len(vt)
		# translate the points according to the transformation matrix
		pt = numpy.ones((cnt, 4), numpy.float32)
		pt[:,:3] = vt
		tpt = numpy.transpose(numpy.dot(mtx, numpy.transpose(pt)))

		if (len(indices) > 0):
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
				obj = newObject(doc, dmsh.name, data)
			else:
				FreeCAD.Console.PrintWarning("... no faces ... ")
	else:
		FreeCAD.Console.PrintWarning("... failed - Unknown mesh format at %X " %(dmsh.pos))
	FreeCAD.Console.PrintMessage("Done!\n")

def read(doc, fileName):
	'''
	Read the binary Maya file.
	'''
	with open(fileName, 'rb') as file:
		data = file.read()
		reader = ReaderMB(data)
		try:
			reader.start("Reading file", len(data))
			next = reader.readNext()
			while (next is not None):
				next = reader.readNext()
			reader.stop()

			reader.start("builing meshes", len(reader.containers))
			for key, container in reader.containers.items():
				reader.progress.next()
				if (container.id == 'DMSH'):
					createObject(doc, container)
		finally:
			reader.stop()
