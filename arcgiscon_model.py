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
import time

class EsriImageServiceQueryFactory:

	@staticmethod
	def createMetaInformationQuery():
		return EsriQuery(params={"f":"json"})


	@staticmethod    
	def createServerItemsQuery(connection):

	  #   bbox = {'xmin': metaJson["extent"]['xmin'], 'ymin': metaJson["extent"]['ymin'], 'xmax': metaJson["extent"]['xmax'], 'ymax': metaJson["extent"]['ymax']}
	  #      metaInfo.extent = {'bbox': bbox, 'spatialReference': metaJson["extent"]['spatialReference']}
	  #  if "serviceDataType" in metaJson:
	  #      metaInfo.layerType = metaJson["serviceDataType"]
	  #  if u'allowRasterFunction' in metaJson and metaJson[u'allowRasterFunction'] and u'rasterFunctionInfos' in metaJson:
	  #      metaInfo.rasterFunctions = metaJson[u'rasterFunctionInfos']
	  #  if u'timeInfo' in metaJson:
	  #      metaInfo.timeExtent = (metaJson['timeInfo']['timeExtent'][0], metaJson['timeInfo']['timeExtent'][1])


		query = {} 
		jsonFormat = {"f":"json"}
		query.update(jsonFormat)
		
		# QgsMessageLog.logMessage(str(connection.metaInfo))
		# timeExtentJson = {"time" : str(connection.metaInfo.timeExtent[0]) + "," + str(connection.metaInfo.timeExtent[1])}
		# query.update(timeExtentJson)
		
		#bbox = connection.metaInfo.extent["bbox"]
		#geometryJson = {"geometry": str(bbox["xmin"]) + "," + str(connection.metaInfo.extent[1])}
		#query.update(geometryJson)

		geometryTypeJson = {"geometryType": "esriGeometryEnvelope"}
		query.update(geometryTypeJson)

		spatialRelJson = {"spatialRel": "esriSpatialRelIntersects"}
		query.update(spatialRelJson)
		
		returnGeometryJson = {"returnGeometry": "false"}
		query.update(returnGeometryJson)

		idsOnlyJson =  {"returnIdsOnly": "false"}
		query.update(idsOnlyJson)

		countOnlyJson = {"returnCountOnly": "false"}
		query.update(countOnlyJson)
		
		groupByFieldsJson = {"groupByFieldsForStatistics": "ImageDate"}
		query.update(groupByFieldsJson)

		distinctValuesJson = {"returnDistinctValues": "false"}
		query.update(distinctValuesJson)

		trueCurvesJson = {"returnTrueCurves": "false"}
		query.update(trueCurvesJson)
		
		QgsMessageLog.logMessage("Server Item Query! " + str(query))
		return EsriQuery("/Query", query)


	@staticmethod
	def createBaseQuery(extent=None, mapExtent=None, settings = {}):
		
		QgsMessageLog.logMessage("Inside base query " +  str(settings))
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
		QgsMessageLog.logMessage("format : " + str(settings["format"])) 

		SETTINGS_LIST = [
			'size',
			'format', 
			'pixelType', 
			'noDataInterpretation', 
			'interpolation', 
			'noData', 
			'compression', 
			'compressionQuality', 
			'bandIds' ]

		for setting in SETTINGS_LIST:
			if setting in settings:
				query.update({setting: settings[setting]})
		return query 

	@staticmethod
	def createExportImageQuery(extent=None, mapExtent=None, settings={}):
		QgsMessageLog.logMessage("Inside export query " +  str(settings))
		query = EsriImageServiceQueryFactory.createBaseQuery(extent, mapExtent, settings)
		QgsMessageLog.logMessage("Query in progress for Exporting image: " + str(query))
		return EsriQuery("/ExportImage", query)

	@staticmethod
	def createExtentParam(extent):

		return {
			"size": "800,800",
			"bbox": json.dumps(extent['bbox']),
			"format": "tiff",
			"pixelType": "UNKNOWN",
			"imageSR": json.dumps(extent['spatialReference']['wkid']),
			"bboxSR": json.dumps(extent['spatialReference']['wkid'])
		}
				
	@staticmethod
	# For exporting small map thumbnails to the graphical userface. 
	#
	# settings of type dict?
	def createThumbnailQuery(extent=None, settings = None):
		query = EsriImageServiceQueryFactory.createBaseQuery(
			extent,
			extent,
			settings)
		return EsriQuery("/ExportImage", query)

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

