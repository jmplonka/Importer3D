# -*- coding: utf8 -*-

__title__  = "Collection of 3D Mesh importers"
__author__ = "Jens M. Plonka"
__url__    = "https://www.github.com/jmplonka/Importer3D"

## FreeCAD importers:
FreeCAD.addImportType("LightWave Object (*.lwo)", "importer3D")
FreeCAD.addImportType("3D Studio Max (*.3ds)", "importer3D") # there exists an other reader from Yorik in Arch-WB
FreeCAD.addImportType("3D Studio Max (*.max)", "importer3D")
FreeCAD.addImportType("GSkin-Mesh (*.gsm)", "importer3D")
FreeCAD.addImportType("Maya binary (*.mb)", "importer3D")
#FreeCAD.addImportType("Maya ASCII (*.ma)", "importer3D")

## FreeCAD exporters:
