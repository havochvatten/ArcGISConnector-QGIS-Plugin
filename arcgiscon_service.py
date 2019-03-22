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
from __future__ import absolute_import

from future import standard_library
standard_library.install_aliases()
from builtins import str
from builtins import range
from builtins import object
from qgis.PyQt import QtCore, QtGui
from qgis.gui import QgsMessageBar
from qgis.core import QgsMessageLog
from .arcgiscon_model import EsriLayerMetaInformation, EsriImageServiceQueryFactory, ConnectionAuthType
import time
import multiprocessing
import math
import json
import os.path
import time
import sys
import shutil
import requests
import base64
import datetime
import urllib.request, urllib.parse, urllib.error
import sip


def downloadSource(args):  
    ':type connection:Connection'
    ':type query:EsriQuery'
    connection, query, resultQueue = args
    resultJson = connection.getJson(query)
    if resultQueue is not None:      
        resultQueue.put(1)
    return resultJson  

# A class for managing downloads from different dates.
# Currently uses the date closest to the high limit.
# Update limHigh to an earlier time to query earlier dates.
class ServerItemManager(object):
    #Limits are stored in Epoch time.
    #A dictionary with 'names', 'dates', 'objectIDs'
    serverItems = None
    keyNames = 'names'
    keyDates = 'dates'
    keyObjectIDs = 'objectIDs'
    currentIndex = None
    serverNotQueryable = False
    
    def __init__(self, connection): 
        self.downloadServerData(connection)
        self.currentIndex = 0

    # Returns a QDate with the current date.
    def _currentTime(self):
        epochTime = QtCore.QDateTime.currentMSecsSinceEpoch()
        return epochTime

    def update(self, key):
        self.currentIndex += 1
        return self.currentIndex <= len(self.serverItems[key])
    
    def getCurrentItem(self, key):
        return self.serverItems[key][self.currentIndex]

    def downloadTimedServerData(self, connection):
        query = EsriImageServiceQueryFactory.createServerItemsQuery(connection, "AcquisitionDate")
        return downloadSource((connection, query ,None))

    def downloadNamedServerData(self, connection):
        query = EsriImageServiceQueryFactory.createServerItemsQuery(connection, "Name")
        return downloadSource((connection, query ,None))

    def extractItemsList(self, result, field):
        if field in result[u'features'][0][u'attributes']:
            items = []
            for x in result[u'features']:
                item = x[u'attributes'][field]
                items.append(item)
            items = [item for item in items if item is not None] 
            items.reverse()
            return items
        else:
            return []

    #Query dependent on what Fields are available at the server.
    def downloadServerData(self, connection):
        fieldDate = u'AcquisitionDate'
        fieldName = u'Name'

        self.serverItems = {self.keyDates:  [], self.keyNames: [], self.keyObjectIDs:[]} 
        timedItemsResult = self.downloadTimedServerData(connection)
        hasNoTimedResult = "CountDate" not in str(timedItemsResult)

        if hasNoTimedResult:
            namedItemsResult = self.downloadNamedServerData(connection)
            hasNoNamedResult = "CountDate" not in str(namedItemsResult)

            if hasNoNamedResult:
                self.serverNotQueryable = True
                return 

            self.serverItems[self.keyNames] = self.extractItemsList(namedItemsResult, fieldName)
            return
    
        self.serverItems[self.keyDates] = self.extractItemsList(timedItemsResult, fieldDate)
        self.createFilterList()
       

    def getStringTimeStamp(self, timeStamp):
        timeStamp = timeStamp / 1000
        return time.strftime('%Y-%m-%d', time.localtime(timeStamp))
        
    def createFilterList(self):
        serverItems = self.serverItems[self.keyDates]
        self.filterItems = {}
        if serverItems is []:
            serverItems = self.serverItemManager.serverItems[self.keyNames]
            #TODO: Implement
            return
            if serverItems is []:
                #TODO?
                return
        for x in serverItems:
            self.filterItems.update({self.getStringTimeStamp(x) : x})
                

