# -*- coding: utf-8 -*-

from __future__ import absolute_import
from builtins import str
from builtins import object
from qgis.PyQt.QtCore import QTranslator, qVersion, QCoreApplication, QSettings
from qgis.PyQt.QtWidgets import QAction, QApplication
from qgis.PyQt.QtGui import QIcon

from qgis.core import QgsMapLayer, QgsProject

from .arcgiscon_service import NotificationHandler, EsriUpdateService,\
    FileSystemService
from .arcgiscon_controller import ArcGisConNewController, \
    ArcGisConRefreshController, ConnectionSettingsController
from .arcgiscon_image_controller import ImageController
from .layer_dialog_controller import LayerDialogController
from .arcgiscon_model import EsriRasterLayer
from uuid import uuid4
import os.path

# import sys;
# sys.path.append(r'/Applications/liclipse/plugins/org.python.pydev_3.9.2.201502042042/pysrc')
# import pydevd


class ArcGisConnector(object):
    # pydevd.settrace()
    _iface = None
    _newLayerAction = None
    _newLayerActionText = None
    _arcGisRefreshLayerAction = None
    _arcGisRefreshLayerWithNewExtentAction = None
    _arcGisTimePickerAction = None
    _arcGisSaveImageAction = None
    _pluginDir = None
    _esriRasterLayers = None
    _updateService = None
    _qSettings = None

