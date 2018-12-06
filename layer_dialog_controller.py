from PyQt4.QtCore import QObject, QCoreApplication, Qt, QDate, QTime, QRect, Qt, pyqtSignal
from PyQt4.QtGui import QPixmap,  QSizePolicy, QMovie
from arcgiscon_model import Connection, EsriRasterLayer, EsriConnectionJSONValidatorLayer
from arcgiscon_service import NotificationHandler, EsriUpdateWorker, TimeCatcher
from qgis.core import QgsMessageLog, QgsMapLayerRegistry
from arcgiscon_ui import LayerDialog, ImageItemWidget
from event_handling import Event
from PIL import Image
import os
import threading
import numpy as np
import PyQt4.QtGui as QtGui



class LayerDialogController(QObject):
	#Variables ---------------------

	# Our QT interface object
	iface = None
	layerDialogUI = None
	# Connection to server.
	connection = None
	# 'Event' Takes care of throwing events when there is need for that.
	event = None
	# Update service for downloading thumbnail images etc.
	updateService = None
	rasterLayers = None
	legendActions = None
	timeCatcher = None
	lastScrollPos = 0

	# Constants--------------------
	MAX_COLUMN_AMOUNT = 3
	IMAGE_SCALE = 1.25

	#------------------------------

	def __init__(self, iface):
		QObject.__init__(self)
		self.iface = iface				
		self.layerDialogUI = LayerDialog()
		self.grid = self.layerDialogUI.imageGridWidget
		self.event = Event()
		self.imageItems = []
		self.layerDialogUI.scrolledDown.connect(self.onScrolledDown)
		self.layerDialogUI.closed.connect(self.onCloseEvent)


	# Add handler to our events
	def addEventHandler(self, handler):
		self.event += handler


	def onCloseEvent(self):
		self.clearThumbnails()

	def onScrolledDown(self, y):
		#TODO: Use the scroll position to avoid getting 300 new images instead of three.
		#if (y > self.lastScrollPos):
		#QgsMessageLog.logMessage("Y pos: " + str(y))
		self.populateImageItems(self.MAX_COLUMN_AMOUNT)
		self.updateGrid()
		self.lastScrollPos = y


	def showView(self, connection, updateService, rasterLayers, legendActions):
		self.updateService = updateService
		self.connection = connection
		self.rasterLayers = rasterLayers
		self.legendActions = legendActions
		# Create meta info (TODO? won't happen earlier currently).
		self.connection.createMetaInfo() 
		self.serverItemsInfo = self.updateService.downloadServerData(self.connection)
		self.timeCatcher = TimeCatcher(self.connection.serviceTimeExtent[0], self.connection.serviceTimeExtent[1])
		self.renderThumbnails()
		self.layerDialogUI.show()


	def renderThumbnails(self): 
		IMAGE_AMOUNT_START = 6
		# TODO: Regulate when to fill the grid, signals like window resize or 
		# scroll.
		self.populateImageItems(IMAGE_AMOUNT_START)
		self.fillGrid()


	def populateImageItems(self, amount):
		FORMAT_PNG = "png"
		FORMAT_TIFF = "tiff"
		MAX_ITEM_WIDTH = 400
		MAX_ITEM_HEIGHT = 400
		GRID_MAX_WIDTH = self.layerDialogUI.width() - 100

		pixmapSignal = pyqtSignal(QPixmap)

		loaderMovie = QMovie(os.path.join(os.path.dirname(__file__), 'loading.gif'))
		imageCount = 0
		baseSpec = imageSpec = self.connection.newImageSpecification(
				MAX_ITEM_WIDTH,
				MAX_ITEM_HEIGHT,
				self.timeCatcher.limLow,
				self.timeCatcher.limHigh,
				FORMAT_PNG)
		# Place ImageItems on the dialog.
		while (imageCount < amount):
			# TODO: Only make *One* meta information query that holds for all images.
			
			imageSpec  = self.connection.newImageFromSpec(
				baseSpec,	
				self.timeCatcher.limLow,
				self.timeCatcher.limHigh) 
			if not imageSpec:
				return

			item = ImageItemWidget(self.grid, imageSpec.width * self.IMAGE_SCALE, imageSpec.height * self.IMAGE_SCALE)
							
			# Config image item
			timeStamp = imageSpec.getTimeStamp()				
			if not timeStamp:
				timeStamp = self.connection.name
			
			# Placeholder with loader
			item.imageDateLabel.setText(timeStamp)
			item.thumbnailLabel.setMovie(loaderMovie)
			item.thumbnailLabel.setAlignment(Qt.AlignCenter)
			loaderMovie.start()

			self.imageItems.append(item)
			imageCount += 1

			# Initiate asynchronous download
			downloader = ImageDownloader(self.connection, imageSpec, self.updateService)
			downloader.downloadFinished.connect(lambda filePath, i=item: self.onDownloadThumbnail(imageSpec, filePath, i))
			downloader.start()

			# Configure widget events
			self.configureThumbnailEvents(item, imageSpec)

			#Update time catcher
			newTime = self.timeCatcher.update(imageSpec.settings.time[1])
			if not newTime:
				return

	def scaleImage(self, filePath, width, height, scalar):
		pix = QPixmap(filePath)
		pix =  pix.scaled(width * scalar , height * scalar, Qt.KeepAspectRatio)
		return pix


	def fillGrid(self):
		layout = self.grid.layout()
		for x in range(len(self.imageItems)):
			row = x / self.MAX_COLUMN_AMOUNT
			col = x % self.MAX_COLUMN_AMOUNT
			layout.addWidget(self.imageItems[x], row, col)
	
		
	def updateGrid(self):
		layout = self.grid.layout()
		newImages = len(self.imageItems) - layout.count()
		for x in range(newImages):
			row = x / self.MAX_COLUMN_AMOUNT
			col = x % self.MAX_COLUMN_AMOUNT
			layout.addWidget(self.imageItems[x], row, col)


	def configureThumbnailEvents(self, item, imageSpec):
		item.clicked.connect(lambda: self.onNewLayerClick(imageSpec))


	def onNewLayerClick(self, imageSpec):
		self.requestLayerForConnection(imageSpec)


	def requestLayerForConnection(self, imageSpec):
		LAYER_IMAGE_SIZE = [800, 800]
		self.connection.updateNamefromUrl()
		imageSpec.setSize(LAYER_IMAGE_SIZE)
		updateWorker = EsriUpdateWorker.create(
			 self.connection, imageSpec,
			 onSuccess=lambda srcPath: self.onSuccess(srcPath, imageSpec), 
			 onWarning=lambda warningMsg: self.onWarning(warningMsg), 
			 onError=lambda errorMsg: self.onError(errorMsg))	

		self.updateService.update(updateWorker)
		imageSpec.settings.imageFormat = None #To reset it for further use
		self.clearThumbnails()
		self.closeWindow()
		
	def clearThumbnails(self):
		del self.imageItems[:]

	def closeWindow(self):
		self.layerDialogUI.close()

	def onSuccess(self, srcPath, imageSpec):
		#Remove thumbnails.
		rasterLayer = EsriRasterLayer.create(self.connection, imageSpec, srcPath)
		for action in self.legendActions:
			self.iface.legendInterface().addLegendLayerActionForLayer(action, rasterLayer.qgsRasterLayer)
		QgsMapLayerRegistry.instance().addMapLayer(rasterLayer.qgsRasterLayer)
		self.rasterLayers[rasterLayer.qgsRasterLayer.id()]=rasterLayer
		self.connection.renderLocked = True

	def onDownloadThumbnail(self, imageSpec, filePath, item):
		pixmap = self.scaleImage(filePath, imageSpec.width, imageSpec.height, self.IMAGE_SCALE)
		item.thumbnailLabel.setPixmap(pixmap)


	def onWarning(self, warningMessage):
		NotificationHandler.pushWarning('['+self.connection.name+'] :', warningMessage, 5)


	def onError(self, errorMessage):
		NotificationHandler.pushError('['+self.connection.name+'] :', errorMessage, 5)

class ImageDownloader(QObject):

	downloadFinished = pyqtSignal(str)

	def __init__(self, connection, imageSpec, updateService):
		QObject.__init__(self)
		self._connection = connection
		self._imageSpec = imageSpec
		self._updateService = updateService

	def start(self):
		self._thread = threading.Thread(target=self.run)
		self._thread.start()

	def downloadPixmap(self):
		filePath = self._updateService.downloadThumbnail(self._connection, self._imageSpec)
		return filePath

	def run(self):
		filePath = self.downloadPixmap()
		self.downloadFinished.emit(filePath)