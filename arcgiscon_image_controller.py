from __future__ import absolute_import

from PyQt5.QtCore import QObject
from PyQt5.QtWidgets import QFileDialog

from .arcgiscon_service import FileSystemService
import os.path


class ImageController(QObject):
    _iface = None

    def __init__(self, iface):
        self._iface = iface

    def saveImage(self, srcPath):
        fileExt = os.path.splitext(srcPath)[1]
        dstPath = QFileDialog.getSaveFileName(caption='Save layer as image', filter='*' + fileExt)
        if len(dstPath) > 0:
            FileSystemService().saveImageAs(srcPath, dstPath)
