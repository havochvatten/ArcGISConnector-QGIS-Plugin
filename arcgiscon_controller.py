# -*- coding: utf-8 -*-
from __future__ import absolute_import

from PyQt5.QtCore import QDate, QTime, QCoreApplication
from PyQt5.QtWidgets import QDialogButtonBox
from future import standard_library
standard_library.install_aliases()
from builtins import str
from builtins import range
from qgis.core import QgsProject, QgsRasterLayer, QgsMessageLog
from .arcgiscon_ui import ArcGisConDialogNew, TimePickerDialog, SettingsDialog
from .arcgiscon_model import Connection, EsriRasterLayer, EsriConnectionJSONValidatorLayer, InvalidCrsIdException
from .arcgiscon_service import NotificationHandler, EsriUpdateWorker, FileSystemService
from .event_handling import *
from queue import Queue
import datetime


import json


class ArcGisConNewController(QObject):

    _newDialog = None
    _esriRasterLayers = None
    _iface = None
    _connection = None
    _legendActions = None
    _updateService = None
    _customFilterJson = None
    _credentials = None
    _updateWorkerPool = None
    _event = None

    def __init__(self, iface):
        QObject.__init__(self)
        self._iface = iface
        self._newDialog = ArcGisConDialogNew()
        self._newDialog.setModal(True)
        self._newDialog.layerUrlInput.editingFinished.connect(self._onUrlEdit)
        self._newDialog.passwordInput.editingFinished.connect(self._onAuthInputChange)
        self._newDialog.rememberCheckbox.stateChanged.connect(lambda state: self._onAuthCheckBoxChanged(state))
        self._newDialog.cancelButton.clicked.connect(self._newDialog.reject)
        self._newDialog.connectButton.clicked.connect(self._onConnectClick)
        self._updateWorkerPool = Queue()
        self._event = Event()

    # Add handler to our events
    def addEventHandler(self, handler):
        self._event += handler

    def showView(self):
        self._resetInputValues()
        self._enableAuthSection()
        self._loadSavedCredentials()
        if self._credentials == None:
            self._newDialog.rememberCheckbox.setChecked(False)
            #self._disableAuthSection()
            self._resetInputValues()
        else:
            self._newDialog.layerUrlInput.setText(self._credentials['url'])
            if len(self._credentials['username']) > 0 or len(self._credentials['password']) > 0:
                self._newDialog.usernameInput.setText(self._credentials['username'])
                self._newDialog.passwordInput.setText(self._credentials['password'])
            self._newDialog.rememberCheckbox.setChecked(True)

        self._newDialog.layerUrlInput.setFocus()

        self._newDialog.show()
        self._newDialog.exec_()

    def _onAuthCheckBoxChanged(self, state):
        if state:
            self._saveCurrentCredentials()
        else:
            FileSystemService().clearSavedCredentials()

    def _saveCurrentCredentials(self):
        self._credentials = {}
        self._credentials['url'] = self._newDialog.layerUrlInput.text()
        self._credentials['username'] = self._newDialog.usernameInput.text()
        self._credentials['password'] = self._newDialog.passwordInput.text()
        FileSystemService().saveCredentials(self._credentials)

    def _loadSavedCredentials(self):
        self._credentials = FileSystemService().loadSavedCredentials()

    def _enableAuthSection(self):
        self._newDialog.usernameInput.setDisabled(False)
        self._newDialog.passwordInput.setDisabled(False)
        self._newDialog.rememberCheckbox.setDisabled(False)

    def _onUrlEdit(self):
        self._enableAuthSection()
        self._initConnection()

    def _initConnection(self):
        url = str(self._newDialog.layerUrlInput.text().strip())
        if (url):
            # TODO: The layer name code will go somewhere else:
            self._connection = Connection.createAndConfigureConnection(url, "")
            self._newDialog.connectionErrorLabel.setText("")
            if not self._connection.needsAuth():
                self._disableAuthSection()
                self._checkConnection()

    def _onConnectClick(self):

        if not self._newDialog.layerUrlInput.text():
            self._newDialog.connectionErrorLabel.setText("Enter a valid URL.")
            return
        if self._connection.needsAuth():
            username = self._newDialog.usernameInput.text()
            password = self._newDialog.passwordInput.text()
            self._connection.updateAuth(username, password)
            if not username or not password:
                self._newDialog.connectionErrorLabel.setText("Enter valid server credentials")
                return
            if self._newDialog.rememberCheckbox.isChecked():
                self._saveCurrentCredentials()

        self._checkConnection()
        if self.canConnect:
            self._event(self, self._connection)
            self._newDialog.hide()

    def _onAuthInputChange(self):
        username = str(self._newDialog.usernameInput.text())
        password = str(self._newDialog.passwordInput.text())
        if self._connection is not None:
            self._connection.updateAuth(username, password)
            self._checkConnection()

    def _checkConnection(self):
        error = self._connection.validate(EsriConnectionJSONValidatorLayer())
        self._newDialog.connectionErrorLabel.setText("")
        self.canConnect = True
        if error:
            self._newDialog.connectionErrorLabel.setText(str(error))
            self.canConnect = False

    def _disableAuthSection(self):
        self._newDialog.usernameInput.setText("")
        self._newDialog.passwordInput.setText("")
        self._newDialog.usernameInput.setDisabled(True)
        self._newDialog.passwordInput.setDisabled(True)
        self._newDialog.rememberCheckbox.setDisabled(True)

    def onSuccess(self, srcPath, connection, imageSpec):
        esriLayer = EsriRasterLayer.create(connection, imageSpec, srcPath)
        QgsProject.instance().addMapLayer(esriLayer.qgsRasterLayer)
        self._esriRasterLayers[esriLayer.connection.conId]=esriLayer
        self._connection.srcPath = srcPath
        self._connection.renderLocked = True

    def onWarning(self, connection, warningMessage):
        NotificationHandler.pushWarning('['+connection.name+'] :', warningMessage, 5)

    def onError(self, connection, errorMessage):
        NotificationHandler.pushError('['+connection.name+'] :', errorMessage, 5)

    def _resetInputValues(self):
        self._newDialog.layerUrlInput.setText("")
        #self._newDialog.layerNameInput.setText("")
        self._newDialog.usernameInput.setText("")
        self._newDialog.passwordInput.setText("")
        self._newDialog.connectionErrorLabel.setText("")
        #TODO: Move somewhere else.
        # self._newDialog.extentOnly.setChecked(False)
        #self._newDialog.extentOnly.hide()
        self._customFilterJson = None

    def _resetConnectionErrorStatus(self):
        self._newDialog.connectionErrorLabel.setText("")

