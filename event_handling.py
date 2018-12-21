from PyQt4.QtCore import QObject


# EVENT TYPES (Static variables / Enum...)
# Defines the event types that exist in the plugin
LOGIN_SUCCESS = 'Login Success'


# Publisher of events, typically a controller object.
# Apparently inheritance doesn't work in Python 2 so just
# disregard this until 
class Publisher(QObject):
    event = None
	
    def __init__(self):
        QObject.__init__(self)
        self.event = Event()

    # Add handler to our events
	def addEventHandler(self, handler):
		self.event.add(handler)

# Events for event handling, especially routing between views. 
# 'Handler' is typically the main plugin object, but can be more than one.
class Event():
    
    def __init__(self):
        self.handlers = []
    
    def add(self, handler):
        self.handlers.append(handler)
        return self
    
    def remove(self, handler):
        self.handlers.remove(handler)
        return self
    
    def fire(self, sender, earg=None):
        for handler in self.handlers:
            handler(sender, earg)
    
    __iadd__ = add
    __isub__ = remove
    __call__ = fire