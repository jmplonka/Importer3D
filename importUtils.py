# -*- coding: utf8 -*-

__title__  = "Collection of utilities for 3D Mesh importers"
__author__ = "Jens M. Plonka"
__url__    = "https://www.github.com/jmplonka/Importer3D"

import re, Mesh, FreeCAD

from struct     import unpack
from os.path    import join, dirname, basename
from sys        import executable
from subprocess import call

INVALID_NAME = re.compile('^[0-9].*')

_can_import  = True
BIG_ENDIAN = '>'
LITTLE_ENDIAN = '<'
ENDIANNESS = BIG_ENDIAN

CENTER = FreeCAD.Vector(0.0, 0.0, 0.0)
DIR_X  = FreeCAD.Vector(1.0, 0.0, 0.0)
DIR_Y  = FreeCAD.Vector(0.0, 1.0, 0.0)
DIR_Z  = FreeCAD.Vector(0.0, 0.0, 1.0)

def setEndianess(endianess):
	global ENDIANNESS
	ENDIANNESS = endianess

def setCanImport(canImport):
	global _can_import
	_can_import = canImport
	return

def canImport():
	global _can_import
	return _can_import

def missingDependency(module):
	python = join(dirname(executable), basename(executable).replace('FreeCAD', 'python'))
	call(u"\"%s\" -m pip install \"%s\"" %(python, module))
	FreeCAD.Console.PrintWarning("DONE!\n")
	setCanImport(False)

def getValidName(name):
	if (INVALID_NAME.match(name)): return "_%s"%(name.encode('utf8'))
	return "%s"%(name.encode('utf8'))

def newObject(doc, name, data):
	obj = doc.addObject('Mesh::Feature', getValidName(name))
	if (obj):
		obj.Label = name
		obj.Mesh = Mesh.Mesh(data)
		obj.ViewObject.Lighting = "Two side"
	return obj

def newGroup(parent, name):
	if (INVALID_NAME.match(name)):
		obj = parent.addObject('Part::Feature', '_' + name.encode('utf8'))
	else:
		obj = parent.addObject('Part::Feature', name.encode('utf8'))
	if (obj):
		obj.Label = name
	return obj

def _get(data, fmt, size, offset):
	end = offset + size
	value, = unpack(ENDIANNESS + fmt, data[offset:end])
	return value, end

def _gets(data, fmt, size, offset, count):
	end = offset + (count * size)
	values = unpack(ENDIANNESS + fmt*count, data[offset:end])
	return values, end

def getFloat(data, offset): return _get(data, 'f', 4, offset)
def getInt(data, offset):   return _get(data, 'i', 4, offset)
def getShort(data, offset): return _get(data, 'H', 2, offset)
def getByte(data, offset):  return _get(data, 'B', 1, offset)

def getFloats(data, offset, count): return _gets(data, 'f', 4, offset, count)
def getInts(data, offset, count):   return _gets(data, 'i', 4, offset, count)
def getShorts(data, offset, count): return _gets(data, 'H', 2, offset, count)
def getBytes(data, offset, count):  return _gets(data, 'B', 1, offset, count)
