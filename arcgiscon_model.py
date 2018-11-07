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

from qgis.core import QgsVectorLayer
from qgis.core import QgsRasterLayer, QgsMessageLog

import requests
import requests_ntlm
import hashlib
import json

class EsriVectorQueryFactoy:
    
    @staticmethod
    def createMetaInformationQuery():
        return EsriQuery(params={"f":"json"})                                 
    
    @staticmethod
    def createTotalFeatureCountQuery(extent=None, customFilter=None):  
        query = EsriVectorQueryFactoy.createBaseQuery(extent, customFilter)
        query.update({"returnCountOnly":"true"})
        return EsriQuery("/query", query)
    
    @staticmethod
    def createFeaturesQuery(extent=None, customFilter=None):
        query = EsriVectorQueryFactoy.createBaseQuery(extent, customFilter)                
        return EsriQuery("/query", query)
    
    @staticmethod
    def createPagedFeaturesQuery(page, maxRecords, extent=None, customFilter=None):
        offset = page * maxRecords
        query = EsriVectorQueryFactoy.createBaseQuery(extent, customFilter)
        query.update({"resultOffset":offset, "resultRecordCount":maxRecords})        
        return EsriQuery("/query", query)
    
    @staticmethod
    def createExtentParam(extent):
        return {
                "geometryType":"esriGeometryEnvelope",
                "geometry":json.dumps(extent['bbox']),
                "inSR":json.dumps(extent['spatialReference'])
                }
        
    @staticmethod    
    def createBaseQuery(extent=None, customFilter=None):        
        allObjects = {"where":"objectid=objectid"}
        allFields = {"outfields":"*"}
        jsonFormat = {"f":"json"}                           
        query = {}         
        customFilterKeys = []
        if not customFilter is None:
            customFilterKeys = [k.lower() for k in customFilter.keys()]
        if customFilter is None or not "where" in customFilterKeys:
            query.update(allObjects)
        if customFilter is None or not "outfields" in customFilterKeys:
            query.update(allFields)
        if customFilter is None or not "f" in customFilterKeys:
            query.update(jsonFormat)
        if customFilter is not None:
            query.update(customFilter)
        if extent is not None and (customFilter is None or "geometry" not in customFilter):
            query.update(EsriVectorQueryFactoy.createExtentParam(extent))
        return query

class EsriImageServiceQueryFactory:

    @staticmethod
    def createMetaInformationQuery():
        return EsriQuery(params={"f":"json"})

    @staticmethod
    def createBaseQuery(extent=None, mapExtent=None, settings={}):
        SETTINGS_LIST = ['size', 'imageFormat', 'pixelType', 'noDataInterpretation', 'interpolation', 
        'noData', 'compression', 'compressionQuality', 'bandIds' ]
        QgsMessageLog.logMessage("settings - " + str(settings))

        query = {"f":"json"}
        if extent is not None:
            query.update(EsriImageServiceQueryFactory.createExtentParam(extent))
        else:
            query.update(EsriImageServiceQueryFactory.createExtentParam(mapExtent))
        if 'renderingRule' in settings:
            rasterJson = settings['renderingRule']
            query.update({'renderingRule' : rasterJson})
        if 'timeExtent' in settings:
            timeExtent = settings['timeExtent']
            if isinstance(timeExtent, tuple):
                timeExtentJson = {"time" : str(timeExtent[0]) + "," + str(timeExtent[1])}
            else:
                timeExtentJson = {"time" : str(timeExtent)}
            query.update(timeExtentJson)
        for setting in SETTINGS_LIST:
            if setting in settings:
                query.update({setting: settings[setting]})
        QgsMessageLog.logMessage(str(query) + " query")
        return query 

    @staticmethod
    def createExportImageQuery(extent=None, mapExtent=None, settings={}):
        query = EsriImageServiceQueryFactory.createBaseQuery(extent, mapExtent, settings)
        return EsriQuery("/ExportImage", query)

    @staticmethod
    def createExtentParam(extent):
        return {
            "bbox": json.dumps(extent['bbox']),
            "format": "tiff",
            "imageSR": json.dumps(extent['spatialReference']['wkid']),
            "bboxSR": json.dumps(extent['spatialReference']['wkid']),
        }
                
class EsriQuery:
    _urlAddon = None
    _params = None
    def __init__(self, urlAddon="", params={}):
        self._urlAddon = urlAddon
        self._params = params
    
    def getUrlAddon(self):
        return self._urlAddon
    
    def getParams(self):
        return self._params
    
        