class ArcGisConRefreshController(QObject):
    _iface = None

    def __init__(self, iface):
        QObject.__init__(self)
        self._iface = iface

    def updateLayer(self, updateService, esriLayer):
        if not esriLayer.connection is None:
            worker = EsriUpdateWorker.create(
                esriLayer.connection,
                esriLayer.imageSpec,
                onSuccess=None,
                onWarning=lambda warningMsg: self.onWarning(esriLayer.connection, warningMsg),
                onError=lambda errorMsg: self.onError(esriLayer.connection, errorMsg))
            updateService.update(worker)

    def showTimePicker(self, layer, updateCallBack):
        startTimeLimitLong = layer.connection.serviceTimeExtent[0] / 1000
        startTimeLimitDate = QDate.fromString(datetime.datetime.fromtimestamp(startTimeLimitLong).strftime('%Y-%m-%d'), "yyyy-MM-dd")

        endTimeLimitLong = layer.connection.serviceTimeExtent[1] / 1000
        endTimeLimitDate = QDate.fromString(datetime.datetime.fromtimestamp(endTimeLimitLong).strftime('%Y-%m-%d'), "yyyy-MM-dd")

        dialog = TimePickerDialog()
        dialog.setModal(True)

        dialog.endDateInput.setMinimumDate(startTimeLimitDate)
        dialog.endDateInput.setMaximumDate(endTimeLimitDate)
        dialog.startDateInput.setMinimumDate(startTimeLimitDate)
        dialog.startDateInput.setMaximumDate(endTimeLimitDate)
        dialog.instantDateInput.setMinimumDate(startTimeLimitDate)
        dialog.instantDateInput.setMaximumDate(endTimeLimitDate)


        timeExtent = layer.imageSpec.settings.timeExtent
        if timeExtent != None and len(timeExtent) > 1:
            if timeExtent[0] != "null":
                currentStartLong = timeExtent[0] / 1000
                currentStart = QDate.fromString(datetime.datetime.fromtimestamp(currentStartLong).strftime('%Y-%m-%d'), "yyyy-MM-dd")
                dialog.startDateInput.setDate(currentStart)

            if timeExtent[1] != "null":
                currentEndLong = timeExtent[1] / 1000
                currentEnd = QDate.fromString(datetime.datetime.fromtimestamp(currentEndLong).strftime('%Y-%m-%d'), "yyyy-MM-dd")
                dialog.endDateInput.setDate(currentEnd)

        elif timeExtent != None and len(timeExtent) == 1 and timeExtent[0] != "null":
            currentInstantLong = timeExtent[0] / 1000
            currentInstant = QDate.fromString(datetime.datetime.fromtimestamp(currentInstantLong).strftime('%Y-%m-%d'), "yyyy-MM-dd")
            dialog.instantDateInput.setDate(currentInstant)
            dialog.tabWidget.setCurrentWidget(dialog.instantTab)


        dialog.startDateCheckBox.stateChanged.connect(lambda state: dialog.startDateInput.setEnabled(not state))
        dialog.endDateCheckBox.stateChanged.connect(lambda state: dialog.endDateInput.setEnabled(not state))

        dialog.buttonBox.accepted.connect(lambda: self.updateLayerWithNewTimeExtent(layer, dialog))
        dialog.buttonBox.accepted.connect(updateCallBack)
        dialog.buttonBox.button(QDialogButtonBox.RestoreDefaults).clicked.connect(lambda: self.onTimePickerRestoreClick(layer, dialog))
        dialog.buttonBox.button(QDialogButtonBox.RestoreDefaults).clicked.connect(updateCallBack)

        dialog.show()
        dialog.exec_()

    def onTimePickerRestoreClick(self, layer, dialog):
        layer.imageSpec.settings.timeExtent = None
        dialog.close()

    def updateLayerWithNewExtent(self, updateService, esriLayer):
        if esriLayer.connection is not None:
            QgsMessageLog.logMessage('checking render lock: ' + str(esriLayer.connection.renderLocked))
            if esriLayer.connection.renderLocked:
                esriLayer.connection.renderLocked = False
                return

            mapCanvas = self._iface.mapCanvas()
            try:
                esriLayer.imageSpec.updateBoundingBoxByRectangle(mapCanvas.extent(), mapCanvas.mapSettings().destinationCrs().authid())
                esriLayer.updateProperties()
                worker = EsriUpdateWorker.create(
                    esriLayer.connection,
                    esriLayer.imageSpec,
                    onSuccess=lambda newSrcPath: self.onUpdateLayerWithNewExtentSuccess(newSrcPath, esriLayer, mapCanvas.extent()),
                    onWarning=lambda warningMsg: self.onWarning(esriLayer.connection, warningMsg),
                    onError=lambda errorMsg: self.onError(esriLayer.connection, errorMsg))
                updateService.update(worker)
            except InvalidCrsIdException as e:
                self.onError(esriLayer.connection, QCoreApplication.translate('ArcGisConController', "CRS [{}] not supported").format(e.crs))

    def updateLayerWithNewTimeExtent(self, layer, dialog):
        timeExtent = []
        if dialog.tabWidget.currentWidget() == dialog.instantTab:
            instantDate = dialog.instantDateInput.dateTime()
            instantDate.setTimeSpec(1) # 1 is for UTC
            instantDate.setTime(QTime(0,0,0,0))
            instantDateStart = instantDate.toMSecsSinceEpoch()
            instantDate.setTime(QTime(23,59,59,999))
            instantDateEnd = instantDate.toMSecsSinceEpoch()
            timeExtent.append(instantDateStart)
            timeExtent.append(instantDateEnd)
        else:
            startDate = endDate = "null"
            if not dialog.startDateCheckBox.isChecked():
                startDate = dialog.startDateInput.dateTime()
                startDate.setTime(QTime(0,0,0))
                startDate = startDate.toMSecsSinceEpoch()
            if not dialog.endDateCheckBox.isChecked():
                endDate = dialog.endDateInput.dateTime()
                endDate.setTime(QTime(23,59,59))
                endDate = endDate.toMSecsSinceEpoch()
            timeExtent.append(startDate)
            timeExtent.append(endDate)
        layer.imageSpec.settings.timeExtent = timeExtent


    def onUpdateLayerWithNewExtentSuccess(self, newSrcPath, esriLayer, extent):
        # Ugly reloading of layers because https://issues.qgis.org/issues/20536
        esriLayer.isUpdating = True
        QgsProject.instance().removeMapLayer(esriLayer.qgsRasterLayer)
        esriLayer.updateQgsRasterLayer(newSrcPath)
        QgsProject.instance().addMapLayer(esriLayer.qgsRasterLayer)
        esriLayer.isUpdating = False
        esriLayer.qgsRasterLayer.triggerRepaint()
        self._iface.layerTreeView().refreshLayerSymbology(esriLayer.qgsRasterLayer.id())

    def onWarning(self, connection, warningMessage):
        NotificationHandler.pushWarning('['+connection.name+'] :', warningMessage, 5)

    def onError(self, connection, errorMessage):
        NotificationHandler.pushError('['+connection.name+'] :', errorMessage, 5)

