# -*- coding: utf8 -*-

__title__="FreeCAD Autodesk 3DS Max importer"
__author__ = "Jens M. Plonka"
__url__ = "https://www.github.com/jmplonka/Importer3D"

def read(doc, filename):
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
