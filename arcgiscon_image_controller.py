from __future__ import absolute_import
from qgis.PyQt import QtGui
from qgis.PyQt.QtCore import QObject
from qgis.core import QgsMessageLog
from .arcgiscon_service import FileSystemService
import os.path

class ImageController(QObject):
    _iface = None

    def __init__(self, iface):
        self._iface = iface

    def saveImage(self, srcPath):
        fileExt = os.path.splitext(srcPath)[1]
        dstPath = QtGui.QFileDialog.getSaveFileName(caption = 'Save layer as image', filter = '*' + fileExt)
        if len(dstPath) > 0:
            FileSystemService().saveImageAs(srcPath, dstPath)