class EsriUpdateWorker(QtCore.QObject):
    def __init__(self, connection, imageSpec):
        QtCore.QObject.__init__(self)
        self.connection = connection
        self.imageSpec = imageSpec
    
    @staticmethod
    def create(connection, imageSpec, onSuccess=None, onWarning=None, onError=None):
        worker = EsriUpdateWorker(connection, imageSpec)
        if onSuccess is not None:
            worker.onSuccess.connect(onSuccess)
        if onWarning is not None:
            worker.onWarning.connect(onWarning)
        if onError is not None:
            worker.onError.connect(onError)
        return worker
                
    onSuccess = QtCore.pyqtSignal(str)
    onWarning = QtCore.pyqtSignal(str)
    onError = QtCore.pyqtSignal(str)

class EsriUpdateServiceState(object):
    Down, Idle, Processing, TearingDown = list(range(4))


class EsriUpdateService(QtCore.QObject):   
    #Constant values, do not mutate.
    REFRESH_WAIT_TIME = .600

    #-------------------------------
    
    connectionPool = None    
    _thread = None
    _iface = None
    _isKilled = None  
    state = None
    
    _messageBar = None
    _progressBar = None
    
    _projectId = None
      
    #because http json response with features over 1000 is too large, 
    #we limit the max features per request to 1000
    _maxRecordCount = 1000   
    
         
    def __init__(self, iface):
        QtCore.QObject.__init__(self)        
        self._isKilled = False
        self._iface = iface
        self.state = EsriUpdateServiceState.Down
        self.connectionPool = []

        
    @staticmethod
    def createService(iface):
        service = EsriUpdateService(iface)            
        return service
    

    def updateProjectId(self, projectId):
        self._projectId = projectId
    
    def update(self, worker):        
        while (self.state == EsriUpdateServiceState.TearingDown):
            time.sleep(0.1)
        self.connectionPool.append(worker)
        if self.isDown():
            self.start()
    
    def start(self):        
        self.state = EsriUpdateServiceState.Idle                
        self._isKilled = False
        self._createMessageBarWidget()
        thread = QtCore.QThread()        
        self.moveToThread(thread)
        thread.started.connect(self.runUpdateWorker)
        thread.start()
        self._thread = thread
        
    def isDown(self):
        return self.state == EsriUpdateServiceState.Down
                
    def kill(self):
        self._isKilled = True  
        
    def tearDown(self):        
        self.state = EsriUpdateServiceState.TearingDown
        self._removeMessageBarWidget()
        self._thread.quit() 
        self._thread.wait()
        self._thread = None                
        self.state = EsriUpdateServiceState.Down

    def runUpdateWorker(self):
        while (not len(self.connectionPool) <= 0 or self.state == EsriUpdateServiceState.Processing) and not self._isKilled:
            try:   
                if self.state == EsriUpdateServiceState.Idle:
                    self.state = EsriUpdateServiceState.Processing
                    
                    # Wait briefly before receiving the refresh, to avoid double work.
                    time.sleep(self.REFRESH_WAIT_TIME)
                    currentJob = self.connectionPool.pop()
                    del self.connectionPool[:]
                       
                    self.progress.emit(10)
                    extent = currentJob.imageSpec.metaInfo.extent
                    settings = currentJob.imageSpec.settings
                    if 'skogsstyrelsen' in currentJob.connection.basicUrl and settings.renderingRule == None and settings.imageFormat != "png": #Added ugly ugly code for PoC
                        #TODO: Delete this if statement
                        settings.renderingRule = json.dumps({"rasterFunction": "SKS SWIR"})
                    
                    responseFormat = "image"
                    query = EsriImageServiceQueryFactory.createThumbnailQuery(
                    extent,
                    settings.getDict(),
                    responseFormat
                    )

                    url = self.createSourceURL(currentJob.connection, query)
                    self.progress.emit(90)                        
                    if url is not None and not self._isKilled:
                        filePath = self._processSources([url], currentJob.connection, settings.imageFormat)
                        currentJob.onSuccess.emit(filePath)
                    self.progress.emit(100)    
                    self.state = EsriUpdateServiceState.Idle 
                    self._isKilled = False

            except Exception as e:      
                currentJob.onError.emit(str(e))
                self.state = EsriUpdateServiceState.Idle
                self._isKilled = False                                                                                 
        self.finished.emit()


    def _downloadSources(self, queries, connection):        
        #workaround for windows qis bug (http://gis.stackexchange.com/questions/35279/multiprocessing-error-in-qgis-with-python-on-windows)
        if os.name == "nt":
            path = os.path.abspath(os.path.join(sys.exec_prefix, '../../bin/pythonw.exe'))
            multiprocessing.set_executable(path)
            sys.argv = [ None ]  
        workerPool = multiprocessing.Pool(multiprocessing.cpu_count())
        manager = multiprocessing.Manager()
        resultQueue = manager.Queue()
        args = [(connection, query, resultQueue) for query in queries]
        workingMap = workerPool.map_async(downloadSource,args)
        progressStepFactor = 80.0 / len(queries)                  
        while not self._isKilled:
            if(workingMap.ready()) :                                
                break
            else:
                size = resultQueue.qsize()                                                              
                self.progress.emit(10+size*progressStepFactor)             
        if self._isKilled:
            workerPool.terminate()
        else:
            workerPool.close()
            workerPool.join()                 
        toReturn = None            
        if not self._isKilled:
            toReturn = workingMap.get()        
        return toReturn
   
    def createSourceURL(self, connection, query):
        url = connection.basicUrl + query.getUrlAddon() + "?"
        params = urllib.parse.urlencode(query.getParams())
        url += params
        return url

    # Downloads thumbnail and returns its filepath.
    # TODO: Will have a separate url for the specific image server when there are more than one!
    def downloadThumbnail(self, connection, imageSpecification):
        imageFormat = "png"
        #size = str(imageSpecification.settings.size[0]) + "," + str(imageSpecification.settings.size[1])
        query = EsriImageServiceQueryFactory.createThumbnailQuery(
            imageSpecification.metaInfo.extent,
            imageSpecification.settings.getDict())
        json = downloadSource((connection, query, None))
        download = self._downloadRaster(json[u'href'], connection)
        filename = "thumbnail_" + str(id(imageSpecification)) + download['filename']
        return FileSystemService().storeBinaryInTmpFolder(download['data'], filename, imageFormat)

    def downloadImageDirectly(self, connection, imageSpecification):
        imageFormat = "png"
        responseFormat = "image"
        query = EsriImageServiceQueryFactory.createThumbnailQuery(
            imageSpecification.metaInfo.extent,
            imageSpecification.settings.getDict(),
            responseFormat)
        url = self.createSourceURL(connection, query)
        download = self._downloadRaster(url, connection)
        filename = "thumbnail_" + str(id(imageSpecification)) + download['filename']
        return FileSystemService().storeBinaryInTmpFolder(download['data'], filename, imageFormat)

    def _downloadRaster(self, href, connection, params = None):
        # Simple PoC implementation of downloading a raster, could probably be done more efficiently.
        response = None
        if connection.authMethod == ConnectionAuthType.BasicAuthetication:
            response = requests.get(href, auth = (connection.username, connection.password))
        else:
            response = requests.get(href)
        connectionName_clean = [ch for ch in connection.name if ch not in " ?.!/;:"]
        fname = connectionName_clean + "_" + str(connection.conId)
        return dict(filename = fname, data = response.content)
    
    def _processSources(self, sources, connection, imageFormat):     
        combined = {}
        progressStepFactor = 10.0 / len(sources)
        if len(sources) > 0:
            hrefSource = sources[0] 
            step = 1
            #if u'href' in hrefSource:
            #    # Used in image service
            #    download = self._downloadRaster(hrefSource[u'href'], connection)
            #    return FileSystemService().storeBinaryInTmpFolder(download['data'], download['filename'], hrefSource[u'href'].lower().split('.')[-1])

            if hrefSource:
                # Used in image service
                download = self._downloadRaster(hrefSource, connection)
                if imageFormat is None:
                    imageFormat = "tiff"
                return FileSystemService().storeBinaryInTmpFolder(download['data'], download['filename'], imageFormat)


            for nextResult in sources[1:]:              
                if self._isKilled:
                    break                             
                if u'features' in hrefSource and u'features' in nextResult:                     
                    hrefSource[u'features'].extend(nextResult[u'features'])
                self.progress.emit(90+step*progressStepFactor)
                step += 1                            
            combined = hrefSource
        
        if not self._isKilled: 
            filePath = None
            if self._projectId is not None:
                filePath = FileSystemService().storeJsonInProjectFolder(combined, connection.createSourceFileName(), self._projectId)
            else:
                filePath = FileSystemService().storeJsonInTmpFolder(combined, connection.createSourceFileName())
            return filePath            

    def _createMessageBarWidget(self):
        messageBar = self._iface.messageBar().createMessage(QtCore.QCoreApplication.translate('ArcGisConService', 'processing arcgis data...'),)
        progressBar = QtGui.QProgressBar()
        progressBar.setAlignment(QtCore.Qt.AlignLeft|QtCore.Qt.AlignVCenter)
        self.progress.connect(self._adjustProgress)
        cancelButton = QtGui.QPushButton()
        cancelButton.setText(QtCore.QCoreApplication.translate('ArcGisConService', 'Cancel'))
        cancelButton.clicked.connect(self.kill)
        messageBar.layout().addWidget(progressBar)
        messageBar.layout().addWidget(cancelButton)
        self._iface.messageBar().pushWidget(messageBar, self._iface.messageBar().INFO)
        self._messageBar = messageBar
        self._progressBar = progressBar
              
    def _removeMessageBarWidget(self):
        self.progress.disconnect(self._adjustProgress)
        self._iface.messageBar().popWidget(self._messageBar)
        self._messageBar = None        
    
    def _adjustProgress(self, value):   
        if not sip.isdeleted(self._progressBar):
            self._progressBar.setValue(value)
        else:
            self._createMessageBarWidget()
            
    finished = QtCore.pyqtSignal()
    #progress is linked with progress bar and expects number 
    #between 0=0% and 100=100%
    progress = QtCore.pyqtSignal(float)
    
    
