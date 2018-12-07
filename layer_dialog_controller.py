from PyQt4.QtCore import QObject, QCoreApplication, Qt, QDate, QTime, QRect, Qt, pyqtSignal
from PyQt4.QtGui import QPixmap,  QSizePolicy, QMovie
from arcgiscon_model import Connection, EsriRasterLayer, EsriConnectionJSONValidatorLayer
from arcgiscon_service import NotificationHandler, EsriUpdateWorker, ServerItemManager
from qgis.core import QgsMessageLog, QgsMapLayerRegistry
from arcgiscon_ui import LayerDialog, ImageItemWidget
from event_handling import Event
from PIL import Image, ImageChops
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
	serverItemManager = None
	lastScrollPos = 0
	serverItemInfo = []

	# Constants--------------------
	MAX_COLUMN_AMOUNT = 3
	IMAGE_SCALE = 1.25

	#------------------------------

	def __init__(self, iface):
		QObject.__init__(self)
		self.iface = iface				


	def _onSearchLineEditChanged(self, text):
		for widget in self.imageItems:
			try:
				widget.setVisible(text in widget.imageDateLabel.text())
			except:
				pass
				


	# Add handler to our events
	def addEventHandler(self, handler):
		self.event += handler

	def onCloseEvent(self):
		self.clearThumbnails()

	def onScrolledDown(self, y):
		#TODO: Use the scroll position to avoid getting 300 new images instead of three.
		#if (y > self.lastScrollPos):
		#QgsMessageLog.logMessage("Y pos: " + str(y))
		self.populateItems(self.MAX_COLUMN_AMOUNT)
		self.updateGrid()
		self.lastScrollPos = y
	

	def showView(self, connection, updateService, rasterLayers, legendActions):
		self.layerDialogUI = LayerDialog()
		self.grid = self.layerDialogUI.imageGridWidget
		self.event = Event()
		self.imageItems = []
		self.hiddenImageItems = []
		self.layerDialogUI.scrolledDown.connect(self.onScrolledDown)
		self.layerDialogUI.closed.connect(self.onCloseEvent)
		self.layerDialogUI.searchLineEdit.textEdited.connect(self._onSearchLineEditChanged)
		self.layerDialogUI.searchLineEdit.returnPressed.connect(lambda: self._onSearchLineEditChanged(self.layerDialogUI.searchLineEdit.text()))

		self.updateService = updateService
		self.connection = connection
		self.rasterLayers = rasterLayers
		self.legendActions = legendActions
		# Create meta info (TODO? won't happen earlier currently).
		self.connection.createMetaInfo() 
		self.serverItemManager = ServerItemManager(self.connection)
		self.renderThumbnails()
		self.layerDialogUI.show()

	def renderThumbnails(self): 
		IMAGE_AMOUNT_START = 6
		# TODO: Regulate when to fill the grid, signals like window resize or 
		if self.serverItemManager.keyDates in self.serverItemManager.serverItems:
			self.populateItems(IMAGE_AMOUNT_START)
		if self.serverItemManager.keyNames in self.serverItemManager.serverItems:	
			#TODO: Implement
			pass
		self.fillGrid()

	def populateItems(self, amount):
		key = self.serverItemManager.keyDates
		FORMAT_PNG = "png"
		FORMAT_TIFF = "tiff"
		MAX_ITEM_WIDTH = 400
		MAX_ITEM_HEIGHT = 400
		GRID_MAX_WIDTH = self.layerDialogUI.width() - 100

		loaderMovie = QMovie(os.path.join(os.path.dirname(__file__), 'loading.gif'))
		self.imageCount = 0

		baseSpec = imageSpec = self.connection.newImageSpecification(
				MAX_ITEM_WIDTH,
				MAX_ITEM_HEIGHT,
				self.serverItemManager.getCurrentItem(key),
				FORMAT_PNG)
		# Place ImageItems on the dialog.
		while (self.imageCount < amount):
			# TODO: Only make *One* meta information query that holds for all images.
			
			imageSpec  = self.connection.newImageFromSpec(
				baseSpec,	
				self.serverItemManager.getCurrentItem(key)) 
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
			self.imageCount += 1
			# Initiate asynchronous download
			downloader = ImageDownloader(self.connection, imageSpec, self.updateService)
			downloader.downloadFinished.connect(lambda filePath, i=item: self.onDownloadThumbnail(imageSpec, filePath, i))
			downloader.start()

			# Configure widget events
			self.configureThumbnailEvents(item, imageSpec)

			#Update time catcher
			newTime = self.serverItemManager.update()
			if not newTime:
				return

	def scaleImage(self, filePath, width, height, scalar):
		pix = QPixmap(filePath)
		pix =  pix.scaled(width * scalar , height * scalar, Qt.KeepAspectRatio)
		return pix

	def fillGrid(self):
		layout = self.grid.layout()
		for x in range(len(self.imageItems)):
			QgsMessageLog.logMessage("Item on screen " + str(self.imageItems[x].imageDateLabel.text()))
			row = x / self.MAX_COLUMN_AMOUNT
			col = x % self.MAX_COLUMN_AMOUNT
			layout.addWidget(self.imageItems[x], row, col)
	
	
	def getColorSpan(self, filePath):
		img = Image.open(filePath)
		imageRGB = img.convert('RGB')
		colorSpan = imageRGB.getextrema()
		return colorSpan

	def updateGrid(self):
		layout = self.grid.layout()
		newImages = len(self.imageItems) - layout.count()
		for x in range(newImages):
			row = x / self.MAX_COLUMN_AMOUNT
			col = x % self.MAX_COLUMN_AMOUNT
			try:
				item = self.imageItems[x]
				layout.addWidget(item, row, col)
			except:
				pass
			

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

	def removeImageItemWidget(self, widget):
		layout = self.grid.layout()
		newList = []
		for x in range(len(self.imageItems)-1):
			newList.append(self.imageItems[x])
			if self.imageItems[x] == widget:
				pass
		self.imageItems = filter(lambda x: x is not None, newList)
		widget.deleteLater()
		QgsMessageLog.logMessage("removed empty widget: "  + widget.imageDateLabel.text())

	def onDownloadThumbnail(self, imageSpec, filePath, item):
		pixmap = self.scaleImage(filePath, imageSpec.width, imageSpec.height, self.IMAGE_SCALE)
		item.thumbnailLabel.setPixmap(pixmap)
		colorSpan =  self.getColorSpan(filePath)
		QgsMessageLog.logMessage("Date color" + item.imageDateLabel.text() + " " + str(colorSpan))
		emptyImage = True
		for x in colorSpan:
			if x[0] != x[1]:
				emptyImage = False
		if emptyImage:
			QgsMessageLog.logMessage("Removing date " + item.imageDateLabel.text() + " " + str(colorSpan))
			self.removeImageItemWidget(item)


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