class ConnectionAuthType:
    NoAuth, BasicAuthetication, NTLM = range(3)

class EsriConnectionJSONValidatorException(Exception):
    NotArcGisRest, WrongLayerType, NoLayer, NoPagination = range(4)  
    
    errorNr = None
    
    def __init__(self, message, errorNr):
        super(EsriConnectionJSONValidatorException, self).__init__(message)
        self.errorNr = errorNr


class EsriConnectionJSONValidatorResponse:
    isValid = None
    exceptionMessage = None
                
    def __init__(self, isValid, exceptionMessage=None):
        self.isValid = isValid
        self.exceptionMessage = exceptionMessage
    
    @staticmethod
    def createValid():
        return EsriConnectionJSONValidatorResponse(True)
    
    @staticmethod
    def createNotValid(message):
        return EsriConnectionJSONValidatorResponse(False, message)
    

class EsriConnectionJSONValidator:
    
    def validate(self, responseJson):
        raise NotImplementedError("Needs implementation")
    
class EsriConnectionJSONValidatorLayer(EsriConnectionJSONValidator):
    
    def validate(self, response):
        try:
            responseJson = response.json()
        except ValueError:
            raise EsriConnectionJSONValidatorException("No ArcGIS Resource found.", EsriConnectionJSONValidatorException.NotArcGisRest)
        metaInfo = EsriLayerMetaInformation.createFromMetaJson(responseJson)
        if metaInfo.layerType is None:
            raise EsriConnectionJSONValidatorException("The URL points not to a layer.", EsriConnectionJSONValidatorException.NoLayer)
        if "esriImageServiceDataType" not in metaInfo.layerType:
            raise EsriConnectionJSONValidatorException("Layer must be of type Image Service. {} provided.".format(metaInfo.layerType), EsriConnectionJSONValidatorException.WrongLayerType)
        
            
class EsriLayerMetaInformation:
    maxRecordCount = 0
    supportsPagination = False
    layerType = None
    extent = None
    rasterFunctions = None
    timeExtent = (None, None)
    
    @staticmethod
    def createFromMetaJson(metaJson):
        ':rtype EsriLayerMetaInformation'
        metaInfo = EsriLayerMetaInformation()
        if u'maxRecordCount' in metaJson:
            metaInfo.maxRecordCount = int(metaJson[u'maxRecordCount'])
        if "advancedQueryCapabilities" in metaJson and "supportsPagination" in metaJson["advancedQueryCapabilities"] and metaJson["advancedQueryCapabilities"]["supportsPagination"]:
            metaInfo.supportsPagination = metaJson["advancedQueryCapabilities"]["supportsPagination"]
        if "extent" in metaJson:
            bbox = {'xmin': metaJson["extent"]['xmin'], 'ymin': metaJson["extent"]['ymin'], 'xmax': metaJson["extent"]['xmax'], 'ymax': metaJson["extent"]['ymax']}
            metaInfo.extent = {'bbox': bbox, 'spatialReference': metaJson["extent"]['spatialReference']}
        if "serviceDataType" in metaJson:
            metaInfo.layerType = metaJson["serviceDataType"]
        if u'allowRasterFunction' in metaJson and metaJson[u'allowRasterFunction'] and u'rasterFunctionInfos' in metaJson:
            metaInfo.rasterFunctions = metaJson[u'rasterFunctionInfos']
        if u'timeInfo' in metaJson:
            metaInfo.timeExtent = (metaJson['timeInfo']['timeExtent'][0], metaJson['timeInfo']['timeExtent'][1])

        return metaInfo
        

class InvalidCrsIdException(Exception):    
    crs = None        
    def __init__(self, crs):
        super(InvalidCrsIdException, self).__init__("CRS not supported")
        self.crs = crs
        

