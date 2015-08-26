define([
	"dijit/_WidgetBase",
    "dojo/Evented",
    "dojo/_base/declare",
    "dojo/_base/lang",
    "dojo/_base/array",
    "dojo/parser",
    "dijit/_TemplatedMixin",
	"dojo/json", 

    "dojo/on",
	"dojo/dom",
    "dojo/dom-construct",
    "dojo/dom-class",
    "dojo/dom-style",
    "dojo/ready", 

    "dojo/request/iframe",
    "dojo/request/xhr", 
	
    "esri/layers/FeatureLayer",
    "esri/dijit/PopupTemplate",
    "esri/geometry/Point",
    "esri/geometry/Polyline",
    "esri/geometry/Polygon",
    "esri/geometry/Extent",
    "esri/graphic",	
	"esri/SpatialReference",
	
	"esri/renderers/SimpleRenderer", 
	"esri/Color", 
	"esri/symbols/SimpleMarkerSymbol", 
    "esri/symbols/SimpleFillSymbol", 
	"esri/symbols/SimpleLineSymbol",

    "dojo/text!apc/dijit/templates/FileUploader.html", // template html
    "apc/util/SvgSymbol" // util class
], function(
	_WidgetBase,
    Evented, declare, lang, array, 
    parser, _TemplatedMixin, JSON, 
    on, dom, domConstruct, domClass, domStyle, ready, 
    iframe, xhr, 
	FeatureLayer, PopupTemplate, Point, Polyline, Polygon, Extent, Graphic, SpatialReference,
	SimpleRenderer, Color, SimpleMarkerSymbol, SimpleFillSymbol, SimpleLineSymbol, 
    dijitTemplate, SvgSymbol
) {

    var fileUploader = declare("FileUploader", [_WidgetBase, _TemplatedMixin, Evented], {

        templateString: dijitTemplate,

        options: {
            map: null, // required
            title: "File Upload",
			disclaimerText: "*csv, zip, gpx and kml/kmz files", 
            acceptedFileTypes: ["csv", "gpx", "kml", "kmz", "zip"],
            username: null, // required
            uploadServiceUrl: null, 
			uploadTimeout: 60000 /* 1-min timeout */,
            dataServiceUrl: null, 
			dataTimeout: 180000 /* 3-min timeout */, 
			renderingStyles: {"point": null, "line": null, "polygon": null}, 
            visible: true
        }, 

        _css: {
            disclaimer: "uploader-disclaimer", 
            statusMessage: "uploader-status",
			fileList: "uploader-fileList",
			button: "uploader-button"
        }, 

        /* ------------------ */
        /* Private Variables  */
        /* ------------------ */
		_layerIdPrefix: "uploadedLayer_", 
		_fileAccept: null, 
        _fileToUpload: null, 
		_addToMapHandler: null, 
		
		_activeUpload: null, 
		_uploadRegistry: {}, 

        constructor: function(options, srcRefNode) {
            // mix in settings and defaults
            declare.safeMixin(this.options, options);
            // properties
            this.set("map", this.options.map);
            this.set("title", this.options.title);
			this.set("disclaimerText", this.options.disclaimerText); 
            this.set("username", this.options.username); 
            this.set("acceptedFileTypes", this.options.acceptedFileTypes);
            this.set("uploadServiceUrl", this.options.uploadServiceUrl);
            this.set("uploadTimeout", this.options.uploadTimeout);
            this.set("dataServiceUrl", this.options.dataServiceUrl);
            this.set("dataTimeout", this.options.dataTimeout);
			this.set("renderingStyles", this.options.renderingStyles); 
            this.set("visible", this.options.visible);
			// derived properties
			this.set("_fileAccept", "." + this.options.acceptedFileTypes.join(",.")); 
            // listeners
            this.watch("visible", this._visible);
        },

        startup: function () {
			// username not defined
			if (!this.username) {
              this.destroy();
              console.log('FileUploader::username required');
            }
            // map not defined
            if (!this.map) {
              this.destroy();
              console.log('FileUploader::map required');
            }
            // when map is loaded
            if (this.map.loaded) {
              this._init();
            } else {
              on(this.map, "load", lang.hitch(this, function () {
                this._init();
              }));
            }
        },

        // connections/subscriptions will be cleaned up during the destroy() lifecycle phase
        destroy: function () {
            this.inherited(arguments);
        },

        /* ---------------------- */
        /* Private Event Handlers */
        /* ---------------------- */
		
		_fileReset: function(evt) {
			//evt.target.value = null; 
			this._fileSelector.value = null;
			this._fileToUpload = null;
			this._pendingList.innerHTML = "";
			this._status.innerHTML = ""; 
		},
		
        _fileSelected: function(evt) {
            console.log("file selected"); 

            // IE9 returns the local path. Chrome return a fake path.
            var files = evt.target.files; // FileList object
            //this._fileToUpload = null;

            this.showMessage("");

            var output = [];
            if (files) {
                // files is a FileList of File objects. List some properties.
                for (var i = 0, f; f = files[i]; i++) {
                    var nameParts = f.name.split(".");
                    var fext = nameParts[nameParts.length - 1];
                    if (array.indexOf(this.acceptedFileTypes, fext) == -1) {
                        this.showMessage(fext + " not supported");
                    } else {
                        output.push('<li>',
                                //'<strong>', escape(f.name), '</strong> ',
                                //'(', f.type || 'n/a', ') ',
                                //'<br/>- ',
                                //'Size: ',
								this._formatFileSize(f.size), ', ', 
                                //Math.round(f.size/100)/10, ' KB, ',
                                'Modified: ',
                                f.lastModifiedDate ? f.lastModifiedDate.toLocaleDateString() : 'n/a',
                                '</li>');
                        this._fileToUpload = f;
                    }
                }
            } 
            this._pendingList.innerHTML = '<ul>' + output.join('') + '</ul>';
        }, 

        _uploadFile: function(evt){
			if (this._pendingList.innerHTML.length == 0) {
				this.showMessage("No file selected"); 
			} else if (! this.uploadServiceUrl) {
				this.showMessage("No upload server url provided"); 
			} else if (! this.username) {
				this.showMessage("No username provided"); 
			} else {
                var queryString = "username="+ this.username;
                if (this._fileToUpload) {
                    queryString += ("&mtime="  + Math.round(this._fileToUpload.lastModifiedDate.getTime() / 1000));
                }

                console.log("Uploading file...");
                this.showMessage("Uploading file...");

                iframe.post(this.uploadServiceUrl, {
                    query: queryString,
                    form: "_uploaderForm",
                    handleAs: "json",
                    timeout: this.uploadTimeout
                }).then(lang.hitch(this, function(data) {
                    this._uploadComplete(data); 
                }), lang.hitch(this, function(err) {
                    this._uploadError(err)
                }));
            }
        }, 
		
		_clearAll: function() {
			console.log("clear all data");
			// remove the UI elements
			this._fileReset(); 
			// remove the existing layer if any
			for (var fname in this._uploadRegistry) {
				var dict = this._getRegistry(filename); 
				//var dict = this._uploadRegistry[fname]; 
				array.forEach(dict["layerIds"], lang.hitch(this, function(layerId) {
					this.map.removeLayer(this.map.getLayer(layerId));
				}));
				dict["layerIds"] = null; 
				dict["data"] = null; 
			}
			this._uploadRegistry = {}; 

			this.emit("clear"); 
		},		

        /* ----------------- */
        /* Private Functions */
        /* ----------------- */
		
		_removeAsLayer: function(filename) {
			var dict = this._getRegistry(filename); 
			//var dict = this._uploadRegistry[filename];
			if (dict) {
				if (dict["layerIds"]) {
					array.forEach(dict["layerIds"], lang.hitch(this, function(layerId) {
						this.map.removeLayer(this.map.getLayer(layerId)); 
					}));
				}
				dict["visible"] = false; 
				dict["layerIds"] = null; 
				dict["data"] = null;
				dict["extent"] = null; 
				// should reuse the drawing info
				//dict["drawing_info"] = null; 
			}			
			// Leave other attributes intact
			//this._uploadRegistry[filename] = null; 
		}, 
		
		_displayAsLayer: function(response) {
			this._displayDataOnMap(this._activeUpload); 
			
			this._activeUpload = null; 
		}, 
		
		_displayDataOnMap: function(filename) {			
			console.log("_displayDataOnMap: " + filename);
			this.showMessage("Displaying data...");
			
			var dict = this._uploadRegistry[filename];
			var featureJsonArray = dict["data"]; 
			var symbolArray = dict["drawing_info"]; 
			
			//loop through the items and add to the feature layer
			var layerIndex = 0;
			var layerExtent = null;

			array.forEach(featureJsonArray, lang.hitch(this, function(featureJson) {
				var featureArray = [];

				var spatialRefWkid = featureJson["spatialReference"] ? featureJson["spatialReference"].wkid : 4326;
				var spatialRef = new SpatialReference({wkid: spatialRefWkid});

				array.forEach(featureJson["features"], function (item) {

					var geometry = null;
					var geometryExtent = null;

					if (featureJson["geometryType"] == "esriGeometryPoint") {
						geometry = new Point(item.geometry);
						geometryExtent = geometry.getExtent();
					} else if (featureJson["geometryType"] == "esriGeometryPolyline") {
						geometry = new Polyline(item.geometry);
						geometryExtent = geometry.getExtent();
					} else if (featureJson["geometryType"] == "esriGeometryPolygon") {
						geometry = new Polygon(item.geometry);
						geometryExtent = geometry.getExtent();
					} else {
						console.log("bad geometry type");
						return
					}
					geometry.spatialReference = spatialRef;
					
					var graphic = new Graphic();
					graphic.setGeometry(geometry);
					graphic.setAttributes(item.attributes);
					featureArray.push(graphic);

					if (geometryExtent) {
						if (!layerExtent) {
							layerExtent = new Extent(geometryExtent.toJson());
						} else {
							layerExtent = layerExtent.union(geometryExtent);
						}
					} else {
						if (!layerExtent) {
							layerExtent = new Extent(geometry.x, geometry.y, geometry.x, geometry.y, spatialRef)
						} else if (!layerExtent.contains(geometry)) {
							if (layerExtent.xmax < geometry.x)
								layerExtent.xmax = geometry.x;
							if (layerExtent.ymax < geometry.y)
								layerExtent.ymax = geometry.y;
							if (layerExtent.xmin > geometry.x)
								layerExtent.xmin = geometry.x;
							if (layerExtent.ymin > geometry.y)
								layerExtent.ymin = geometry.y;
						}
					}
				});

				var featureLayer = this.map.getLayer(dict["layerIds"][layerIndex]); 
				// TODO - apply style
				var renderer = null, symbolInfo = null; 
				if (symbolArray && symbolArray[layerIndex]) {
					// stored style
					symbolInfo = symbolArray[layerIndex]["symbol"]; 
					if (symbolInfo["style"] === "appDefault") {
						// default style 
						symbolInfo = this._getDefaultSymbolStyle(featureJson["geometryType"]);
					}
				} else {
					// default style 
					symbolInfo = this._getDefaultSymbolStyle(featureJson["geometryType"]); 
				}

				switch(symbolInfo["type"]) {
					case "esriSMS":
						renderer = new SimpleRenderer(
							new SimpleMarkerSymbol(symbolInfo)
						);
						break;
					case "esriSLS": 
						renderer = new SimpleRenderer(
							new SimpleLineSymbol(symbolInfo)
						);
						break; 
					case "esriSFS":
						renderer = new SimpleRenderer(
							new SimpleFillSymbol(symbolInfo)
						);
						break; 
					default: 
						console.log("unknown symbol style")
				}				

				if (renderer) {
					featureLayer.setRenderer(renderer);
				}
				// apply data
				featureLayer.applyEdits(featureArray, null, null);

				layerIndex ++;
			}));

			// cache the layer extent 
			dict["extent"] = layerExtent; 
			
			this.map.setExtent(layerExtent, true);
			
			// remove the old handler to hide the internal logic
			if (this._addToMapHandler) {
				this._addToMapHandler.remove(); 
				this._addToMapHandler = null; 
			}
			
			dict["visible"] = true; 
			this.showMessage(""); 
			
			this.emit("dataOnMap", filename); 	
		}, 
		
		_addAsLayer: function (filename, metadata) {
			console.log("Loading data to map...");
			this.showMessage("Loading data to map...");
			
			var dict = this._uploadRegistry[filename];
			var featureMetadata = dict["data"];
			
			// remove the old handler
			if (this._addToMapHandler) {
				this._addToMapHandler.remove(); 
				this._addToMapHandler = null; 
			}
			// add a new one
			this._addToMapHandler = 
				this.map.on("layers-add-result", lang.hitch(this, function (result) {
					//map.on("layer-add-result", function (result) {
					this._displayAsLayer(result);
				}));

			// find the next layer index 
			var layerIdx = -1;
			array.forEach(this.map.graphicsLayerIds, lang.hitch(this, function(layerId) {
				var idxString = layerId.replace(this._layerIdPrefix, "");
				if (idxString !== layerId) {					
					layerIdx = Number(idxString); 
				}
			}));
			layerIdx ++; 			
			
			dict["layerIds"] = []; 
			var featureLayerSet = [];
			
			array.forEach(featureMetadata, lang.hitch(this, function(featureJson) {
				// construct feature collection
				var featureCollection = {
					"layerDefinition": {
						"displayFieldName": featureJson["displayFieldName"],
						"geometryType": featureJson["geometryType"],
						"fields": featureJson["fields"],
						"fieldAliases": featureJson["fieldAliases"]
					},
					"featureSet": {
						"features": [],
						"geometryType": featureJson["geometryType"]
					}
				};

				var popupTemplate = null;
				if (featureJson["displayFieldName"] && featureJson["displayFieldName"].length > 0) {
					popupTemplate = new PopupTemplate({
						title: "{" + featureJson["displayFieldName"] + "}",
						description: "{" + featureJson["displayFieldName"] + "}"
					});
				}

				//create a feature layer based on the feature collection
				var layerId = this._layerIdPrefix + layerIdx; 
				var featureLayer = new FeatureLayer(featureCollection, {
					id: layerId,
					mode: FeatureLayer.MODE_SNAPSHOT,
					infoTemplate: popupTemplate
				});

				//associate the features with the popup on click
				featureLayer.on("click", lang.hitch(this, function (evt) {
					map.infoWindow.setFeatures([evt.graphic]);
				}));

				featureLayerSet.push(featureLayer);
				dict["layerIds"].push(layerId);
				
				layerIdx ++;
			}));

			if (featureLayerSet && featureLayerSet.length > 0) {
				this.map.addLayers(featureLayerSet);
			}
			
			featureLayerSet = []; 
			
			return dict["layerIds"]; 
		},
		
        /* ---------------- */
        /* Public Functions */
        /* ---------------- */
		
		addToMap: function(filename) {
			var fileData = this._getRegistry(filename, "data"); 
			if (fileData) {
				this._addAsLayer(filename, fileData); 
			} else {
				console.log("data not ready: " + filename); 
			}
			/*
			var dict = this._uploadRegistry[filename]; 
			if (dict && dict["data"]) {
				this._addAsLayer(filename, dict["data"]); 
			} else {
				console.log("data not ready: " + filename); 
			}
			 */			 
		},
		
        listData: function() {
            console.log("Refresh data list");
            this.showMessage("Refreshing data list...");

            var requestUrl = this._composeRequestUrl("list");
            var requestHandle = xhr(requestUrl, {
                method: "POST", 
                handleAs: "json",
                timeout: this.dataTimeout
            }).then(lang.hitch(this, function(data) {
                this._dataListLoaded(data); 
            }), lang.hitch(this, function(err) {
                this._dataLoadFailed(err)
            }));
        }, 
		
		requestData: function(filename) {
			console.log("RequestData " + filename);
			this.showMessage("Loading data...");
			
			// remove the existing layer if any
			this._removeAsLayer(filename); 
			
			// request new data 
			this._activeUpload = filename; 
			var requestUrl = this._composeRequestUrl("data", {
				"filename": filename});
			var requestHandle = xhr(requestUrl, {
				method: "POST", 
				handleAs: "json",
				timeout: this.dataTimeout
			}).then(lang.hitch(this, function(data) {
                this._dataLoaded(data); 
            }), lang.hitch(this, function(err) {
                this._dataLoadFailed(err)
            }));
		}, 
		
		archiveData: function(filename) {
			console.log("Archive data");
			this.showMessage("Archive data...");

			var requestUrl = this._composeRequestUrl("archive", {
				"filename": filename});
			var requestHandle = xhr(requestUrl, {
				method: "POST",
				handleAs: "json",
				timeout: this.dataTimeout
			}).then(lang.hitch(this, function(data) {
				this._dataArchived(data); 
			}), lang.hitch(this, function(err) {
				this._dataLoadFailed(err)
			}));
		},	

		renameData: function(filename, newName) {
			console.log("Rename data");
			this.showMessage("Rename data...");

			var requestUrl = this._composeRequestUrl("rename", {
				"filename": filename, 
				"data_name": newName});
			var requestHandle = xhr(requestUrl, {
				method: "POST",
				handleAs: "json",
				timeout: this.dataTimeout
			}).then(lang.hitch(this, function(data) {
				this._dataRenamed(data); 
			}), lang.hitch(this, function(err) {
				this._dataLoadFailed(err)
			}));
		},
	
		styleData: function(filename, drawingInfo) {
			console.log("Style data");
			this.showMessage("Style data...");
			
			// update the upload registry
			this._setRegistry(filename, "drawing_info", JSON.parse(drawingInfo, true)); 
			/*
			if (this._uploadRegistry[filename]) {
				this._uploadRegistry[filename]["drawing_info"] 
					= JSON.parse(drawingInfo, true); 
			}
			 */

			// update the server
			var requestUrl = this._composeRequestUrl("style", {
				"filename": filename, 
				"drawing_info": drawingInfo});
			var requestHandle = xhr(requestUrl, {
				method: "POST",
				handleAs: "json",
				timeout: this.dataTimeout
			}).then(lang.hitch(this, function(data) {
				this._dataStyled(data); 
			}), lang.hitch(this, function(err) {
				this._dataLoadFailed(err)
			}));
		}, 

        /* ------------------ */
        /* Callback Functions */
        /* ------------------ */
		
        _uploadComplete: function(result) {
            if (result) {
                if (result.error) {
                    console.log("Upload Error: " + result.error);
                    this.showMessage("Upload Error: " + result.error);
                } else {
                    console.log("uploadComplete: " + result);
                    this.showMessage("upload completed");
					
					this.requestData(result.filename); 

                    this.emit("upload", result);
                }
            } else {
                console.log("Upload Server internal error");
                this.showMessage("Upload Server internal error");
            }
        }, 

        _uploadError: function (err) {
            console.log("Upload Error: " + err.message);
            this.showMessage("Error:" + err.message);
        }, 
		
        _dataListLoaded: function(data) {
            console.log("_dataListLoaded");
			
			this._fileList.innerHTML = "";

			for(var i=0, l=data.length; i<l; i++) {
				var item = data[i];
				var item_value = item["src_file_path"];
				if (! this._getRegistry(item_value)) {
					this._setRegistry(item_value, "visible", false); 
				}
				this._setRegistry(item_value, "data_name", item["data_name"]); 
				this._setRegistry(item_value, "drawing_info", item["drawing_info"]); 
				
				var dict = this._getRegistry(item_value); 
				/*
				if (!this._uploadRegistry[item_value]) {
					this._uploadRegistry[item_value] = {
						"visible": false
					}; 
				}
				// cache into the registry
				this._uploadRegistry[item_value]["data_name"] = item["data_name"]; 
				this._uploadRegistry[item_value]["drawing_info"] = item["drawing_info"]; 
				//
				
				var dict = this._uploadRegistry[item_value];
				 */
				var item_visible = dict["visible"];

				var itemHtml = "<div id='file-item-" + i + "' class='"+ (i%2==0?"file-item-even":"file-item-odd") + "'>";
				itemHtml += ("<table cellpadding='0' cellspacing='0' width='95%'>");
				itemHtml += ("<tbody>");
				itemHtml += ("<tr>");

				itemHtml += ("<td width='25' align='center'>");
				itemHtml += ("<input id='file-chkbox-" + i + "' type='checkbox' name='filelist' value='" + item_value + "' userData='" + item_value + "' " + (item_visible===true?"checked":"") + ">");
				itemHtml += ("</td>");
				/*
				itemHtml += ("<td width='35'>");
				itemHtml += ("<span id='file-style-" + i + "' class='file-style-icon' userData='" + item_value + "'>" + SvgSymbol.parseSymbolInfo(item["drawing_info"]) + "</span>"); 
				itemHtml += ("</td>");
				 */
				itemHtml += ("<td>");
				itemHtml += ("<span id='file-name-" + i + "' class='file-title-name' userData='" + item_value + "'>" + item["data_name"] + "</span>");
				itemHtml += ("</td>");

				itemHtml += ("<td align='right'>");
				itemHtml += ("<img id='file-del-" + i + "' src='images/trash_file.png' class='file-del-icon' userData='" + item_value + "'>");
				itemHtml += ("</td>");

				itemHtml += ("</tr>");
				itemHtml += ("</tbody>");
				itemHtml += ("</table>");

				itemHtml += ("<ul class='file-item-detail'>");
				//itemHtml += ("<li>" + Math.round(Number(item["size"])/100)/10 + " KB,  ");
				itemHtml += ("<li>" + this._formatFileSize(item["size"]) + ",  ");
				itemHtml += ("Modified: " + item["last_modified"].slice(0, item["last_modified"].indexOf(" ")) + "</li>");
				itemHtml += ("</ul>");

				itemHtml += ("<table cellpadding='0' cellspacing='0' width='95%'>");
				itemHtml += ("<tbody>");

				// transform into svg
				var symbolArray = item["drawing_info"]; 
				if (! symbolArray) {
					// set a dummmy item into an array for refactoring
					symbolArray = ["0"]; 
				}
				for(var s=0; s<symbolArray.length; s++) {
					var symbolInfo = symbolArray[s];
					var symbolStyle = symbolInfo["symbol"]; 
					if (symbolStyle && symbolStyle["style"] == "appDefault") {
						symbolInfo["symbol"] = this._getDefaultSymbolStyle(symbolStyle["type"]); 
					}
					
					itemHtml += ("<tr>");

					itemHtml += ("<td width='35px'>");
					itemHtml += ("<span id='file-style-icon-" + (i + "-" + s) + "' class='file-style-icon' userData='" + item_value + "'>" 
									+ SvgSymbol.parseSymbolInfo(symbolInfo["symbol"]) + "</span>"); 
					itemHtml += ("</td>");

					itemHtml += ("<td width='150px'>");
					itemHtml += ("<span id='file-style-label-" + (i + "-" + s) + "' class='file-style-label' userData='" + item_value + "'>" 
									//+ ((symbolInfo["label"] && symbolInfo["label"].length>0)?symbolInfo["label"]:"default") + "</span>"); 
									+ ((symbolInfo["label"])?symbolInfo["label"]:"") + "</span>"); 
					itemHtml += ("</td>");

					itemHtml += ("</tr>");
				};

				 
				itemHtml += ("</tbody>");
				itemHtml += ("</table>");
				itemHtml += ("</div>");

				domConstruct.place(itemHtml, this._fileList);
				
				// add event handlers
				//
				var fileChkboxNode = dom.byId("file-chkbox-" + i);
				on(fileChkboxNode, "click", lang.hitch(this, function(evt){
					if (evt.target.checked === true) {
						console.log("display data: " + evt.target.value);
						this.requestData(evt.target.value);
					} else {
						console.log("hide data: " + evt.target.value);
						this._removeAsLayer(evt.target.value);
					}
				}));
				
				for(var s=0; s<symbolArray.length; s++) {
					var fileImgNode = dom.byId("file-style-icon-" + (i + "-" + s));
					on(fileImgNode, "dblclick", lang.hitch(this, function(evt){
						var svgShp = evt.target; 
						while(svgShp.nodeName != "svg") {
							svgShp = svgShp.parentNode; 
						}
						var filename = dojo.attr(svgShp.parentNode, "userData");
						console.log("request style for: " + filename);
						
						this.emit("style-start", 
							{"name": filename, "drawing_info": this._getRegistry(filename, "drawing_info")});
						/*
						var dict = this._uploadRegistry[filename]; 
						this.emit("style-start", {"name": filename, "drawing_info": (!dict)?null:dict["drawing_info"]});
						 */
						 
						//event.preventDefault(); 
					}));
				}

				var fileNameNode = dom.byId("file-name-" + i);
				on(fileNameNode, "click", lang.hitch(this, function(evt) {
					var filename = dojo.attr(evt.target, "userData"); 
					console.log("zoom to data: " + dojo.attr(evt.target, "userData"));
					var layerExtent = this._getRegistry(filename, "extent")
					if (layerExtent) {
						this.map.setExtent(layerExtent); 
					} else {
						console.log("data is not loaded to map"); 
					}
					/*
					if (this._uploadRegistry[filename]) {
						var layerExtent = this._uploadRegistry[filename]["extent"]; 
						if (layerExtent) {
							this.map.setExtent(layerExtent); 
						} else {
							console.log("data is not loaded to map"); 
						}
					}
					 */
				})); 
				on(fileNameNode, "dblclick", lang.hitch(this, function(evt){
					console.log("change the file name: " + dojo.attr(evt.target, "userData"));
					//event.preventDefault(); 

					var nodeIndex = this._parseIndexFromId(evt.target.id);
					var oldName = evt.target.innerHTML; 

					domStyle.set(evt.target, "display", "none"); 

					var editorHtml = '<span id="file-name-editor-' + nodeIndex + '">'; 
					editorHtml += '<input id="file-name-input-' + nodeIndex + '" type="text" class="file-name-input" value="' + oldName + '"/>';
					editorHtml += '<img id="file-name-save-' + nodeIndex + '" src="images/change_accept.png" class="file-action-icon"/>';
					editorHtml += '<img id="file-name-undo-' + nodeIndex + '" src="images/change_undo.png" class="file-action-icon"/>'
					editorHtml += '</span>'; 

					var editorNode = domConstruct.toDom(editorHtml); 
					domConstruct.place(editorNode, evt.target, "after"); 

					var nameEditSaveNode = dom.byId("file-name-save-" + nodeIndex);
					on(nameEditSaveNode, "click", lang.hitch(this, function(evt) {
						var nodeIndex = this._parseIndexFromId(evt.target.id);
						
						var nameTextNode = dom.byId("file-name-" + nodeIndex);
						var nameEditorNode = dom.byId("file-name-editor-" + nodeIndex);
						var nameInputNode = dom.byId("file-name-input-" + nodeIndex);

						this.renameData(dojo.attr(nameTextNode, "userData"), nameInputNode.value);

						domStyle.set(nameTextNode, "display", "inline"); 
						domConstruct.destroy(nameEditorNode);
					}));

					var nameEditUndoNode = dom.byId("file-name-undo-" + nodeIndex);
					on(nameEditUndoNode, "click", lang.hitch(this, function(evt){
						var nodeIndex = this._parseIndexFromId(evt.target.id);

						var nameTextNode = dom.byId("file-name-" + nodeIndex);
						var nameEditorNode = dom.byId("file-name-editor-" + nodeIndex);

						domStyle.set(nameTextNode, "display", "inline"); 
						domConstruct.destroy(nameEditorNode);
					})); 

				}));

				var fileDelNode = dom.byId("file-del-" + i);
				on(fileDelNode, "click", lang.hitch(this, function(evt){
					console.log("delete the file: " + dojo.attr(evt.target, "userData"));
					this.archiveData(dojo.attr(evt.target, "userData"));
				}));
				
			}

			this.showMessage("");
			
            this.emit("listLoaded"); 
        }, 

        _dataLoadFailed: function(err) {
            console.log("Error: " + err.message);
			if (err.message.search(/timeout/i) > -1) {
				this.showMessage("still processing"); 
				this._setRegistry(this._activeUpload, "status", "processing");
				/*
				if (!this._uploadRegistry) {
					this._uploadRegistry = {}; 
				}
				if (!this._uploadRegistry[this._activeUpload]) {
					this._uploadRegistry[this._activeUpload] = {}; 
				}
				this._uploadRegistry[this._activeUpload]["status"] = "processing"; 
				 */
			} else {
				this.showMessage("Error:" + err.message);
			}
        }, 

		_dataLoaded: function (response) {
			console.log("dataReady");
			//this.showMessage("data ready");
			
			if (! this._getRegistry(this._activeUpload, "data")) {
				this._setRegistry(this._activeUpload, "data", response); 
				this._setRegistry(this._activeUpload, "layerIds", []); 
				
				this.addToMap(this._activeUpload);
			} else {
				this._displayDataOnMap(this._activeUpload); 
			}
			/*
			if (! this._uploadRegistry[this._activeUpload]) {
				this._uploadRegistry[this._activeUpload] = {}; 
			}
			if (! this._uploadRegistry[this._activeUpload]["data"]) {
				this._uploadRegistry[this._activeUpload]["data"] = response; 
				this._uploadRegistry[this._activeUpload]["layerIds"] = []; 
				
				this.addToMap(this._activeUpload);
			} else {
				this._displayDataOnMap(this._activeUpload); 
			}
			 */
			 
			this.emit("dataReady", this._activeUpload); 
		},
		
		_dataArchived: function (response) {
			console.log("archive response: " + response);
			this.showMessage("data archived");
			
			this._removeAsLayer(response.filename);

			// remove the cached style as well
			this._setRegistry(response.filename, "drawing_info", null); 
			/*
			var dict = this._uploadRegistry[response.filename];
			if (dict) {
				dict["drawing_info"] = null;
			}
			 */			 
			
			this.emit("dataArchive", response.filename); 
		}, 
		
		_dataRenamed: function(response) {
			console.log("Rename response: " + response);
			this.showMessage("data renamed");
			
			this.emit("dataRename", response.filename); 
		}, 
		
		_dataStyled: function(response) {
			console.log("Style response: " + response);
			this.showMessage("data styled");
			
			// refresh the data
			if (this._getRegistry(response.filename, "data")) {
				this.requestData(response.filename);
			}			
			/*
			if (this._uploadRegistry[response.filename] 
				&& this._uploadRegistry[response.filename]["data"]) {
				this.requestData(response.filename);
			}
			 */
			
			this.emit("dataStyle", response.filename);
		}, 
		
        /* ------------------------- */
        /* Private Utility Functions */
        /* ------------------------- */
        
        _init: function () {
            this._visible();
            this.set("loaded", true);
            this.emit("load", {});
        },

        _visible: function () {
            if (this.get("visible")) {
                domStyle.set(this.domNode, 'display', 'block');
            } else {
                domStyle.set(this.domNode, 'display', 'none');
            }
        }, 

		/* not used */
        _isFileApiSupported: function() {
            if (window.File && window.FileReader && window.FileList && window.Blob) {
                // Great success! All the File APIs are supported.
                return true;
            } else {
                console.log('FileUploader: The required File APIs are not supported in this browser.');
                return false; 
            }
        }, 

        _composeRequestUrl: function (action, queryParams) {
            var requestUrl = this.dataServiceUrl; 
            requestUrl += "?action=" + action + "&username=" + this.username;
			for(var qp in queryParams) {
				requestUrl += (queryParams[qp]?("&"+qp+"="+queryParams[qp]):"");
			}            
            console.log("requestUrl  " + requestUrl);

            return requestUrl;
        }, 
		
		_parseIndexFromId: function (nodeId) {
			//TODO: get the index from the ID
			var nodeIdParts = nodeId.split("-"); 
			var nodeIndex = nodeIdParts[nodeIdParts.length-1]; 
			////
			return nodeIndex; 
		}, 
		
		_formatFileSize: function(file_size) {
			if (isNaN(file_size)) {
				return "N/A"; 
			} else {
				var unit_array = ["B", "KB", "MB", "GB"]; 
				var file_size_string = file_size.toString();				 
				var u = 0; 
				while(file_size_string.length > 3 && u < unit_array.length) {
					file_size = Math.round(file_size*10/1024)/10; 
					file_size_string = file_size.toString().split(".")[0];
					u++; 
				}
				return file_size.toString() + " " + unit_array[u]; 
			}
		}, 
		
		_getDefaultSymbolStyle: function(symbolType) {
			switch(symbolType) {
				case "esriGeometryPoint":
				case "esriSMS":
					return this.renderingStyles["point"];
				case "esriGeometryPolyline":
				case "esriSLS": 
					return this.renderingStyles["line"];
				case "esriGeometryPolygon":
				case "esriSFS":
					return this.renderingStyles["polygon"]; 
				default: 
					console.log("error: unknown geometry type"); 
					return null; 
			}
		},

		_getRegistry: function(key, attr) {
			if (this._uploadRegistry && this._uploadRegistry[key]) {
				if (attr) {
					return this._uploadRegistry[key][attr]; 
				} else {
					return this._uploadRegistry[key]; 
				}
			} else {
				return null; 
			}
		}, 
		
		_setRegistry: function(key, attr, val) {
			if (! this._uploadRegistry) {
				this._uploadRegistry = {};
			}
			if (! this._uploadRegistry[key]) {
				this._uploadRegistry[key] = {};
			}
			this._uploadRegistry[key][attr] = val; 
		},		
		
        showMessage: function (message) {
            if (message) {
                /* limit the message size */
                message = message.substr(0, 100); 
            }
            this._status.innerHTML = message;
        }
		
    });

    ready(function(){
        console.log("Widget FileUploader is ready!");
    });	

    return fileUploader; 

}); 