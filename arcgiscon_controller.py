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
from qgis.core import QgsMapLayerRegistry, QgsMessageLog
from PyQt4.QtCore import QObject, QCoreApplication, Qt, QDate, QTime
from PyQt4 import QtGui
from arcgiscon_ui import ArcGisConDialogNew, TimePickerDialog
from arcgiscon_model import Connection, EsriVectorLayer, EsriRasterLayer, EsriConnectionJSONValidatorLayer, InvalidCrsIdException
from arcgiscon_service import NotificationHandler, EsriUpdateWorker
from Queue import Queue
import datetime

import json


class ArcGisConNewController(QObject):

	_newDialog = None
	_esriVectorLayers = None
	_iface = None
	_connection = None
	_legendActions = None
	_connection = None
	_updateService = None	
	_authSectionIsVisible = False	
	_customFilterJson = None
	
	def __init__(self, iface):
		QObject.__init__(self)
		self._iface = iface				
		self._newDialog = ArcGisConDialogNew()	
		self._newDialog.setModal(True)
		self._newDialog.layerUrlInput.editingFinished.connect(self._initConnection)
		self._newDialog.usernameInput.editingFinished.connect(self._onAuthInputChange)
		self._newDialog.passwordInput.editingFinished.connect(self._onAuthInputChange)	
		self._newDialog.rasterComboBox.currentIndexChanged.connect(self._onRasterBoxChange)	
		self._newDialog.cancelButton.clicked.connect(self._newDialog.reject)
		self._newDialog.connectButton.clicked.connect(self._onConnectClick)
		self._updateWorkerPool = Queue()				
			
	def createNewConnection(self, updateService, esriVectorLayers, legendActions):
		self._esriVectorLayers = esriVectorLayers
		self._legendActions = legendActions
		self._updateService = updateService
		self._hideAuthSection()
		self._resetInputValues()
		self._hideRasterSection()
		#self._newDialog.connectButton.setDisabled(True)
		self._newDialog.layerUrlInput.setFocus()
		self._newDialog.helpLabel.setOpenExternalLinks(True)
		self._newDialog.show()
		self._newDialog.exec_()
		
	def _initConnection(self):
		url = str(self._newDialog.layerUrlInput.text().strip()) 		
		name = self._newDialog.layerNameInput.text()		
		#self._newDialog.connectButton.setDisabled(True)		
		self._connection = Connection.createAndConfigureConnection(url, name)					
		if self._connection.needsAuth():
			self._newDialog.connectionErrorLabel.setText("")						
			self._showAuthSection()				
		else:							
			self._hideAuthSection()
			self._checkConnection()
	
	def _onConnectClick(self):
		if len(self._newDialog.layerUrlInput.text()) > 0:
			if len(self._newDialog.layerNameInput.text()) == 0:
				self._initConnection()
			self._requestLayerForConnection()
																						
	def _onAuthInputChange(self):
		username = str(self._newDialog.usernameInput.text())
		password = str(self._newDialog.passwordInput.text())
		if self._connection is not None and username != "" and password != "":
			self._connection.username = username
			self._connection.password = password			
			self._checkConnection()
			
	def _checkConnection(self):
		try:
			self._connection.validate(EsriConnectionJSONValidatorLayer())			
			self._newDialog.connectionErrorLabel.setText("")
			self._newDialog.layerNameInput.setText(self._connection.name)
			if self._connection.rasterFunctions is not None:
				self._addRasterFunctions(self._connection.rasterFunctions)
			self._newDialog.connectButton.setDisabled(False)		
		except Exception as e:						
			self._newDialog.connectionErrorLabel.setText(str(e.message))

	def _showAuthSection(self):
		if not self._authSectionIsVisible:
			self._newDialog.usernameLabel.show()
			self._newDialog.passwordLabel.show()
			self._newDialog.usernameInput.show()
			self._newDialog.passwordInput.show()
			
			self._newDialog.usernameInput.setFocus()
			self._authSectionIsVisible = True
		
	def _hideAuthSection(self):
		self._newDialog.usernameLabel.hide()
		self._newDialog.passwordLabel.hide()
		self._newDialog.usernameInput.hide()
		self._newDialog.passwordInput.hide()
		self._newDialog.usernameInput.setText("")
		self._newDialog.passwordInput.setText("")
		self._authSectionIsVisible = False

	def _showRasterSection(self):
		self._newDialog.rasterLabel.show()
		self._newDialog.rasterComboBox.show()

	def _hideRasterSection(self):
		self._newDialog.rasterLabel.hide()
		self._newDialog.rasterComboBox.hide()

	def _addRasterFunctions(self, rasterFunctions):
		self._newDialog.rasterComboBox.clear()
		self._newDialog.rasterComboBox.addItem('-- No raster function --')
		for i in range(len(rasterFunctions)):
			self._newDialog.rasterComboBox.addItem(rasterFunctions[i]['name'])
			self._newDialog.rasterComboBox.setItemData(i+1, rasterFunctions[i]['description'], 3) #3 Is the value for tooltip
		self._showRasterSection()

	def _onRasterBoxChange(self):
		self._connection.setCurrentRasterFunction(self._newDialog.rasterComboBox.currentIndex()-1)
							
	def _requestLayerForConnection(self):
		if self._newDialog.extentOnly.isChecked():
			mapCanvas = self._iface.mapCanvas()
			try:			
				self._connection.updateBoundingBoxByRectangle(mapCanvas.extent(), mapCanvas.mapSettings().destinationCrs().authid())
			except InvalidCrsIdException as e:
				self._newDialog.connectionErrorLabel.setText(QCoreApplication.translate('ArcGisConController', "CRS [{}] not supported").format(e.crs))				
				return
		if not self._customFilterJson is None: 
			self._connection.customFiler = self._customFilterJson
		self._connection.name = self._newDialog.layerNameInput.text()
		updateWorker = EsriUpdateWorker.create(self._connection, onSuccess=lambda srcPath: self.onSuccess(srcPath, self._connection), onWarning=lambda warningMsg: self.onWarning(self._connection, warningMsg), onError=lambda errorMsg: self.onError(self._connection, errorMsg))							
		self._updateService.update(updateWorker)
		self._newDialog.accept()		
		
	def onSuccess(self, srcPath, connection):
		#esriLayer = EsriVectorLayer.create(connection, srcPath)
		esriLayer = EsriRasterLayer.create(connection, srcPath)
		for action in self._legendActions:
			self._iface.legendInterface().addLegendLayerActionForLayer(action, esriLayer.qgsRasterLayer)
		#QgsMapLayerRegistry.instance().addMapLayer(esriLayer.qgsVectorLayer)
		QgsMapLayerRegistry.instance().addMapLayer(esriLayer.qgsRasterLayer)
		self._esriVectorLayers[esriLayer.qgsRasterLayer.id()]=esriLayer
		self._connection.renderLocked = True

	def onWarning(self, connection, warningMessage):
		NotificationHandler.pushWarning('['+connection.name+'] :', warningMessage, 5)
			
	def onError(self, connection, errorMessage):
		NotificationHandler.pushError('['+connection.name+'] :', errorMessage, 5)
		
	def _resetInputValues(self):
		self._newDialog.layerUrlInput.setText("")
		self._newDialog.layerNameInput.setText("")
		self._newDialog.usernameInput.setText("")
		self._newDialog.passwordInput.setText("")
		self._newDialog.connectionErrorLabel.setText("")
		self._newDialog.extentOnly.setChecked(False)
		self._newDialog.extentOnly.hide()
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
			worker = EsriUpdateWorker.create(esriLayer.connection, onSuccess=None, onWarning=lambda warningMsg: self.onWarning(esriLayer.connection, warningMsg), onError=lambda errorMsg: self.onError(esriLayer.connection, errorMsg))			
			updateService.update(worker)

	def showTimePicker(self, layer):
		startTimeLimitLong = layer.connection.serviceTimeExtent[0] / 1000L
		startTimeLimitDate = QDate.fromString(datetime.datetime.fromtimestamp(startTimeLimitLong).strftime('%Y-%m-%d'), "yyyy-MM-dd")

		endTimeLimitLong = layer.connection.serviceTimeExtent[1] / 1000L
		endTimeLimitDate = QDate.fromString(datetime.datetime.fromtimestamp(endTimeLimitLong).strftime('%Y-%m-%d'), "yyyy-MM-dd")

		dialog = TimePickerDialog()
		dialog.setModal(True)

		dialog.endDateInput.setMinimumDate(startTimeLimitDate)
		dialog.endDateInput.setMaximumDate(endTimeLimitDate)
		dialog.startDateInput.setMinimumDate(startTimeLimitDate)
		dialog.startDateInput.setMaximumDate(endTimeLimitDate)
		dialog.instantDateInput.setMinimumDate(startTimeLimitDate)
		dialog.instantDateInput.setMaximumDate(endTimeLimitDate)


		dialog.startDateCheckBox.stateChanged.connect(lambda state: dialog.startDateInput.setEnabled(not state))
		dialog.endDateCheckBox.stateChanged.connect(lambda state: dialog.endDateInput.setEnabled(not state))

		dialog.buttonBox.accepted.connect(lambda: self.updateLayerWithNewTimeExtent(layer, dialog))
		dialog.buttonBox.button(QtGui.QDialogButtonBox.RestoreDefaults).clicked.connect(lambda: self.onTimePickerRestoreClick(layer, dialog))

		dialog.show()
		dialog.exec_()

	def onTimePickerRestoreClick(self, layer, dialog):
		layer.connection.setTimeExtent((None,None))
		dialog.close()
			
	def updateLayerWithNewExtent(self, updateService, esriLayer):
		if not esriLayer.connection is None:

			if esriLayer.connection.renderLocked:
				esriLayer.connection.renderLocked = False
				return

			mapCanvas = self._iface.mapCanvas()
			try:
				esriLayer.connection.updateBoundingBoxByRectangle(mapCanvas.extent(), mapCanvas.mapSettings().destinationCrs().authid())
				esriLayer.updateProperties()			
				worker = EsriUpdateWorker.create(esriLayer.connection, onSuccess=lambda newSrcPath: self.onUpdateLayerWithNewExtentSuccess(newSrcPath, esriLayer, mapCanvas.extent()), onWarning=lambda warningMsg: self.onWarning(esriLayer.connection, warningMsg), onError=lambda errorMsg: self.onError(esriLayer.connection, errorMsg))			
				updateService.update(worker)
			except InvalidCrsIdException as e:
				self.onError(esriLayer.connection, QCoreApplication.translate('ArcGisConController', "CRS [{}] not supported").format(e.crs))			
			
	def updateLayerWithNewTimeExtent(self, layer, dialog):
		
		if dialog.tabWidget.currentWidget() == dialog.instantTab:
			timeExtent = dialog.startDateInput.dateTime().toMSecsSinceEpoch()
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
			timeExtent = (startDate, endDate)

		layer.connection.setTimeExtent(timeExtent)
		
	
	def onUpdateLayerWithNewExtentSuccess(self, newSrcPath, esriLayer, extent):
		esriLayer.qgsRasterLayer.triggerRepaint()
		
	def onWarning(self, connection, warningMessage):
		NotificationHandler.pushWarning('['+connection.name+'] :', warningMessage, 5)		
																	
	def onError(self, connection, errorMessage):
		NotificationHandler.pushError('['+connection.name+'] :', errorMessage, 5)	
		
		
		