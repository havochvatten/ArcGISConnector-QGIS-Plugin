# -*- coding: utf-8 -*-
from __future__ import absolute_import

# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Load ArcGisConnector class from file ArcGisImageServerConnector.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    #
    from .arcgiscon_plugin import ArcGisConnector
    return ArcGisConnector(iface)