class Connection:    
    basicUrl = None    
    name = None    
    authMethod = None
    username = None
    password = None
    bbBox = None
    rasterFunctions = None
    serviceTimeExtent = (None, None)
    settings = {}
    conId = None
    
    def __init__(self, basicUrl, name, username=None, password=None, authMethod=ConnectionAuthType.NoAuth):
        self.basicUrl = basicUrl
        self.name = name
        self.username = username
        self.password = password
        self.authMethod = authMethod
        self.conId = id(self)
        
    @staticmethod
    def createAndConfigureConnection(basicUrl, name, username=None, password=None, authMethod=ConnectionAuthType.NoAuth, validator=EsriConnectionJSONValidatorLayer()):
        connection = Connection(basicUrl, name, username, password, authMethod)
        connection.configure(validator)
        return connection
       
    def configure(self, validator):
        try:
            query = EsriImageServiceQueryFactory.createMetaInformationQuery()                                     
            response = self.connect(query)
            if response.status_code != 200: 
                if "www-authenticate" in response.headers:
                    if "NTLM, Negotiate" in response.headers["www-authenticate"]:
                        self.authMethod = ConnectionAuthType.NTLM
                    else:
                        self.authMethod = ConnectionAuthType.BasicAuthetication
        except (requests.exceptions.RequestException, ValueError):
            # fail silently
            pass   
                             
    def validate(self, validator):
        try:
            query = EsriImageServiceQueryFactory.createMetaInformationQuery()
            response = self.connect(query)
            response.raise_for_status()
            validator.validate(response)
            self._updateLayerNameFromServerResponse(response)
            metaInfo = EsriLayerMetaInformation.createFromMetaJson(response.json())
            self._updateRasterFunctions(metaInfo.rasterFunctions)
            self._updateTimeExtent(metaInfo.timeExtent)
        except Exception:
            raise
    
    def connect(self, query):       
        auth = None
        try: 
            if self.authMethod != ConnectionAuthType.NoAuth and self.username and self.password:
                if self.authMethod == ConnectionAuthType.NTLM:                    
                    auth = requests_ntlm.HttpNtlmAuth(self.username, self.password)
                if self.authMethod == ConnectionAuthType.BasicAuthetication:
                    auth = (self.username, self.password)
            request = requests.post(self.basicUrl + query.getUrlAddon(), params=query.getParams(), auth=auth, timeout=180)            
        except requests.ConnectionError:
            raise
        except requests.HTTPError:
            raise
        except requests.Timeout:
            raise
        except requests.TooManyRedirects:
            raise        
        return request
    
    def needsAuth(self):
        return self.authMethod != ConnectionAuthType.NoAuth
    
    def updateBoundingBoxByExtent(self, extent):
        self.bbBox = extent

    def updateBoundingBoxByRectangle(self, qgsRectangle, authId):
        spacialReferenceWkid = self.extractWkidFromAuthId(authId)
        QgsMessageLog.logMessage(str(qgsRectangle.xMinimum()) + ", " + str(qgsRectangle.yMinimum()) + ", " + str(qgsRectangle.xMaximum()) + ", " + str(qgsRectangle.yMaximum()))
        self.bbBox = {
            "bbox":
            {
                "xmin": qgsRectangle.xMinimum(),
                "ymin": qgsRectangle.yMinimum(),
                "xmax": qgsRectangle.xMaximum(),
                "ymax": qgsRectangle.yMaximum()
            },
            "spatialReference":
            {
                "wkid": spacialReferenceWkid
            }
        }

        
    def clearBoundingBox(self):
        self.bbBox = None        
    
    def getJson(self, query):
        return self.connect(query).json()
                                    
    def createSourceFileName(self):        
        vectorSrcName = hashlib.sha224(self.getConnectionIdentifier()).hexdigest()
        return vectorSrcName + ".json"
    
    def getConnectionIdentifier(self):
        identifier = self.basicUrl
        if self.bbBox is not None:
            identifier += json.dumps(self.bbBox)
        return identifier
                                            
    def _updateLayerNameFromServerResponse(self, response):
        try:
            responseJson = response.json()
            if "name" in responseJson:
                self.name = responseJson["name"]
        except ValueError:
            raise
        
    def _updateRasterFunctions(self, rasterFunctions):
        self.rasterFunctions = rasterFunctions
    
    def _updateTimeExtent(self, extent):
        self.serviceTimeExtent = extent

    def createMetaDataAbstract(self):
        meta = ""
        if self.bbBox is not None:
            meta += "bbox: "+json.dumps(self.bbBox)+"\n\n"
        return meta
    
    def extractWkidFromAuthId(self, authId):
        try:
            return int(authId.split(":")[1])
        except ValueError:
            raise InvalidCrsIdException(authId)
    
    def setCurrentRasterFunction(self, index):
        if index >= 0 and self.rasterFunctions is not None:
            self.settings.update(
                {
                    "renderingRule": json.dumps({
                        "rasterFunction": self.rasterFunctions[index]["name"]
                    })
                }
            )
    
    def updateSettings(self, newSettings):
        self.settings.update(newSettings)
    
    def setTimeExtent(self, timeExtent):
        self.settings.update(
            {'timeExtent' : timeExtent}
        )
      
              
