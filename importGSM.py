# -*- coding: utf8 -*-

__title__  = "FreeCAD Maya file importer"
__author__ = "Jens M. Plonka"

import sys, shlex, struct, FreeCAD, numpy
from importUtils import newObject, getShort, getInt, setEndianess, LITTLE_ENDIAN

class GsmHeader():
	def __init__(self):
		self.length     = 0x28
		self.blocks = []

class GsmMySg():
	def __init__(self):
		self.length = 0x08

class GsmDaeH():
	def __init__(self):
		self.length = 0x50

class GsmBlockHeader():
	def __init__(self):
		self.length      = 0x10
		self.blockPos    = 0
		self.blockLength = 0
		self.key = None

class GsmBlock():
	def __init__(self, data, bHdr):
		self.pos = bHdr.blockPos + 4
		self.key = data[bHdr.blockPos:self.pos]
		self.subName = data[self.pos:self.pos + 2]
		self.subKey, self.pos  = getShort(data, self.pos + 2)
		self.size, self.pos    = getInt(data, self.pos)
		self.version, self.pos = getInt(data, self.pos)

class GsmCsd1(GsmBlock):
	def __init__(self, data, bHdr): GsmBlock.__init__(self, data, bHdr)

class GsmCsd2(GsmBlock): # Lines
	def __init__(self, data, bHdr): GsmBlock.__init__(self, data, bHdr)

class GsmCsd3(GsmBlock):
	def __init__(self, data, bHdr):
		GsmBlock.__init__(self, data, bHdr)
		end = bHdr.blockPos + bHdr.blockLength
		if (data[bHdr.blockPos + 0x10:bHdr.blockPos + 0x13] == '\xEF\xBB\xBF'):
			self.text = data[bHdr.blockPos + 0x13:end].decode('cp1252')
		else:
			self.text = data[bHdr.blockPos + 0x10:end].decode('cp1252')

class GsmCsiu(GsmBlock):
	def __init__(self, data, bHdr): GsmBlock.__init__(self, data, bHdr)

class GsmCslv(GsmBlock):
	def __init__(self, data, bHdr): GsmBlock.__init__(self, data, bHdr)

class GsmCsrp(GsmBlock):
	def __init__(self, data, bHdr): GsmBlock.__init__(self, data, bHdr)

class GsmDrapInfo():
	def __init__(self, data, pos):
		self.pos = bHdr.blockPos + 4
		self.key = data[bHdr.blockPos:self.pos]
		self.varType, self.pos = readShort(data, self.pos)
		if (self.varType == 0x02):
			self.bytes = data[self.pos:self.pos + 0x12]
			self.pos += 0x12
			self.value, self.pos = readFloat(data, self.pos)
		elif (self.varType == 0x04):
			self.bytes = data[self.pos:self.pos + 0x0A]
			self.pos += 0x0A
			r, self.pos = readFloat(data, self.pos)
			g, self.pos = readFloat(data, self.pos)
			b, self.pos = readFloat(data, self.pos)
			self.value = (r, g, b)
		elif (self.varType == 0x0d):
			self.bytes = readBytes(0x12);
			self.bytes = data[self.pos:self.pos + 0x12]
			self.pos += 0x12
			self.value, self.pos = readInt(data, self.pos)
			self.value = (self.value != 0)
		elif (self.varType == 0x0f):
			self.bytes = data[self.pos:self.pos + 0x12]
			self.pos += 0x12
			self.value, self.pos = readInt(data, self.pos)
		else:
			self.bytes = data[self.pos:self.pos + 0x16]
			self.pos += 0x16
			self.value = None
		self.name = data[self.pos:self.pos + 0x20].decode('utf8')
		self.pos = self.pos + 0x20
		i = self.name.find('\0')
		if (i != -1): self.name = self.name[0:i]
		self.flag1, self.pos = readInt(data, self.pos);
		self.flag2, self.pos = readInt(data, self.pos)

class GsmDrap(GsmBlock):
	def __init__(self, data, bHdr):
		GsmBlock.__init__(self, id, l)
		self.count, self.pos = getShort(data, bHdr.blockPos + 0x32)
		self.infos = {}
		self.pos = bHdr.blockPos + 0x80
		i = self.count
		while (i > 0):
			info = GsmDrapInfo(data, self.pos)
			self.pos += 0x40
			self.infos[info.key] = info
			i -= 1
		txt = data[self.pos, bHdr.blockPos + bHdr.blockLength].decode('UTF-16LE')
		self.strings = txt.split('\0')

