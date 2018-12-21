
# -*- coding: utf-8 -*-
"""
/***************************************************************************
ArcGIS REST API Connector
A QGIS plugin
                              -------------------
        begin                : 2015-05-27
        git sha              : $Format:%H$
        copyright            : (C) 2015 by geometalab
        email                : geometalab@gmail.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
from qgis.core import QgsMessageLog
import os
import resources_rc
from arcgiscon_service import FileSystemService
from PyQt4 import QtGui, uic
import PyQt4

FORM_CLASS_NEW, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'arcgiscon_dialog_new.ui'))

TIME_FORM, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'timeinput_dialog.ui'))

SETTINGS_FORM, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'settings.ui'))
DASHBOARD_WINDOW, _ = uic.loadUiType(os.path.join(
os.path.dirname(__file__), 'image_server_dashboard.ui'))

LAYER_DIALOG, _ = uic.loadUiType(os.path.join(
os.path.dirname(__file__), 'new_layer_dialog.ui'))

IMAGE_ITEM, _ = uic.loadUiType(os.path.join(
os.path.dirname(__file__), 'image_item.ui'))

service = FileSystemService()


class ArcGisConDialogNew(QtGui.QDialog, FORM_CLASS_NEW):
    def __init__(self, parent=None):        
        super(ArcGisConDialogNew, self).__init__(parent)        
        self.setupUi(self)        


class TimePickerDialog(QtGui.QDialog, TIME_FORM):
    def __init__(self, parent=None):
        super(TimePickerDialog, self).__init__(parent)
        self.setupUi(self)


class SettingsDialog(QtGui.QDialog, SETTINGS_FORM):
    def __init__(self, parent=None):
        super(SettingsDialog, self).__init__(parent)
        self.setupUi(self) 


class ImageServerDashboard(QtGui.QMainWindow, DASHBOARD_WINDOW):
    def __init__(self, parent=None):        
        super(ImageServerDashboard, self).__init__(parent)        
        self.setupUi(self)


class LayerDialog(QtGui.QDialog, LAYER_DIALOG):
    scrolledDown = PyQt4.QtCore.pyqtSignal([int])
    closed = PyQt4.QtCore.pyqtSignal()


    def __init__(self, parent=None):        
        super(LayerDialog, self).__init__(parent)        
        self.setupUi(self)  
        self.imageGridWidget.layout().setSpacing(50)


    def wheelEvent(self, wheelEvent):
        if wheelEvent.delta() < -1:        
            self.scrolledDown.emit(wheelEvent.y)
        wheelEvent.ignore()


    def clearLayout(self,layout):
        for i in reversed(range(layout.count())): 
            widgetToRemove = layout.itemAt(i).widget()
            # remove it from the layout list
            layout.removeWidget(widgetToRemove)
            # remove it from the gui
            widgetToRemove.setParent(None)


    def closeEvent(self, event):
        self.clearLayout(self.scrollArea.widget().layout())
        self.closed.emit()
        super(LayerDialog, self).closeEvent(event)


class ImageLabel(QtGui.QLabel):
    labelSize = None


    def __init__(self, parent):
        super(ImageLabel, self).__init__(parent)

    def setSizeHint(self, size):
        self.labelSize = size
 
    def sizeHint(self):
        return self.labelSize

    def minimumSizeHint(self):
        return self.labelSize


class ImageItemWidget(QtGui.QWidget):
    imageDateLabel = None
    thumbnailLabel = None
    widgetSize = None
    clicked = PyQt4.QtCore.pyqtSignal()

    def __init__(self, parent, width, height):
        super(ImageItemWidget, self).__init__(parent)
        self.initUI(width, height)
        

    def mouseReleaseEvent(self, event):
        self.clicked.emit()
        event.accept()

    def setSizeHint(self, size):
        self.widgetSize = size

    def sizeHint(self):
        return self.widgetSize
    
    def minimumSizeHint(self):
        return self.widgetSize

    def initUI(self, width, height):
        layout = QtGui.QVBoxLayout(self)
        layout.setContentsMargins(2,2,2,2)
        layout.setSizeConstraint(QtGui.QLayout.SetNoConstraint)
   
        self.imageDateLabel = ImageLabel(self)
        self.thumbnailLabel = ImageLabel(self)
        self.layout().addWidget(self.thumbnailLabel)
        self.layout().addWidget(self.imageDateLabel) 
 
        self.setAutoFillBackground(True)
        self.setLayout(layout)
        self.setAttribute(PyQt4.QtCore.Qt.WA_StyledBackground)
        self.styleFromFile(self, "gui/styleSheets/ImageItemWidget.qss")
        
        self.configureChildren()
        self.configureFromDimensions(width, height)

    def configureChildren(self):

        self.imageDateLabel.setText("2018-11-04")
        self.styleFromFile(self.thumbnailLabel, "gui/styleSheets/thumbnailLabel.qss")
        self.styleFromFile(self.imageDateLabel, "gui/styleSheets/imageItemLabel.qss")


    # Public function for adapting the widget size to the thumbnail image's dimensions. 
    # Where thumbnailDimensions is a list [width, height]
    def configureFromDimensions(self, width, height):
       
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Fixed, QtGui.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)

        thumbnailSize = PyQt4.QtCore.QSize(width, height)
        labelSize = PyQt4.QtCore.QSize(width, 50)
        widgetSize = PyQt4.QtCore.QSize(width + 4, height + labelSize.height())

        self.thumbnailLabel.setFixedSize(thumbnailSize)
        self.thumbnailLabel.setSizeHint(thumbnailSize)
        self.thumbnailLabel.setSizePolicy(sizePolicy)

        self.imageDateLabel.setFixedSize(labelSize)
        self.imageDateLabel.setSizeHint(labelSize)
        self.imageDateLabel.setSizePolicy(sizePolicy)
       
        self.setFixedSize(widgetSize)
        self.setSizeHint(widgetSize)
        self.setSizePolicy(sizePolicy)
        self.repaint()
        self.imageDateLabel.repaint()
        self.thumbnailLabel.repaint()

    # Shorthand for setting stylesheet from file.
    def styleFromFile(self, widget, src):
        widget.setStyleSheet(service.openFile(src))

    # For Debug purposes
    def logSizeInfo(self):  
        QgsMessageLog.logMessage("Size info")
        QgsMessageLog.logMessage("size downloaded image: " + "[" + str(thumbnailWidth) + ", " + str(thumbnailHeight) + "]")
        
        QgsMessageLog.logMessage("max widget: " + "[" + str(self.maximumWidth()) + ", " + str(self.maximumHeight()) + "]")
        QgsMessageLog.logMessage("min  widget: " + "[" + str(self.minimumWidth()) + ", " + str(self.minimumHeight()) + "]")
        
        QgsMessageLog.logMessage("max label: " + "[" + str(self.imageDateLabel.maximumWidth()) + ", " + str(self.imageDateLabel.maximumHeight()) + "]")
        QgsMessageLog.logMessage("min  label: " + "[" + str(self.imageDateLabel.minimumWidth()) + ", " + str(self.imageDateLabel.minimumHeight()) + "]")
       
        QgsMessageLog.logMessage("max thumbnail: " + "[" + str(self.thumbnailLabel.maximumWidth()) + ", " + str(self.thumbnailLabel.maximumHeight()) + "]")
        QgsMessageLog.logMessage("min  thumbnail: " + "[" + str(self.thumbnailLabel.minimumWidth()) + ", " + str(self.thumbnailLabel.minimumHeight()) + "]")
        
        QgsMessageLog.logMessage("width/height widget: " + "[" + str(self.width()) + ", " + str(self.height()) + "]")
        QgsMessageLog.logMessage("width/height label: " + "[" + str(self.imageDateLabel.width()) + ", " + str(self.imageDateLabel.height()) + "]")
        QgsMessageLog.logMessage("width/height thumbnail: " + "[" + str(self.thumbnailLabel.width()) + ", " + str(self.thumbnailLabel.height()) + "]")

        QgsMessageLog.logMessage("geometry widget: " + str(self.geometry()))
        QgsMessageLog.logMessage("geometry label: " + str(self.imageDateLabel.geometry()))
        QgsMessageLog.logMessage("geometry thumbnail: " + str(self.thumbnailLabel.geometry()))

        QgsMessageLog.logMessage("sizehint widget: " + str(self.sizeHint()))
        QgsMessageLog.logMessage("sizehint label: " + str(self.imageDateLabel.sizeHint()))
        QgsMessageLog.logMessage("sizehint thumbnail: " + str(self.thumbnailLabel.sizeHint()))
        QgsMessageLog.logMessage("\n \n")

           