class FileSystemService(object):
    
    arcGisJsonSrc = os.path.join(os.path.dirname(__file__),"imageSrc")
    credentialsFile =  os.path.join(os.path.dirname(__file__),"credentials.json")
    tmpFolderName = "tmp"

    def openFile(self, src):
        path = os.path.join(os.path.dirname(__file__), src)
        file = open(path,"rt")
        text = file.read()
        file.close()
        return text

    def storeJsonInTmpFolder(self, jsonFile, jsonFileName):
        tmpPath = os.path.join(self.arcGisJsonSrc, self.tmpFolderName)
        self._createFolderIfNotExists(tmpPath)
        filePath = os.path.join(tmpPath, jsonFileName)
        self._storeJson(jsonFile, filePath)
        return filePath

    def storeBinaryInTmpFolder(self, binaryFile, binaryFileName, fileFormat):
        tmpPath = os.path.join(self.arcGisJsonSrc, self.tmpFolderName)
        self._createFolderIfNotExists(tmpPath)
        filePath = os.path.join(tmpPath, binaryFileName + "." + fileFormat)
        self._storeBinary(binaryFile, filePath)
        return filePath
    
    def storeJsonInProjectFolder(self, jsonFile, jsonFileName, projectId):
        projectDir = os.path.join(self.arcGisJsonSrc,projectId)
        self._createFolderIfNotExists(projectDir)
        filePath = os.path.join(projectDir, jsonFileName)
        self._storeJson(jsonFile, filePath)
        return filePath
      
    def removeDanglingFilesFromProjectDir(self, existingFileNames, projectId):        
        projectPath = os.path.join(self.arcGisJsonSrc, projectId)
        self._createFolderIfNotExists(projectPath)
        filePaths = [os.path.join(projectPath, fileName) for fileName in existingFileNames]
        for existingName in os.listdir(projectPath):
            existingPath = os.path.join(self.arcGisJsonSrc, projectId, existingName)
            if existingPath not in filePaths:
                if os.path.isfile(existingPath):
                    os.unlink(existingPath)  
    
    def moveFileFromTmpToProjectDir(self, fileName, projectId):               
        pathToReturn = None 
        srcPath = os.path.join(self.arcGisJsonSrc,self.tmpFolderName, fileName)
        if os.path.isfile(srcPath):
            tarPath = os.path.join(self.arcGisJsonSrc, projectId)
            if not os.path.isfile(tarPath):
                self._createFolderIfNotExists(tarPath)
                shutil.copy2(srcPath, tarPath)
            pathToReturn = os.path.join(tarPath,fileName)
        return pathToReturn
    
    def clearAllFilesFromTmpFolder(self):
        tmpPath = os.path.join(self.arcGisJsonSrc, self.tmpFolderName)
        if os.path.isdir(tmpPath):
            for fileName in os.listdir(tmpPath):
                filePath = os.path.join(tmpPath, fileName)
                if os.path.isfile(filePath):
                    os.unlink(filePath)

    def loadSavedCredentials(self):
        if os.path.isfile(self.credentialsFile):
            cred = None
            try: 
                cred = json.loads(open(self.credentialsFile).read())
                cred['password'] = base64.b64decode(cred['password'])
            except:
                pass
            return cred
    
    def clearSavedCredentials(self):
        if os.path.isfile(self.credentialsFile):
            os.remove(self.credentialsFile)

    def saveCredentials(self, credentials):
        with open(self.credentialsFile, 'w+') as outfile:
            credentials['password'] = base64.b64encode(credentials['password'])
            json.dump(credentials, outfile)

    def saveImageAs(self, srcPath, dstPath):
        shutil.copy2(srcPath, dstPath)

    def _storeJson(self, jsonFile, filePath):                
        with open(filePath, 'w+') as outfile:
            json.dump(jsonFile, outfile)

    def _storeBinary(self, binaryFile, filePath):
        with open(filePath, 'wb') as outfile:
            outfile.write(binaryFile)
            outfile.flush()
            outfile.close()
    
    def _createFolderIfNotExists(self, folderPath):
        if not os.path.isdir(folderPath):
            os.makedirs(folderPath)