class GsmFfig(GsmBlock):
	def __init__(self, data, bHdr): GsmBlock.__init__(self, id, l)

class GsmScna(GsmBlock):
	def __init__(self, data, bHdr): GsmBlock.__init__(self, id, l)

class GsmSrcm(GsmBlock):
	def __init__(self, data, bHdr): GsmBlock.__init__(self, id, l)

class GsmTxtc(GsmBlock):
	def __init__(self, data, bHdr): GsmBlock.__init__(self, id, l)

def readGsmHeader(data):
	header = GsmHeader()
	header.magic        = data[0:2]
	header.version, pos = getShort(data, 2)
	header.name         = data[pos:pos+0x20]
	count, pos          = getInt(data, pos + 0x20)
	header.mySg, pos    = readGsmMySg(data, pos)
	header.daeH, pos    = readGsmDaeH(data, pos)

	i = 0
	while i < count:
		bHdr, pos = readGsmBlockHeader(data, pos)
		header.blocks.append(bHdr)
		i += 1
	return header, pos

def readGsmMySg(data, pos):
	mySg = GsmMySg()
	mySg.key      = data[pos:pos + 0x04].decode('cp1252')
	mySg.val, pos = getInt(data, pos + 4)
	return mySg, pos

def readGsmDaeH(data, pos):
	daeH = GsmDaeH()
	daeH.key         = data[pos:pos + 0x04].decode('cp1252')
	daeH.offset, pos = getInt(data, pos + 4)
	daeH.length, pos = getInt(data, pos)
	daeH.data        = data[pos:pos+0x44]
	return daeH, pos + 0x44

def readGsmBlockHeader(data, pos):
	bHdr = GsmBlockHeader()
	ofs  = pos + 4
	bHdr.key = data[pos:ofs].decode('utf8')
	bHdr.blockPos, ofs    = getInt(data, ofs)
	bHdr.blockLength, ofs = getInt(data, ofs)
	bHdr.flags, ofs       = getInt(data, ofs)
	return bHdr, pos + bHdr.length

def readGsmBlock(data, bHdr):
	#if (bHdr.key == 'CSD1'): return GsmCsd1(data, bHdr)
	#if (bHdr.key == 'CSD2'): return GsmCsd2(data, bHdr) # Lines
	if (bHdr.key == 'CSD3'): return GsmCsd3(data, bHdr)
	#if (bHdr.key == 'CSIU'): return GsmCsiu(data, bHdr)
	#if (bHdr.key == 'CSLV'): return GsmCslv(data, bHdr)
	#if (bHdr.key == 'CSRP'): return GsmCsrp(data, bHdr)
	#if (bHdr.key == 'DRAP'): return GsmDrap(data, bHdr)
	#if (bHdr.key == 'FFIG'): return GsmFfig(data, bHdr) #Thumbnail
	#if (bHdr.key == 'SCNA'): return GsmScna(data, bHdr)
	#if (bHdr.key == 'SRCM'): return GsmSrcm(data, bHdr)
	#if (bHdr.key == 'TXTC'): return GsmTxtc(data, bHdr)
	return None

def getFloat(st):
	f = st.get_token()
	try:
		return float(f)
	except:
		raise Exception("Can't convert '%s' to float!" %(f))

def getInteger(st): return int(st.get_token())
def getColor(st):
	r = getFloat(st)
	g = getFloat(st)
	b = getFloat(st)
	return (r, g, b)
class GsmMaterial():
	def __init__(self):
		self.name = None
		self.number = -1