class EsriVectorLayer:
    qgsVectorLayer = None
    connection = None
    
    @staticmethod
    def create(connection, srcPath):
        esriLayer = EsriVectorLayer()
        esriLayer.connection = connection
        esriLayer.updateQgsVectorLayer(srcPath)
        return esriLayer
    
    @staticmethod
    def restoreFromQgsLayer(qgsLayer):
        esriLayer = EsriVectorLayer()
        esriLayer.qgsVectorLayer = qgsLayer
        basicUrl = str(qgsLayer.customProperty("arcgiscon_connection_url"))
        name = qgsLayer.name()
        username = str(qgsLayer.customProperty("arcgiscon_connection_username")) 
        password = str(qgsLayer.customProperty("arcgiscon_connection_password"))
        authMethod = int(qgsLayer.customProperty("arcgiscon_connection_authmethod"))
        esriLayer.connection = Connection(basicUrl, name, username, password, authMethod)
        extent = str(qgsLayer.customProperty("arcgiscon_connection_extent"))
        if extent != "":
            esriLayer.connection.updateBoundingBoxByExtent(json.loads(extent))
        return esriLayer
                                                
    def updateQgsVectorLayer(self, srcPath):
        self.qgsVectorLayer = QgsVectorLayer(srcPath, self.connection.name, "ogr")        
        self.updateProperties()          
    
    def updateProperties(self):
        self.qgsVectorLayer.setCustomProperty("arcgiscon_connection_url", self.connection.basicUrl)            
        self.qgsVectorLayer.setCustomProperty("arcgiscon_connection_authmethod", self.connection.authMethod)
        self.qgsVectorLayer.setCustomProperty("arcgiscon_connection_username", self.connection.username)
        self.qgsVectorLayer.setCustomProperty("arcgiscon_connection_password", self.connection.password)
        extent = json.dumps(self.connection.bbBox) if self.connection.bbBox is not None else ""
#         extent = self.connection.bbBox if self.connection.bbBox is not None else ""
        self.qgsVectorLayer.setCustomProperty("arcgiscon_connection_extent", extent)
        self.qgsVectorLayer.setDataUrl(self.connection.basicUrl)
        self.qgsVectorLayer.setAbstract(self.connection.createMetaDataAbstract())

class EsriRasterLayer:
    qgsRasterLayer = None        
    connection = None
    
    @staticmethod
    def create(connection, srcPath):
        esriLayer = EsriRasterLayer()
        esriLayer.connection = connection
        esriLayer.updateQgsRasterLayer(srcPath)
        return esriLayer
    
    @staticmethod
    def restoreFromQgsLayer(qgsLayer):
        esriLayer = EsriRasterLayer()
        esriLayer.qgsRasterLayer = qgsLayer
        basicUrl = str(qgsLayer.customProperty("arcgiscon_connection_url"))
        name = qgsLayer.name()
        username = str(qgsLayer.customProperty("arcgiscon_connection_username")) 
        password = str(qgsLayer.customProperty("arcgiscon_connection_password"))
        authMethod = int(qgsLayer.customProperty("arcgiscon_connection_authmethod"))
        esriLayer.connection = Connection(basicUrl, name, username, password, authMethod)
        extent = str(qgsLayer.customProperty("arcgiscon_connection_extent"))
        if extent != "":
            esriLayer.connection.updateBoundingBoxByExtent(json.loads(extent))
        return esriLayer
                                                
    def updateQgsRasterLayer(self, srcPath):
        self.qgsRasterLayer = QgsRasterLayer(srcPath, self.connection.name)        
        self.updateProperties()          
    
    def updateProperties(self):
        self.qgsRasterLayer.setCustomProperty("arcgiscon_connection_url", self.connection.basicUrl)            
        self.qgsRasterLayer.setCustomProperty("arcgiscon_connection_authmethod", self.connection.authMethod)
        self.qgsRasterLayer.setCustomProperty("arcgiscon_connection_username", self.connection.username)
        self.qgsRasterLayer.setCustomProperty("arcgiscon_connection_password", self.connection.password)
        extent = json.dumps(self.connection.bbBox) if self.connection.bbBox is not None else ""
#         extent = self.connection.bbBox if self.connection.bbBox is not None else ""
        self.qgsRasterLayer.setCustomProperty("arcgiscon_connection_extent", extent)
        self.qgsRasterLayer.setDataUrl(self.connection.basicUrl)
        self.qgsRasterLayer.setAbstract(self.connection.createMetaDataAbstract())
                      
