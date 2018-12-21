# -*- coding: utf-8 -*-
"""
/***************************************************************************
 ArcGisImageServerConnector
                                 A QGIS plugin
 ArcGIS REST API ImageServer Connector
                             -------------------
        begin                : 2018-08-31
        copyright            : (C) 2018 by Anton Myrholm, Swedish Agency for Marine and Water Management, SwAM.
        email                : anton.myrholm@havochvatten.se
        git sha              : $Format:%H$
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/

Original by:

/***************************************************************************
 ArcGisConnector
                                 A QGIS plugin
 ArcGIS REST API Connector
                             -------------------
        begin                : 2015-05-27
        copyright            : (C) 2015 by geometalab
        email                : geometalab@gmail.com
        git sha              : $Format:%H$
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
 This script initializes the plugin, making it known to QGIS.
"""

# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Load ArcGisConnector class from file ArcGisImageServerConnector.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    #
    from arcgiscon_plugin import ArcGisConnector
    return ArcGisConnector(iface)