class GsmReader():
	def __init__(self):
		self.currentName = None
		self.materials   = None
		self.vertexList  = None
		self.textureList = None
		self.edgeList    = None
		self.faceList    = None
		self.model       = None
		self.material    = None
		self.mat_block   = 0
		self.currentMaterial = None

	def resetMaterial(self):
		self.mat_block = 0
		if (self.material is not None):
			self.materials[self.material.name] = self.material
			self.material = None

	def readBase(self, st):
		self.resetMaterial()
		self.textureList = []
		self.vertexList  = []
		self.edgeList    = []
		self.faceList    = []

	def adjustMaterial(self, mesh):
		if (self.material is not None):
			amb = self.currentMaterial.ambient
			dif = self.currentMaterial.diffuse
			mesh.ViewObject.ShapeMaterial.AmbientColor  = (amb, amb, amb)
			mesh.ViewObject.ShapeMaterial.DiffuseColor  = (dif, dif, dif)
			mesh.ViewObject.ShapeMaterial.EmissiveColor = self.currentMaterial.emissionRGB
			mesh.ViewObject.ShapeMaterial.SpecularColor = self.currentMaterial.specularRGB
			mesh.ViewObject.ShapeMaterial.Shininess     = self.currentMaterial.shining
			mesh.ViewObject.ShapeMaterial.Transparency  = self.currentMaterial.transparency

	def getFaces(self):
		faces = []
		for i in self.faceList:
			i0 = i[0]
			i1 = i[1]
			i2 = i[2]

			if (i0 < 0):
				e0 = self.edgeList[-i0 - 1]
				idx0 = e0[1] - 1
				idx1 = e0[0] - 1
			else:
				e0 = self.edgeList[i0 - 1]
				idx0 = e0[0] - 1
				idx1 = e0[1] - 1
			if (i1 < 0):
				e1 = self.edgeList[-i1 - 1]
				idx2 = e1[0] - 1
			else:
				e1 = self.edgeList[i1 - 1]
				idx2 = e1[1] - 1
			faces.append([idx0, idx1, idx2])
		return faces

	def readBody(self, st, doc):
		self.resetMaterial()
		number = getInteger(st)

		if (len(self.vertexList) > 0):
			data = []
			faces = self.getFaces()
			for f in faces:
				p0 = self.vertexList[f[0]]
				p1 = self.vertexList[f[1]]
				p2 = self.vertexList[f[2]]
				data.append([p0, p1, p2])
			mesh = newObject(doc, self.currentName, data)
			self.adjustMaterial(mesh)


	def readDefine(self, st):
		# DEFINE MATERIAL "name" 0,
		# 0.713726, 0.482353, 0.403922, !surface RGB [0.0..1.0]x3
		# 0.650000, 0.800000, 0.900000, 0.000000, !ambient, diffuse, specular, transparent coefficients [0.0..1.0]x4
		# 2.000000, !shining [0.0..100.0]
		# 1.000000, !transparency attenuation [0.0..4.0]
		# 0.086275, 0.086275, 0.086275, !specular RGB [0.0..1.0]x3
		# 0.000000, 0.000000, 0.000000, !emission RGB [0.0..1.0]x3
		# 0.000000
		#
		if (self.mat_block == 0):
			tok = st.get_token()
			if (tok == 'MATERIAL'):
				self.material = GsmMaterial()
				self.material.name = st.get_token()
				self.material.number = getInteger(st)
				self.mat_block = 1
			elif (tok == 'TEXTURE'):
				self.mat_block = -1
			else:
				raise Exception("Unknown Token '%s' in DEFINE!" %(tok))

		elif (self.mat_block == 1):
			self.material.ambient = getFloat(st)
			self.material.diffuse = getFloat(st)
			self.material.specular = getFloat(st)
			self.mat_block = 2
			return

		elif (self.mat_block == 2):
			self.material.transparent = getFloat(st)
			self.mat_block = 3
			return

		elif (self.mat_block == 3):
			self.material.shining = getFloat(st)
			self.mat_block = 4
			return

		elif (self.mat_block == 4):
			self.material.transparencyAttentuation = getFloat(st)
			self.mat_block = 5
			return

		elif (self.mat_block == 5):
			self.material.specularRGB = getColor(st)
			self.mat_block = 6
			return

		elif (self.mat_block == 6):
			self.material.emissionRGB = getColor(st)
			self.mat_block = 7
			return

		elif (self.mat_block == 7):
			self.material.emissionAttentuation = getFloat(st)
			self.resetMaterial()
			return

		elif (self.mat_block != -1):
			raise Exception("Unrecognized token in DEFINE: '%s'!" %(tok))

	def readEdge(self, st):
		# EDGE 1, 2, 1, 17, 2 !#1
		self.resetMaterial()
		p1 = getInteger(st)
		p2 = getInteger(st)
		a  = getInteger(st)
		b  = getInteger(st)
		c  = getInteger(st)
		self.edgeList.append((p1, p2, a, b, c))

	def readMaterial(self, st):
		self.resetMaterial()
		name = st.get_token()
		mat = self.materials.get(name)
		if (mat is not None):
			self.currentMaterial = mat

	def readModel(self, st):
		# MODEL SURFACE
		self.resetMaterial()
		self.model = st.get_token()

	def readPolygon(self, st):
		# PGON 3, 0, 2, 1, 2, 3
		self.resetMaterial()
		a = getInteger(st)
		b = getInteger(st)
		c = getInteger(st)
		d = getInteger(st)
		e = getInteger(st)
		f = getInteger(st)

		self.faceList.append([d, e, f])

	def readTextureVertex(self, st):
		self.readVertex(st)

		x = getFloat(st)
		y = getFloat(st)

		self.textureList.append([x, y])

	def readVertex(self, st):
		self.resetMaterial()
		x = getFloat(st)
		y = getFloat(st)
		z = getFloat(st)

		self.vertexList.append([x, y, z])

	def readComment(self, st):
		tok = st.get_token()
		if (len(tok) > 0):
			if (tok == 'Mesh'):
				tok = st.get_token()
				if (tok == 'name'):
					tok = st.get_token() # skip ':'
					self.currentName = st.get_token()

	def read(self, doc, csd3):
		self.materials = {}
		self.vertexList = []
		self.textureList = []
		self.edgeList = []
		self.faceList = []
		lines = csd3.text.splitlines()
		progressbar = FreeCAD.Base.ProgressIndicator()
		progressbar.start("  reading ...", len(lines))
		try:
			for line in lines:
				progressbar.next()
				st = shlex.shlex(line.strip())
				st.wordchars += '.-'
				st.whitespace += ','
				tok = st.get_token()
				if (tok == ''): pass
				elif (tok == 'BASE'):      self.readBase(st)
				elif (tok == 'BODY'):      self.readBody(st, doc)
				elif (tok == 'COOR'):      self.resetMaterial()
				elif (tok == 'DEFINE'):    self.readDefine(st)
				elif (tok == 'EDGE'):      self.readEdge(st)
				elif (tok == 'ELSE'):      self.resetMaterial()
				elif (tok == 'ENDIF'):     self.resetMaterial()
				elif (tok == 'hotspot'):   self.resetMaterial()
				elif (tok == 'IF'):        pass
				elif (tok == 'material'):  self.readMaterial(st)
				elif (tok == 'min'):       pass
				elif (tok == 'MODEL'):     self.readModel(st)
				elif (tok == 'MUL'):       self.resetMaterial()
				elif (tok == 'PEN'):       self.resetMaterial()
				elif (tok == 'PGON'):      self.readPolygon(st)
				elif (tok == 'TEVE'):      self.readTextureVertex(st)
				elif (tok == 'VERT'):      self.readVertex(st)
				elif (tok == '!'):         self.readComment(st)
				else:
					if (self.mat_block != 0):
						st.push_token(tok)
						self.readDefine(st)
					else:
						raise Exception("Unrecognized token '%s' (mat_block=%d)" %(tok, self.mat_block))
		except:
			pass
		progressbar.stop()

def read(doc, fileName):
	with open(fileName, 'rb') as file:
		setEndianess(LITTLE_ENDIAN)
		data = file.read()
		hdr, pos  = readGsmHeader(data)
		blocks = {}
		for bHdr in hdr.blocks:
			block = readGsmBlock(data, bHdr)
			blocks[bHdr.key] = block
		reader = GsmReader()
		reader.read(doc, blocks.get('CSD3'))

if __name__ == '__main__':
	if (len(sys.argv) > 1):
		print(sys.argv[1])
		read(FreeCAD.ActiveDocument, sys.argv[1])
	else:
		read(FreeCAD.ActiveDocument, u"D:/documents/NOTE/3d/ArmChair/Armchair fotel b6500.gsm")
		#read(FreeCAD.ActiveDocument, u"D:/documents/NOTE/3d/motorristja.gsm")