class ConnectionSettingsController(QObject):
    _iface = None
    _settingsDialog = None
    _connection = None
    _settings = {}
    _settingsObject = None
    _layer = None

    _renderingMode = None
    _mosaicMode = None

    def __init__(self, iface):
        QObject.__init__(self)
        self._iface = iface
        self._settingsDialog = SettingsDialog()
        self._settingsDialog.setModal(True)

    def showSettingsDialog(self, layer, updateCallBack):
        self._settingsDialog = SettingsDialog()
        self._layer = layer
        self._settingsObject = layer.imageSpec.settings
        self._settings = layer.imageSpec.settings.getDict()

        self._initGeneralTab()
        self._initRenderingRuleTab()
        self._initMosaicRuleTab()

        self._settingsDialog.buttonBox.accepted.connect(self._updateSettings)
        self._settingsDialog.buttonBox.accepted.connect(updateCallBack)
        self._settingsDialog.buttonBox.button(QDialogButtonBox.Apply).clicked.connect(self._updateSettings)
        self._settingsDialog.buttonBox.button(QDialogButtonBox.Apply).clicked.connect(updateCallBack)

        self._settingsDialog.show()
        self._settingsDialog.exec_()

    def _updateSettings(self):
        self._onSizeEditChange()

        if self._renderingMode == "template":
            self._settingsObject.setCurrentRasterFunction(self._settingsDialog.comboBox.currentIndex())
            self._settings['renderingRule'] = self._settingsObject.renderingRule
        elif self._renderingMode == "custom":
            self._settings['renderingRule'] = ' '.join(self._settingsDialog.customTextEdit.toPlainText().split())
        else:
            if 'renderingRule' in self._settings:
                self._settings.pop('renderingRule')

        if self._mosaicMode == True:
            self._settings['mosaicRule'] = ' '.join(self._settingsDialog.mosaicTextEdit.toPlainText().split())
        else:
            if 'mosaicRule' in self._settings:
                self._settings['mosaicRule'] = None

        self._settingsObject.updateValues(self._settings)

    def _initGeneralTab(self):
        size = ['800','800']
        if 'size' in self._settings:
            size = self._settings['size'].split(',')

        self._settingsDialog.sizeXEdit.setText(size[0])
        self._settingsDialog.sizeYEdit.setText(size[1])

        for imageFormat in self._settingsObject.IMAGE_FORMATS:
            self._settingsDialog.imageFormatComboBox.addItem(imageFormat)

        for pixelType in self._settingsObject.PIXEL_TYPES:
            self._settingsDialog.pixelTypeComboBox.addItem(pixelType)

        for noDataInter in self._settingsObject.NO_DATA_INTERPRETATIONS:
            self._settingsDialog.noDataInterpretationComboBox.addItem(noDataInter)

        for interpolation in self._settingsObject.INTERPOLATIONS:
            self._settingsDialog.interpolationComboBox.addItem(interpolation)

        if 'format' in self._settings:
            index = self._settingsDialog.imageFormatComboBox.findText(self._settings['format'])
            self._settingsDialog.imageFormatComboBox.setCurrentIndex(index)

        if 'pixelType' in self._settings:
            index = self._settingsDialog.pixelTypeComboBox.findText(self._settings['pixelType'])
            self._settingsDialog.pixelTypeComboBox.setCurrentIndex(index)

        if 'noDataInterpretation' in self._settings:
            index = self._settingsDialog.noDataInterpretationComboBox.findText(self._settings['noDataInterpretation'])
            self._settingsDialog.noDataInterpretationComboBox.setCurrentIndex(index)

        if 'interpolation' in self._settings:
            index = self._settingsDialog.interpolationComboBox.findText(self._settings['interpolation'])
            self._settingsDialog.interpolationComboBox.setCurrentIndex(index)

        if 'noData' in self._settings:
            self._settingsDialog.noDataEdit.setText(self._settings['noData'])

        if 'compression' in self._settings:
            self._settingsDialog.compressionEdit.setText(self._settings['compression'])

        if 'compressionQuality' in self._settings:
            self._settingsDialog.compressionQualityEdit.setText(self._settings['compressionQuality'])

        if 'bandIds' in self._settings:
            self._settingsDialog.bandIdEdit.setText(self._settings['bandIds'])

        self._settingsDialog.imageFormatComboBox.currentIndexChanged.connect(lambda index: self._onGeneralComboBoxChange(self._settingsDialog.imageFormatComboBox, index, 'format'))
        self._settingsDialog.pixelTypeComboBox.currentIndexChanged.connect(lambda index: self._onGeneralComboBoxChange(self._settingsDialog.pixelTypeComboBox, index, 'pixelType'))
        self._settingsDialog.noDataInterpretationComboBox.currentIndexChanged.connect(lambda index: self._onGeneralComboBoxChange(self._settingsDialog.noDataInterpretationComboBox, index, 'noDataInterpretation'))
        self._settingsDialog.interpolationComboBox.currentIndexChanged.connect(lambda index: self._onGeneralComboBoxChange(self._settingsDialog.interpolationComboBox, index, 'interpolation'))

        self._settingsDialog.noDataEdit.textEdited.connect(lambda text: self._onGeneralEditChange(text, 'noData'))
        self._settingsDialog.compressionEdit.textEdited.connect(lambda text: self._onGeneralEditChange(text, 'compression'))
        self._settingsDialog.compressionQualityEdit.textEdited.connect(lambda text: self._onGeneralEditChange(text, 'compressionQuality'))
        self._settingsDialog.bandIdEdit.textEdited.connect(lambda text: self._onGeneralEditChange(text, 'bandIds'))

        self._settingsDialog.sizeXEdit.textEdited.connect(self._onSizeEditChange)
        self._settingsDialog.sizeYEdit.textEdited.connect(self._onSizeEditChange)


    def _onSizeEditChange(self):
        if len(self._settingsDialog.sizeXEdit.text()) > 0 and len(self._settingsDialog.sizeYEdit.text()) > 0:
            self._settings['size'] = self._settingsDialog.sizeXEdit.text() + ',' + self._settingsDialog.sizeYEdit.text()
        elif len(self._settingsDialog.sizeXEdit.text()) == 0 and len(self._settingsDialog.sizeYEdit.text()) == 0 and 'size' in self._settings:
            self._settings.pop('size')

    def _onGeneralComboBoxChange(self, comboBox, index, setting):
        if len(comboBox.itemText(index)) > 0:
            self._settings[setting] = comboBox.itemText(index)
        elif setting in self._settings:
            self._settings.pop(setting)

    def _onGeneralEditChange(self, text, setting):
        if len(text) > 0:
            self._settings[setting] = text
        elif setting in self._settings:
            self._settings.pop(setting)

    def _initRenderingRuleTab(self):

        self._settingsDialog.radioButtonTemplate.toggled.connect(
            lambda buttonValue: self._renderingButtonChecked("radioButtonTemplate") if buttonValue else None)
        self._settingsDialog.radioButtonCustom.toggled.connect(
            lambda buttonValue: self._renderingButtonChecked("radioButtonCustom") if buttonValue else None)
        self._settingsDialog.radioButtonNone.toggled.connect(
            lambda buttonValue: self._renderingButtonChecked("radioButtonNone") if buttonValue else None)

        self._settingsDialog.comboBox.clear()
        rasterFunctions = self._settingsObject.rasterFunctions
        if rasterFunctions != None:
            for i in range(len(rasterFunctions)):
                self._settingsDialog.comboBox.addItem(rasterFunctions[i]['name'])
                self._settingsDialog.comboBox.setItemData(i+1, rasterFunctions[i]['description'], 3) #3 Is the value for tooltip
            self._settingsDialog.comboBox.currentIndexChanged.connect(self._onTemplateComboBoxChange)
            self._onTemplateComboBoxChange()
        else:
            self._settingsDialog.radioButtonTemplate.setEnabled(False)

        if 'renderingRule' in self._settings:
            rasterFunctionInSettings = 'rasterFunction' in self._settings['renderingRule']
            singularRenderRule = len(json.loads(self._settings['renderingRule'])) == 1
            if rasterFunctionInSettings and singularRenderRule:
                self._renderingMode = "template"
                self._settingsDialog.radioButtonTemplate.click()
                self._settingsDialog.comboBox.setCurrentIndex(self._settingsDialog.comboBox.findText(json.loads(self._settings['renderingRule'])['rasterFunction']))
            else:
                self._renderingMode = "custom"
                self._settingsDialog.radioButtonCustom.click()
                self._settingsDialog.customTextEdit.setPlainText(self._settingsObject.renderingRule)
        else:
            self._renderingMode = "none"
            self._settingsDialog.radioButtonNone.click()

    def _onTemplateComboBoxChange(self):
        rasterFunctions = self._settingsObject.rasterFunctions
        index = self._settingsDialog.comboBox.currentIndex()
        descriptionText = rasterFunctions[index]['description']
        helpText = rasterFunctions[index]['help']
        self._settingsDialog.templateTextEdit.clear()
        self._settingsDialog.templateTextEdit.appendPlainText('Description: ' + descriptionText + "\n" + 'Help: ' + helpText)

    def _renderingButtonChecked(self, button):
        if button == "radioButtonTemplate":
            self._renderingMode = "template"
            self._settingsDialog.comboBox.setEnabled(True)
            self._settingsDialog.templateTextEdit.setEnabled(True)
            self._settingsDialog.customTextEdit.setEnabled(False)
        if button == "radioButtonCustom":
            self._renderingMode = "custom"
            self._settingsDialog.comboBox.setEnabled(False)
            self._settingsDialog.templateTextEdit.setEnabled(False)
            self._settingsDialog.customTextEdit.setEnabled(True)
        if button == "radioButtonNone":
            self._renderingMode = "none"
            self._settingsDialog.comboBox.setEnabled(False)
            self._settingsDialog.templateTextEdit.setEnabled(False)
            self._settingsDialog.customTextEdit.setEnabled(False)

    def _initMosaicRuleTab(self):
        if self._mosaicMode == None or self._mosaicMode == False:
            self._settingsDialog.mosaicTextEdit.setEnabled(False)
        else:
            self._settingsDialog.mosaicCheckBox.setChecked(True)
            self._settingsDialog.mosaicTextEdit.setPlainText(self._settingsObject.mosaicRule)
        self._settingsDialog.mosaicCheckBox.stateChanged.connect(lambda value: self._mosaicCheckBoxChanged(value))

    def _mosaicCheckBoxChanged(self, value):
        self._mosaicMode = bool(value)
        self._settingsDialog.mosaicTextEdit.setEnabled(value)
