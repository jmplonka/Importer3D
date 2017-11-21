# -*- coding: utf8 -*-

__title__  = "Collection of 3D Mesh importers"
__author__ = "Jens M. Plonka"
__url__    = "https://www.github.com/jmplonka/Importer3D"

import os, FreeCAD, import3DS, importLWO, importMAX

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
	ext = filename[-4:].lower()
	if (ext == '.lwo'):
		importLWO.read(doc, filename)
	elif (ext == '.3ds'):
		import3DS.read(doc, filename)
	elif (ext == '.max'):
		importMAX.read(doc, filename)
	else:
		FreeCAD.Console.PrintError("No suitable reader found for ext=%s\n" %(ext))
	return

def insert(filename, docname):
	'''
	Called when freecad wants to import a file into an existing project.
	'''
	try:
		doc = FreeCAD.getDocument(docname)
		FreeCAD.ActiveDocument = doc
		read(doc, filename)
		return doc
	except:
		return open(filename)

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
