# -*- coding: utf8 -*-

import os
import FreeCAD
import Chunks

__title__="FreeCAD Autodesk 3DS Max importer"
__author__ = "Jens M. Plonka"
__url__ = "https:#www.github.com/jmplonka/Import3DS"

def decode(name):
	"decodes encoded strings"
	try:
		decodedName = (name.decode("utf8"))
	except UnicodeDecodeError:
		try:
			decodedName = (name.decode("latin1"))
		except UnicodeDecodeError:
			FreeCAD.Console.PrintError("Error: Couldn't determine character encoding")
			decodedName = name
	return decodedName

def read(doc, filename):
	reader = Chunks.Importer(doc, filename)
	chunkId = reader.getChunkId2()
	chunkLen = reader.getChunkLen4() - 6
	if (chunkId == Chunks.MAIN):
		chunk = reader.createChunk(chunkId, chunkLen)
		reader.loadSubChunks(chunk, chunkLen)
	reader.close()
	return

def insert(filename, docname):
	'''
	Called when freecad wants to import a file into an existing project.
	'''
	try:
		doc = FreeCAD.getDocument(docname)
	except NameError:
		doc = FreeCAD.newDocument(docname)
	FreeCAD.ActiveDocument = doc
	read(doc, filename)
	return doc

def open(filename):
	'''
	Called when freecad wants to open a file as a new project.
	'''
	docname = (os.path.splitext(os.path.basename(filename))[0]).encode("utf8")
	doc = FreeCAD.newDocument(docname)
	doc.Label = decode(docname)
	FreeCAD.ActiveDocument = doc
	read(doc, filename)
	return doc

if __name__ == '__main__':
	open('C:/Users/pln2si/Documents/NOTE/3d/heroic-women-fantasy-adventure.3DS')
