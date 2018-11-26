from PyQt4.QtCore import QObject, QCoreApplication, Qt, QDate, QTime, QRect
from PyQt4.QtGui import QPixmap,  QSizePolicy
from arcgiscon_model import Connection, EsriRasterLayer, EsriConnectionJSONValidatorLayer
from arcgiscon_service import NotificationHandler, EsriUpdateWorker
from qgis.core import QgsMessageLog
from arcgiscon_ui import ImageServerDashboard
from event_handling import Event

class DashboardController(QObject):
	
	# Our QT interface object
	iface = None

	# The UI object, ultimately designed in QT designer.
	dashboardUI = None

	# Connection to server.
	connection = None

	# 'Event' Takes care of throwing events when there is need for that.
	event = None

	# Update service for downloading thumbnail images etc.
	updateService = None
	
	#Our layers
	rasterLayers = None
	
	#If we need to write anything to the legend.
	legendActions = None

	def __init__(self, iface):
		QObject.__init__(self)
		self.iface = iface				
		self.dashboardUI = ImageServerDashboard()
		self.event = Event()

    # Add handler to our events
	def addEventHandler(self, handler):
		self.event += handler

	def showView(self, connection, updateService, rasterLayers, legendActions):
		self.connection = connection
		self.updateService = updateService
		self.rasterLayers = rasterLayers
		self.legendActions = legendActions
		self.renderThumbnails()
		self.dashboardUI.show()

	def renderThumbnails(self): 
		thumbnailLabel = self.dashboardUI.thumbnailLabel	
		filePath = self.updateService.downloadThumbnail(self.connection)			
		pixmap = QPixmap(filePath)

		rect = QRect(0, 0, thumbnailLabel.minimumWidth(), thumbnailLabel.minimumHeight())
		cropped = pixmap.copy(rect);
		thumbnailLabel.setPixmap(cropped)