class NotificationHandler(object):
    
    _iface = None
    _duration = 4
    
    @classmethod
    def configureIface(cls, iface):        
        cls._iface = iface
    
    @classmethod    
    def pushError(cls, title, message, duration=None):
        cls._checkConfiguration()        
        cls._pushMessage(title, message, QgsMessageBar.CRITICAL, duration)
        
    @classmethod    
    def pushWarning(cls, title, message, duration=None):
        cls._checkConfiguration()
        cls._pushMessage(title, message, QgsMessageBar.WARNING, duration)
        
    @classmethod  
    def pushSuccess(cls, title, message, duration=None):
        cls._checkConfiguration()
        cls._pushMessage(title, message, QgsMessageBar.SUCCESS, duration)   
    
    @classmethod  
    def pushInfo(cls, title, message, duration=None):
        cls._checkConfiguration()
        cls._pushMessage(title, message, QgsMessageBar.INFO, duration)        
    
    @classmethod  
    def _pushMessage(cls, title, message, messageLevel, duration=None):
        duration = duration if duration is not None else cls._duration
        cls._iface.messageBar().pushMessage(title, message, level=messageLevel, duration=duration)
    
    @classmethod 
    def _checkConfiguration(cls):
        if not cls._iface:
            raise RuntimeError("iface is not configured")
        