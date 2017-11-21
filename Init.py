# -*- coding: utf8 -*-

__title__  = "Collection of 3D Mesh importers"
__author__ = "Jens M. Plonka"
__url__    = "https://www.github.com/jmplonka/Importer3D"

## FreeCAD importers:
FreeCAD.addImportType("LightWave Object (*.lwo)", "importer")
FreeCAD.addImportType("3D Studio Max (*.3ds)", "importer") # there exists an other reader from Yorik in Arch-WB
FreeCAD.addImportType("3D Studio Max (*.max)", "importer")
#FreeCAD.addImportType("GSkin-Mesh (*.gsm)", "importer")
#FreeCAD.addImportType("Autodesk binary Maya (*.md)", "importer")

## FreeCAD exporters:
