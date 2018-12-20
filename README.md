# ArcGIS Image Server Connector. 

## Summary
**Welcome to this open source [QGIS](https://qgis.org/en/site/) plugin.**
The purpose of the plugin is to enable users to browse and manipulate raster images, in particular satellite images. It does this through connecting [QGIS](https://qgis.org/en/site/) to ArcGIS Image Servers. However, the way the *hosts*, the [*Image Services*](https://developers.arcgis.com/rest/services-reference/image-service.htm), use the [ArcGis REST API](https://developers.arcgis.com/documentation/core-concepts/rest-api/) does not follow a universal standard. Therefore, the plugin suffers from compability issues toward some image servers. It is, however, compatible with most image servers that index their data with *dates*, and *names*. That being said, the plugin is currently in an alpha release state and we hope that the community will find it useful enough to continue its development.

The secondary purpose of the plugin is to stray away from the convoluted interaction design that is common in both QGIS and ArcGis. Its core functionality puts emphasis on four values; being *visual*, *interactive*, *simple*, and the interactions leading to *predictable* results. For the future of the plugin, we hope that those who take up the banner choose to hold on to these values. The current alpha release is on the right path, yet there are several issues we propose be resolved for future releases.

## Background

The project was set in motion by the [*Swedish Agency for Marine and Water Management*](https://www.havochvatten.se/en) to enable other agencies, and the public, ease of access to raster data in QGIS for environmental analyses. The project is a fork of [ArcGIS_REST_API_Connector_Plugin](http://giswiki.hsr.ch/QGIS_ArcGIS_REST_API_Connector_Plugin) by Geometa Lab.

## Limitations
The plugin was developed for QGIS 2, and is currently not compatible with QGIS 3+. The plugin currently only supports logging in to image servers directly, meaning any image service url that ends with *'/ImageServer'*.

## How to Use
In your QGIS instance, you can download the latest version of the *ArcGIS Image Server Connector* plugin under *'Plugins --> Manage and Install Plugins'* tab. Currently, you have to open the *'Settings'* tab and enable the *'Show also experimental plugins'* to see the plugin. Once installed, the plugin will appear as an icon on the *'Manage Layers Toolbar'*.

### Example Servers & Hosts

[The Swedish Forest Agency (Image Service)](https://geodata.skogsstyrelsen.se/arcgis/rest/services/)

[The Swedish County Administrative Board (Image Service)](http://ext-geodata.lansstyrelsen.se/arcgis/rest/services/raster) 

[London Aerial 2017 (Image Server)](https://logis.loudoun.gov/image/rest/services/Aerial/COLOR_2017/ImageServer)

## Development
The plugin is developed using Python 2. It uses a version of the [*model-view-controller*](https://en.wikipedia.org/wiki/Model%E2%80%93view%E2%80%93controller) design pattern. The model aims to only contain data to be manipulated by the controller and not use any third party modules. Currently, we use a service module to tie the functionality together between view controllers and the model. The controllers handle the interaction between the model and the user interface, each controller handling a single such interface. The current architecture leaves a lot of space for improvement, and is, just as the plugin, in an alpha state.

## Backlog for Future Development 
For the future of this project we have composed a list of features to be implemented.  

**Implement a test Suite for stability**