class Settings:
   
	IMAGE_FORMATS = ['', 'tiff', 'jpgpng', 'png', 'png8', 'png24', 'jpg', 'bmp', 'gif', 'png32', 'bip', 'bsq', 'lerc']
	PIXEL_TYPES = ['', 'UNKNOWN','C128', 'C64', 'F32', 'F64', 'S16', 'S32', 'S8', 'U1', 'U16', 'U2', 'U32', 'U4', 'U8', 'UNKNOWN']
	NO_DATA_INTERPRETATIONS = ['', 'esriNoDataMatchAny', 'esriNoDataMatchAll']
	INTERPOLATIONS = ['', 'RSP_BilinearInterpolation', 'RSP_CubicConvolution', 'RSP_Majority', 'RSP_NearestNeighbor']

	size = None
	format = None
	pixelType = None
	noDataInterpretation = None
	interpolation = None 
	noData = None 
	compression = None
	compressionQuality = None
	bandIds = None
	renderingRule = None
	mosaicRule = None
	time = None

	# A list of the raster functions available.
	rasterFunctions = {}

	#Takes a Dict
	def updateValues(self, nextSettings):
		self.size = nextSettings['size']
		self.format = nextSettings['format']
		self.pixelType = nextSettings['pixelType']
		self.noDataInterpretation = nextSettings['noDataInterpretation']
		self.interpolation = nextSettings['interpolation']
		self.noData = nextSettings['noData']
		self.compression = nextSettings['compression']
		self.compressionQuality = nextSettings['compressionQuality']
		self.bandIds = nextSettings['bandIds']
		self.renderingRule = nextSettings['renderingRule']
		self.mosaicRule = nextSettings['mosaicRule']			
		self.time = nextSettings['time']	

	def getDict(self):
		return {
			'size':self.size,
			'format':self.format,
			'pixelType':self.pixelType,
			'noDataInterpretation':self.noDataInterpretation,
			'interpolation':self.interpolation, 
			'noData':self.noData,
			'compression':self.compression, 
			'compressionQuality':self.compressionQuality, 
			'bandIds':self.bandIds,
			'renderingRule':self.renderingRule,
			'mosaicRule':self.mosaicRule,
			'time':self.time
			}

	def setCurrentRasterFunction(self, index):
		if index >= 0 and self.rasterFunctions is not None:
			self.renderingRule = json.dumps({"rasterFunction": self.rasterFunctions[index]["name"]})

# An ImageSpecification is an object which contains all the information
# that pertains the acquiring of an image.
# 
# It is only created by a Connection object. Therefore, a Connection and an
# ImageSpecification are both needed to download images through the EsriUpdateService.
class ImageSpecification:
	aspectRatio = None
	customFilter = None
	rasterFunctions = None
	currentRasterFunction = None
	metaInfo = None
	width = None
	height = None
	settings = Settings()

	def setTime(self, low, high):
		self.settings.time = [low, high]
	
	# Returns the most recent time extent, none if there is no time extent.
	def getTimeStamp(self):
		timeStamp = self.settings.time[1]
		if not timeStamp:
			return self.settings.time[0]

		#Remove the milliseconds (last three digits)
		timeStamp = timeStamp / 1000
		return time.strftime('%Y-%m-%d', time.localtime(timeStamp))

	#Configures image spec from meta info.
	def configure(self, metaInfo, maxWidth, maxHeight, limLow, limHigh, format):
		self.metaInfo = metaInfo
		self.setAspectRatio()
		self.setImageSize(maxWidth, maxHeight)
		#Timestamp is not the real time stamp but the upper boundary.
		self.setTime(limLow, limHigh) 
		self.settings.format = format

	def setAspectRatio(self):
		#TODO: Image aspect ratio currently does not consider 
		# special case where the pixel size is uneven between X Y axis.
		
		x = self.metaInfo.extent['bbox']['xmax']
		y = self.metaInfo.extent['bbox']['ymax']
		
		if x < 0:
			x = x *-1
		if y < 0:
			y = y * -1
		ratio = float(x)/y

		# Ratio must not be too small.
		if ratio < 0.2:
			ratio += 0.4

		self.aspectRatio = ratio

	# Acquires a max size from a set width and height while keeping the aspect ratio (width/height)
	def setImageSize(self, maxWidth = 100, maxHeight = 100):
		width = self.aspectRatio
		height = 1
		while (True):
			if (width*2 > maxWidth or height*2 > maxHeight):
			   break;

			width = width * 2
			height = height * 2
		self.settings.size = str(int(width)) + "," + str(int(height))
		self.width = int(width)
		self.height = int(height)

	# Parameters: Extent object. Bounding box IS an extent it would seem.
	def updateBoundingBoxByExtent(self, extent):
		self.metaInfo.extent = extent

	def updateBoundingBoxByRectangle(self, qgsRectangle, authId):
		spacialReferenceWkid = self.extractWkidFromAuthId(authId)
		QgsMessageLog.logMessage(" Updating bounding box: " + str(qgsRectangle.xMinimum()) + ", " + str(qgsRectangle.yMinimum()) + ", " + str(qgsRectangle.xMaximum()) + ", " + str(qgsRectangle.yMaximum()))
		self.metaInfo.extent = {
						"bbox":
						{
							"xmin":qgsRectangle.xMinimum(),
							"ymin":qgsRectangle.yMinimum(),
							"xmax":qgsRectangle.xMaximum(),
							"ymax":qgsRectangle.yMaximum()
						},
						"spatialReference": 
						{
							"wkid":spacialReferenceWkid
						}
					  }

	def clearBoundingBox(self):
		self.metaInfo.extent = None        
   
	def createMetaDataAbstract(self):
		meta = ""
		if self.metaInfo.extent is not None:
			meta += "bbox: "+json.dumps(self.metaInfo.extent)+"\n\n"
		if self.customFilter is not None:
			meta += "filter:"+json.dumps(self.customFilter)
		return meta
	
	def extractWkidFromAuthId(self, authId):
		try:
			return int(authId.split(":")[1])
		except ValueError:
			raise InvalidCrsIdException(authId)