# Controllers
    _settingsController = None
    _imageController = None
    _refreshController = None
    _connectionController = None
    _layerDialogController = None
    
    def __init__(self, iface):            
        self._iface = iface        
        self.initControllers()
        self._pluginDir = os.path.dirname(__file__)
        self._qSettings = QSettings()
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(self._pluginDir,'i18n','arcgiscon_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)

            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)
        NotificationHandler.configureIface(iface)
        self._esriRasterLayers = {}
        self._iface.projectRead.connect(self._onProjectLoad)        
        self._updateService = EsriUpdateService.createService(iface)
        self._updateService.finished.connect(self._updateServiceFinished) 

        QgsProject.instance().layerRemoved.connect(self._onLayerRemoved)
        QgsProject.instance().writeProject.connect(self._onProjectInitialWrite)
        QgsProject.instance().projectSaved.connect(self._onProjectSaved)
        self._connectToRefreshAction()

    def initControllers(self):
        self._settingsController = ConnectionSettingsController(self._iface)
        self._imageController = ImageController(self._iface)
        self._refreshController = ArcGisConRefreshController(self._iface)
        self._connectionController = ArcGisConNewController(self._iface)
        self._layerDialogController = LayerDialogController(self._iface)

        # Register handler to event
        self._connectionController.addEventHandler(self.handleLogin)
        
    def handleLogin(self, sender, connection): 
        self._layerDialogController.showView(connection,
            self._updateService,
            self._esriRasterLayers,
                [
                    self._arcGisRefreshLayerAction,
                    self._arcGisRefreshLayerWithNewExtentAction,
                    self._arcGisTimePickerAction,
                    self._arcGisSaveImageAction,
                    self._arcGisTimePickerAction,
                    self._arcGisSettingsAction
                ])

    def initGui(self):
        newLayerActionIcon = QIcon(':/plugins/ImageServerConnector/icons/logo.png')
        self._newLayerActionText = QCoreApplication.translate('ArcGisConnector', 'arcgiscon')
        self._newLayerAction = QAction(
            newLayerActionIcon,
            self._newLayerActionText,
            self._iface.mainWindow())

        self._newLayerAction.triggered.connect(
            lambda: self._connectionController.showView()
            )
        try:
            self._iface.layerToolBar().addAction(self._newLayerAction)
        except:
            self._iface.addToolBarIcon(self._newLayerAction)   
        self._iface.addPluginToRasterMenu(self._newLayerActionText, self._newLayerAction)
        self._iface.insertAddLayerAction(self._newLayerAction)
        self._arcGisRefreshLayerWithNewExtentAction = QAction( QCoreApplication.translate('ArcGisConnector', 'Refresh layer with current extent'), self._iface.legendInterface() )
        self._arcGisSaveImageAction = QAction( QCoreApplication.translate('ArcGisConnector', 'Save layer image as..'), self._iface.legendInterface() )
        self._arcGisTimePickerAction = QAction( QCoreApplication.translate('ArcGisConnector', 'Choose layer time extent..'), self._iface.legendInterface() )
        self._arcGisSettingsAction = QAction( QCoreApplication.translate('ArcGisConnector', 'ArcGIS layer settings..'), self._iface.legendInterface() )

        self._iface.legendInterface().addLegendLayerAction(self._arcGisSaveImageAction, QCoreApplication.translate('ArcGisConnector', 'ArcGIS'), u"id1", QgsMapLayer.RasterLayer, False )
        self._iface.legendInterface().addLegendLayerAction(self._arcGisRefreshLayerWithNewExtentAction, QCoreApplication.translate('ArcGisConnector', 'ArcGIS'), u"id2", QgsMapLayer.RasterLayer, False )
        self._iface.legendInterface().addLegendLayerAction(self._arcGisTimePickerAction, QCoreApplication.translate('ArcGisConnector', 'ArcGIS'), u"id3", QgsMapLayer.RasterLayer, False )
        self._iface.legendInterface().addLegendLayerAction(self._arcGisSettingsAction, QCoreApplication.translate('ArcGisConnector', 'ArcGIS'), u"id4", QgsMapLayer.RasterLayer, False )

        self._iface.mapCanvas().extentsChanged.connect(self._onExtentsChanged)
        self._arcGisSaveImageAction.triggered.connect(self._onLayerImageSave)
        self._arcGisRefreshLayerWithNewExtentAction.triggered.connect(lambda: self._refreshEsriLayer(True))
        self._arcGisTimePickerAction.triggered.connect(self._chooseTimeExtent)
        self._arcGisSettingsAction.triggered.connect(self._showSettingsDialog)

    def _connectToRefreshAction(self):
        for action in self._iface.mapNavToolToolBar().actions():
            if action.objectName() == "mActionDraw":
                action.triggered.connect(self._refreshAllEsriLayers)
                
    def _refreshAllEsriLayers(self): 
        for layer in list(self._esriRasterLayers.values()):
            self._refreshController.updateLayer(self._updateService, layer)

    def _refreshAllVisibleLayers(self):
        for layer in list(self._esriRasterLayers.values()):
            if QgsProject.instance().layerTreeRoot().findLayer(layer.qgsRasterLayer.id()).isVisible():
                self._refreshController.updateLayerWithNewExtent(self._updateService, layer)
                
    
    def _refreshEsriLayer(self, withCurrentExtent=False):
        qgsLayers = self._iface.legendInterface().selectedLayers()
        for layer in qgsLayers:
            if layer.id() in self._esriRasterLayers:  
                if withCurrentExtent:
                    self._refreshController.updateLayerWithNewExtent(self._updateService, self._esriRasterLayers[layer.id()])

    def _onExtentsChanged(self):
        if self._iface.mapCanvas().renderFlag():
            self._refreshAllVisibleLayers()

    def _onProjectLoad(self): 
        projectId = str(QgsProject.instance().readEntry("arcgiscon","projectid","-1")[0])
        if  projectId != "-1":                                
            self._reconnectEsriLayers()
            FileSystemService().removeDanglingFilesFromProjectDir([layer.connection.createSourceFileName() for layer in list(self._esriRasterLayers.values())], projectId)
            self._updateService.updateProjectId(projectId)            
        
    def _onProjectInitialWrite(self):
        projectId = str(QgsProject.instance().readEntry("arcgiscon","projectid","-1")[0])
        if projectId == "-1" and self._esriRasterLayers:
            projectId = uuid4().hex
            for esriLayer in list(self._esriRasterLayers.values()):                
                newSrcPath = FileSystemService().moveFileFromTmpToProjectDir(esriLayer.connection.createSourceFileName(), projectId)
                if newSrcPath is not None:
                    esriLayer.qgsRasterLayer.setDataSource(newSrcPath, esriLayer.qgsRasterLayer.name(),"ogr")            
            QgsProject.instance().writeEntry("arcgiscon","projectid",projectId)
            self._updateService.updateProjectId(projectId)                    
    
    def _onProjectSaved(self):
        projectId = str(QgsProject.instance().readEntry("arcgiscon","projectid","-1")[0])
        if projectId != "-1":
            FileSystemService().removeDanglingFilesFromProjectDir([layer.connection.createSourceFileName() for layer in list(self._esriRasterLayers.values())], projectId)
                        
    def _reconnectEsriLayers(self):
        layers = QgsProject.instance().mapLayers()
        for qgsLayer in list(layers.values()):            
            if qgsLayer.customProperty('arcgiscon_connection_url', ''):                
                try:
                    esriLayer = EsriRasterLayer.restoreFromQgsLayer(qgsLayer)
                    self._esriRasterLayers[qgsLayer.id()] = esriLayer
                    self._iface.legendInterface().addLegendLayerActionForLayer(self._arcGisRefreshLayerAction, qgsLayer)
                    self._iface.legendInterface().addLegendLayerActionForLayer(self._arcGisRefreshLayerWithNewExtentAction, qgsLayer)
                except: 
                    raise

    def _onLayerImageSave(self):
        qgsLayers = self._iface.legendInterface().selectedLayers()
        for layer in qgsLayers:
            if layer.id() in self._esriRasterLayers:
                selectedLayer = self._esriRasterLayers[layer.id()]
                self._imageController.saveImage(selectedLayer.qgsRasterLayer.dataProvider().dataSourceUri())

    def _chooseTimeExtent(self):
        qgsLayers = self._iface.legendInterface().selectedLayers()
        for layer in qgsLayers:
            if layer.id() in self._esriRasterLayers:
                selectedLayer = self._esriRasterLayers[layer.id()]
                self._refreshController.showTimePicker(selectedLayer, lambda: self._refreshEsriLayer(True))

    def _showSettingsDialog(self):
        qgsLayers = self._iface.legendInterface().selectedLayers()
        for layer in qgsLayers:
            if layer.id() in self._esriRasterLayers:
                selectedLayer = self._esriRasterLayers[layer.id()]
                self._settingsController.showSettingsDialog(selectedLayer, lambda: self._refreshEsriLayer(True))   

    def _updateServiceFinished(self):            
        self._updateService.tearDown()
        # move back to main GUI thread
        self._updateService.moveToThread(QApplication.instance().thread())

    def _onLayerRemoved(self, layerId):
        if layerId in self._esriRasterLayers:
            del self._esriRasterLayers[layerId]

    def unload(self):
        FileSystemService().clearAllFilesFromTmpFolder()
        self._iface.removePluginMenu(
            QCoreApplication.translate('ArcGisConnector', 'arcgiscon'),
            self._newLayerAction)
        self._iface.removePluginVectorMenu(self._newLayerActionText, self._newLayerAction)
        self._iface.removeToolBarIcon(self._newLayerAction)        
        self._iface.legendInterface().removeLegendLayerAction(self._arcGisRefreshLayerAction)
