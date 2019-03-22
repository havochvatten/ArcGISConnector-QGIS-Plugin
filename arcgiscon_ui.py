
# -*- coding: utf-8 -*-
from __future__ import absolute_import
from builtins import range
import os
from .arcgiscon_service import FileSystemService
from PyQt5.QtWidgets import QDialog, QMainWindow, QLabel, QWidget, \
    QVBoxLayout, QLayout, QSizePolicy
from PyQt5.QtCore import QSize, pyqtSignal
from PyQt5 import uic, QtCore

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


class ArcGisConDialogNew(QDialog, FORM_CLASS_NEW):
    def __init__(self, parent=None):        
        super(ArcGisConDialogNew, self).__init__(parent)        
        self.setupUi(self)        


class TimePickerDialog(QDialog, TIME_FORM):
    def __init__(self, parent=None):
        super(TimePickerDialog, self).__init__(parent)
        self.setupUi(self)


class SettingsDialog(QDialog, SETTINGS_FORM):
    def __init__(self, parent=None):
        super(SettingsDialog, self).__init__(parent)
        self.setupUi(self) 


class ImageServerDashboard(QMainWindow, DASHBOARD_WINDOW):
    def __init__(self, parent=None):        
        super(ImageServerDashboard, self).__init__(parent)        
        self.setupUi(self)


class LayerDialog(QDialog, LAYER_DIALOG):
    scrolledDown = pyqtSignal([int])
    closed = pyqtSignal()


    def __init__(self, parent=None):        
        super(LayerDialog, self).__init__(parent)        
        self.setupUi(self)  
        self.imageGridWidget.layout().setSpacing(50)


    def wheelEvent(self, wheelEvent):
        if wheelEvent.delta() < -1:        
            self.scrolledDown.emit(wheelEvent.y)
        wheelEvent.ignore()


    def clearLayout(self,layout):
        for i in reversed(list(range(layout.count()))): 
            widgetToRemove = layout.itemAt(i).widget()
            # remove it from the layout list
            layout.removeWidget(widgetToRemove)
            # remove it from the gui
            widgetToRemove.setParent(None)


    def closeEvent(self, event):
        self.clearLayout(self.scrollArea.widget().layout())
        self.closed.emit()
        super(LayerDialog, self).closeEvent(event)


class ImageLabel(QLabel):
    labelSize = None


    def __init__(self, parent):
        super(ImageLabel, self).__init__(parent)

    def setSizeHint(self, size):
        self.labelSize = size
 
    def sizeHint(self):
        return self.labelSize

    def minimumSizeHint(self):
        return self.labelSize


class ImageItemWidget(QWidget):
    imageDateLabel = None
    thumbnailLabel = None
    widgetSizeHint = None
    clicked = pyqtSignal()

    def __init__(self, parent, width, height):
        super(ImageItemWidget, self).__init__(parent)
        self.initUI(width, height)

    def mouseReleaseEvent(self, event):
        self.clicked.emit()
        event.accept()

    def setSizeHint(self, size):
        self.widgetSize = size

    def sizeHint(self):
        return self.widgetSizeHint
    
    def minimumSizeHint(self):
        return self.widgetSizeHint

    def initUI(self, width, height):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2,2,2,2)
        layout.setSizeConstraint(QLayout.SetNoConstraint)
   
        self.imageDateLabel = ImageLabel(self)
        self.thumbnailLabel = ImageLabel(self)
        self.layout().addWidget(self.thumbnailLabel)
        self.layout().addWidget(self.imageDateLabel) 
 
        self.setAutoFillBackground(True)
        self.setLayout(layout)
        self.setAttribute(QtCore.Qt.WA_StyledBackground)
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
       
        sizePolicy = QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)

        thumbnailSize = QSize(width, height)
        labelSize = QSize(width, 50)
        widgetSize = QSize(width + 4, height + labelSize.height())

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