class Connection:    
	basicUrl = None    
	name = None    
	authMethod = None
	username = None
	password = None
	srcPath = None
	conId = None
	serviceTimeExtent = (None, None)
	metaInfo = None
	# Auth is the auth header for requests.
	auth = None

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
		#connection.metaInfo = connection.createMetaInfo() 
		return connection

	def configure(self, validator):
		try:

			# Configure meta authorization method
			query =  EsriImageServiceQueryFactory.createMetaInformationQuery()
			response = self.connect(query)
			if response.status_code != 200: 
				if "www-authenticate" in response.headers:
					if "NTLM, Negotiate" in response.headers["www-authenticate"]:
						self.authMethod = ConnectionAuthType.NTLM
					else:
						self.authMethod = ConnectionAuthType.BasicAuthetication
			
		except ValueError as e:
			QgsMessageLog.logMessage("error:  " + str(e))	
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
	

	def updateAuth(self, username, password):
		self.username = username
		self.password = password

	def createMetaInfo(self):
		query = EsriImageServiceQueryFactory.createMetaInformationQuery()   
		try:
			request = requests.post(self.basicUrl + query.getUrlAddon(), params=query.getParams(), auth=self.auth, timeout=180)
			metaJson = request.json()
			metaInfo = EsriLayerMetaInformation.createFromMetaJson(metaJson)
			return metaInfo

		except ValueError as e:
			QgsMessageLog.logMessage("error in createMetaInfo:  " + str(e))	
			return False

	#  Creates and returns an ImageSpecification object.
	#  Requires that the correct auth is set, otherwise fails.
	#
	def newImageSpecification(self, maxWidth, maxHeight, limLow, limHigh, format):
		imageSpec = ImageSpecification()
		if not self.metaInfo:
			self.metaInfo  = self.createMetaInfo() 
		
		if not self.metaInfo:
			return False
		imageSpec.configure(
			self.metaInfo,
			maxWidth,
			maxHeight,
			limLow,
			limHigh,
			format)
		return imageSpec

	def connect(self, query):       
		try: 
			QgsMessageLog.logMessage("Query in connect: " + str(self.username) + " " + str(self.password))
			if self.authMethod != ConnectionAuthType.NoAuth and self.username and self.password:
				QgsMessageLog.logMessage("Pass and user : " + str(self.username) + " " + str(self.password))
				if self.authMethod == ConnectionAuthType.NTLM:                    
					self.auth = requests_ntlm.HttpNtlmAuth(self.username, self.password)
				if self.authMethod == ConnectionAuthType.BasicAuthetication:
					self.auth = (self.username, self.password) 
			request = requests.post(self.basicUrl + query.getUrlAddon(), params=query.getParams(), auth=self.auth, timeout=180)            
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
		connected = self.connect(query)
		QgsMessageLog.logMessage(str(connected))
		return connected.json()
									
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
	

class EsriRasterLayer:
	qgsRasterLayer = None        
	connection = None
	imageSpec = None
	
	@staticmethod
	def create(connection, imageSpec, srcPath):
		esriLayer = EsriRasterLayer()
		esriLayer.connection = connection
		esriLayer.imageSpec = imageSpec
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
	   
		#extent = json.dumps(self.connection.bbBox) if self.connection.bbBox is not None else ""
		#extent = self.connection.bbBox if self.connection.bbBox is not None else ""
		#self.qgsRasterLayer.setCustomProperty("arcgiscon_connection_extent", extent)
	   
		self.qgsRasterLayer.setDataUrl(self.connection.basicUrl)
					  
