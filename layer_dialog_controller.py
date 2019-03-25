from __future__ import absolute_import
from builtins import range

from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtGui import QMovie, QPixmap
from PyQt5 import Qt

from .arcgiscon_model import EsriRasterLayer
from .arcgiscon_service import NotificationHandler, EsriUpdateWorker, ServerItemManager
from qgis.core import QgsMessageLog, QgsProject
from .arcgiscon_ui import LayerDialog, ImageItemWidget
from .event_handling import Event
from .PIL import Image
import os
import threading

class LayerDialogController(QObject):
    #Variables ---------------------

    # Our QT interface object
    EMPTY_GRID_MESSAGE = "No images could be found..."
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
    serverExtentNotRepresentative = False
    lastScrollPos = 0
    imageCount = 0
    serverItemInfo = []
    # Constants--------------------
    MAX_COLUMN_AMOUNT = 3
    IMAGE_SCALE = 1.25

    #------------------------------

    def __init__(self, iface):
        QObject.__init__(self)
        self.iface = iface				

    def _onSearchLineEditChanged(self, text):
        #TODO: Show filtered items in a good way. Almost done.
        # filterItems = self.serverItemManager.filterItems
        # if filterItems is not {}:
        # 	#Filter existing server items on the string.
        # 	dateItems = []
        # 	for key in self.serverItemManager.filterItems:
        # 		if text in key:
        # 			dateItems.append(filterItems[key])
        #	#Add those filtered items to the screen.
        # 	self.clearThumbnails()
        # 	self.populateItems(-1, [dateItems[0], dateItems[1], dateItems[2], dateItems[3], dateItems[4], dateItems[5]])
            
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
        self.populateItems(self.MAX_COLUMN_AMOUNT*2)
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
        self.layerDialogUI.infoLabel.clear()

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

        entryContainsDates = self.serverItemManager.serverItems[self.serverItemManager.keyDates] != []
        entryContainsNames = self.serverItemManager.serverItems[self.serverItemManager.keyNames] != []

        if entryContainsDates:
            self.populateItems(IMAGE_AMOUNT_START)
        elif entryContainsNames:	
            self.populateNamedItems(IMAGE_AMOUNT_START)
        elif self.serverItemManager.serverNotQueryable:
            self.showNonQueryableImage()
        self.updateGrid()

    def createAndConfigureImageItem(self, imageSpec, name):
        imageSpec.name = name
        loaderMovie = QMovie(':/plugins/ImageServerConnector/icons/loading.gif')
        item = ImageItemWidget(self.grid, imageSpec.width * self.IMAGE_SCALE, imageSpec.height * self.IMAGE_SCALE)
        item.imageDateLabel.setText(name) 
        item.thumbnailLabel.setMovie(loaderMovie)
        item.thumbnailLabel.setAlignment(Qt.AlignCenter)
        loaderMovie.start()
        # Initiate asynchronous download
        downloader = ImageDownloader(self.connection, imageSpec, self.updateService)
        downloader.downloadFinished.connect(lambda filePath, i=item: self.onDownloadThumbnail(imageSpec, filePath, i))
        downloader.start()
        # Configure widget events
        self.configureThumbnailEvents(item, imageSpec)
        return item

    def showNonQueryableImage(self):
        FORMAT_PNG = "png"
        FORMAT_TIFF = "tiff"
        MAX_ITEM_WIDTH = 400
        MAX_ITEM_HEIGHT = 400
        GRID_MAX_WIDTH = self.layerDialogUI.width() - 100
        imageSpec = self.connection.newImageSpecification(
                    MAX_ITEM_WIDTH,
                    MAX_ITEM_HEIGHT,
                    None,
                    FORMAT_PNG)
        if not imageSpec:
                return
        itemName = self.connection.name
        item = self.createAndConfigureImageItem(imageSpec, itemName)
        

    def populateNamedItems(self, amount):
        key = self.serverItemManager.keyNames
        if self.serverItemManager.serverItems[key] != []:
            FORMAT_PNG = "png"
            FORMAT_TIFF = "tiff"
            MAX_ITEM_WIDTH = 400
            MAX_ITEM_HEIGHT = 400
            GRID_MAX_WIDTH = self.layerDialogUI.width() - 100
            self.imageCount = 0

            imageSpec = self.connection.newImageSpecification(
                    MAX_ITEM_WIDTH,
                    MAX_ITEM_HEIGHT,
                    None,
                    FORMAT_PNG)

            if not imageSpec:
                return
            name = self.serverItemManager.getCurrentItem(key)
            
            # Add new image item
            item = self.createAndConfigureImageItem(imageSpec, name)
            self.imageItems.append(item)
            self.imageCount += 1
    
            #Update time catcher
            newTime = self.serverItemManager.update(key)
            if not newTime:
                return

    def populateItems(self, amount, source = None):
        key = self.serverItemManager.keyDates
        FORMAT_PNG = "png"
        FORMAT_TIFF = "tiff"
        MAX_ITEM_WIDTH = 400
        MAX_ITEM_HEIGHT = 400
        GRID_MAX_WIDTH = self.layerDialogUI.width() - 100
        self.imageCount = 0
        
        if source is not None:
            self.clearThumbnails()
            for date in source:	
                baseSpec = imageSpec = self.connection.newImageSpecification(
                    MAX_ITEM_WIDTH,
                    MAX_ITEM_HEIGHT,
                    source[0],
                    FORMAT_PNG)	
                    # Place ImageItems on the dialog.
                
                for x in range(len(source)-2):
                    # TODO: Only make *One* meta information query that holds for all images.
                    imageSpec  = self.connection.newImageFromSpec(
                        baseSpec,	
                        source[x+1]) 
                    if not imageSpec:
                        return
                    # Config image item
                    itemName = imageSpec.getTimeStamp()				
                    if not itemName:
                        itemName = self.connection.name
                    
                    item = self.createAndConfigureImageItem(imageSpec, itemName)
                    self.imageItems.append(item)
                    self.imageCount += 1
                return			
    
        if self.serverItemManager.serverItems[key] != []:
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
        
                # Config image item
                itemName = imageSpec.getTimeStamp()				
                if not itemName:
                    itemName = self.connection.name
                
                item = self.createAndConfigureImageItem(imageSpec, itemName)
                self.imageItems.append(item)
                self.imageCount += 1

                #Update time catcher
                newTime = self.serverItemManager.update(key)
                if not newTime:
                    return

    def scaleImage(self, filePath, width, height, scalar):
        pix = QPixmap(filePath)
        pix = pix.scaled(width * scalar, height * scalar, Qt.KeepAspectRatio)
        return pix
    
    def getColorSpan(self, filePath):
        try:
            img = Image.open(filePath)
            imageRGB = img.convert('RGB')
            colorSpan = imageRGB.getextrema()
            return colorSpan
        except:
            QgsMessageLog.logMessage("IOException, unsupported format / corrupted file.")
            return None
        

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
        self.updateInfoMessage()

    def updateInfoMessage(self):
        if self.grid.layout().isNull():
            #TODO: Make it function properly.
            pass
            #self.layerDialogUI.infoLabel.setText(self.EMPTY_GRID_MESSAGE)
        else:
            self.layerDialogUI.infoLabel.clear()
            

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
        layout = self.layerDialogUI.scrollArea.widget().layout()
        self.layerDialogUI.clearLayout(layout)

    def closeWindow(self):
        self.layerDialogUI.close()

    def onSuccess(self, srcPath, imageSpec):
        #Remove thumbnails.
        rasterLayer = EsriRasterLayer.create(self.connection, imageSpec, srcPath)
        for action in self.legendActions:
            self.iface.addCustomActionForLayer(action, rasterLayer.qgsRasterLayer)
        QgsProject.instance().addMapLayer(rasterLayer.qgsRasterLayer)
        self.rasterLayers[rasterLayer.qgsRasterLayer.id()]=rasterLayer
        self.connection.renderLocked = True

    def removeImageItemWidget(self, widget):
        layout = self.grid.layout()
        newList = []
        for x in range(len(self.imageItems)-1):
            newList.append(self.imageItems[x])
            if self.imageItems[x] == widget:
                pass
        self.imageItems = [x for x in newList if x is not None]
        widget.deleteLater()
        self.updateInfoMessage()
    
    def fileIsHealthy(self, filePath):
        try:
            img = Image.open(filePath)
            return True
        except:
            os.remove(filePath)
            return False
    
    def startImageScrapingJob(self, imageSpec, item):
        downloader = ImageDownloader(self.connection, imageSpec, self.updateService, True)
        downloader.downloadFinished.connect(lambda filePath, i=item: self.onDownloadThumbnail(imageSpec, filePath, i))
        downloader.start()


    def startDownloadJob(self, imageSpec, item):
        # Initiate asynchronous download
        downloader = ImageDownloader(self.connection, imageSpec, self.updateService)
        downloader.downloadFinished.connect(lambda filePath, i=item: self.onDownloadThumbnail(imageSpec, filePath, i))
        downloader.start()

    def onDownloadThumbnail(self, imageSpec, filePath, item):
        if self.fileIsHealthy(filePath):
            pixmap = self.scaleImage(filePath, imageSpec.width, imageSpec.height, self.IMAGE_SCALE)
            item.thumbnailLabel.setPixmap(pixmap)
            colorSpan =  self.getColorSpan(filePath)
            emptyImage = True
            if colorSpan:
                for x in colorSpan:
                    if x[0] != x[1]:
                        emptyImage = False
                if emptyImage:
                    self.removeImageItemWidget(item)
        else:
            newWidth = 300
            newHeight = 300
            self.serverExtentNotRepresentative = True
            item.configureFromDimensions(newWidth,newHeight)
            newSpec = imageSpec.copy() 
            newSpec.setSize([newWidth,newHeight])
            newSpec.setAspectRatio(newWidth,newHeight)
            self.startImageScrapingJob(newSpec,item)

    def onWarning(self, warningMessage):
        NotificationHandler.pushWarning('['+self.connection.name+'] :', warningMessage, 5)


    def onError(self, errorMessage):
        NotificationHandler.pushError('['+self.connection.name+'] :', errorMessage, 5)

class ImageDownloader(QObject):

    downloadFinished = pyqtSignal(str)

    def __init__(self, connection, imageSpec, updateService, retryFromIncompatible = False):
        QObject.__init__(self)
        self._connection = connection
        self._imageSpec = imageSpec
        self._updateService = updateService
        self.retryFromIncompatible = retryFromIncompatible

    def start(self):
        self._thread = threading.Thread(target=self.run)
        self._thread.start()

    def downloadAsJson(self):
        filePath = self._updateService.downloadThumbnail(self._connection, self._imageSpec)
        return filePath

    def downloadAsImage(self):
        filePath = self._updateService.downloadImageDirectly(self._connection, self._imageSpec)
        return filePath

    def run(self):
        filePath = None
        if self.retryFromIncompatible:
            filePath = self.downloadAsImage()
        else:
            filePath = self.downloadAsJson()
        self.downloadFinished.emit(filePath)

