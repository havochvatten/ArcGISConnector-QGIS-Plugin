# -*- coding: utf-8 -*-
import os

from PyQt5 import uic
from PyQt5.QtWidgets import QDialog

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'arcgiscon_plugin_dialog_base.ui'))


class ArcGisConnectorDialog(QDialog, FORM_CLASS):
    def __init__(self, parent=None):
        super(ArcGisConnectorDialog, self).__init__(parent)
        # Set up the user interface from Designer.
        # After setupUI you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)
