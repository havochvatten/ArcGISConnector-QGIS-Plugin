# ArcGIS Image Server Connector. 

## Summary
**Welcome to this open source [QGIS](https://qgis.org/en/site/) plugin.**
The purpose of the plugin is to enable users to browse and manipulate raster images, in particular satellite images. It does this through connecting [QGIS](https://qgis.org/en/site/) to ArcGIS Image Servers. However, the way the *hosts*, the [*Image Services*](https://developers.arcgis.com/rest/services-reference/image-service.htm), use the [ArcGis REST API](https://developers.arcgis.com/documentation/core-concepts/rest-api/) does not follow a universal standard. Therefore, the plugin suffers from compability issues toward some image servers. It is, however, compatible with most image servers that index their data with *dates*, and *names*. That being said, the plugin is currently in an alpha release state and we hope that the community will find it useful enough to continue its development.

The secondary purpose of the plugin is to stray away from the convoluted interaction design that is common in both QGIS and ArcGis. Its core functionality puts emphasis on four values; being *visual*, *interactive*, *simple*, and the interactions leading to *predictable* results. For the future of the plugin, we hope that those who take up the banner choose to hold on to these values. The current alpha release is on the right path, yet there are several issues we propose be resolved for future releases.

## Background

The project was set in motion by the [*Swedish Agency for Marine and Water Management*](https://www.havochvatten.se/en) to enable other agencies, and the public, ease of access to raster data in QGIS for environmental analyses. The project is a fork of [ArcGIS_REST_API_Connector_Plugin](http://giswiki.hsr.ch/QGIS_ArcGIS_REST_API_Connector_Plugin) by Geometa Lab.

## Limitations
* The plugin was developed for QGIS 2, and is currently not compatible with QGIS 3+. 
* The plugin currently only supports logging in to image servers directly, meaning any image service url that ends with *'/ImageServer'*. 
* There is currently no support for saving and loading a project with raster layers.

## How to Use
In your QGIS instance, you can download the latest version of the *ArcGIS Image Server Connector* plugin under *'Plugins --> Manage and Install Plugins'* tab. Currently, you have to open the *'Settings'* tab and enable the *'Show also experimental plugins'* to see the plugin. Once installed, the plugin will appear as an icon on the *'Manage Layers Toolbar'*.

### Example Servers & Hosts

[The Swedish Forest Agency (Image Service)](https://geodata.skogsstyrelsen.se/arcgis/rest/services/)

[The Swedish County Administrative Board (Image Service)](http://ext-geodata.lansstyrelsen.se/arcgis/rest/services/raster) 

[London Aerial 2017 (Image Server)](https://logis.loudoun.gov/image/rest/services/Aerial/COLOR_2017/ImageServer)

## Development
The plugin is developed using Python 2. It uses a version of the [*model-view-controller*](https://en.wikipedia.org/wiki/Model%E2%80%93view%E2%80%93controller) design pattern. The model aims to only contain data to be manipulated by the controller and not use any third party modules. Currently, we use a service module to tie the functionality together between view controllers and the model. The controllers handle the interaction between the model and the user interface, each controller handling a single such interface. The current architecture leaves a lot of space for improvement, and is, just as the plugin, in an alpha state.

## Backlog for Future Development 
For the future of this project we have composed a backlog for issues we recommend looking into.

### General

* Implement a test Suite for stability
* Save and load project feature
* QGIS 3 support, ie. upgrade to Python 3.
* Add support for more server configurations. Currently quite experimental with the type of servers it supports.

### QGIS main view

* Optimize how the image is updated in the **main view**, to avoid making new calls to the server anytime the image extent is changed (eg. moving in any cardinal direciton).
* Optimize the pixel density of the layer image in QGIS **main view** to be crisp and clear at all times. Perhaps use filtering or some algorithm to calculate the resolution of the main grid to use as a guideline.
* Bugfix: When the image is loaded at first it loaded twice and downscaled the second time. Make it load just the one time.
 
### Settings view

* Update the **settings view** to be in the same style as the other views. There are resources for stylesheets in the *gui* folder.
* In the **settings view**, show raster function options as a grid of thumbnails showing previews of each raster function, instead of a drop down list with no preview.
* Reload the extent when clicking ok/apply such that the mosaic rule is applied immediately.
* Suggest more (auto complete?) in each field, to alleviate the process for the user. (eg based on earlier usages, or some smart stuff you can come up with.)
* In the custom raster function field, allow the user to write stuff without having to add the syntactic stuff like '{}' brackets.

### Create layer view

* ***Priority*:** Functionality for the search field to filter items that are on the server. It is almost already done, and the finishing step is to intergrate it in *'layer_dialog_controller.py'*. There is a TODO in the file and some code that has been commented out, have a look there to find where to start. Currently it 'can' filter server items but it crashes because there are usually too many (Only 'works' for image servers with dates on their server items). Also, there is no regulation of how to handle filtered images and then going back to showing all images.
* Bugfix: The grid already removes 'empty' or malformed images. However, it creates white space where these widgets were supposed to be. Please make it go away, such that the grid is *compact*.
* Bugfix: When filtering stuff in the search field one image just sticks to the top left corner of the grid. Please remove this unholy beast.
* Bugfix the crashing when you close the application with the 'create layer' view open.
* Load new items even when scrolling with the scroll slider. Currently it only loads new items when scrolling with the mouse wheel.
* Generalize UI in the **create layer view** for when there are more than one image per day (date items). Currently only shows the image date.
* Unclear whether servers with named server items have more than one image. If they do, and it's possible to somehow get them using some of the server functions like *'ExportImage'*, show them in the **create layer** view too. So far, we have not found a way to browse named images on the server as the API for *'ExportImage'* doesn't seem to contain a suitable field for that.

### Login view

* Make the connect button go back to its initial color when clicked, instead of awkwardly staying in the 'clicked' state.
* Add a dialog with help text when clicking the *'?'* button on the top right, or remove it completely. For example, it could show a dialog with some basic information about how to login, and some example servers. Maybe some visual aid showing how to navigate the plugin.
* Add autofill suggestions based on earlier successful logins.
