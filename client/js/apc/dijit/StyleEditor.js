define([
	"dijit/_WidgetBase", 
	"dojo/_base/declare",
	"dojo/Evented",
	"dijit/_TemplatedMixin", 
	"dojo/parser",
	"dojo/ready",
	"dojo/dom-style", 
	
	"dojo/text!apc/dijit/templates/StyleEditor.html"
], function(
	_WidgetBase, declare, Evented, _TemplatedMixin, parser, ready, 
	domStyle, dijitTemplate
) {
	var editor = declare("StyleEditor", [_WidgetBase, _TemplatedMixin, Evented], {
		
		templateString: dijitTemplate, 
		
		options: {
			name: null, // required
			title: null, // required
			content: "", 
			visible: false
		},
		
		_css: {
			title: "styleEditor-title", 
			content: "styleEditor-content",
			button: "styleEditor-button"
		}, 
		
		constructor: function(options, srcRefNode) {
			declare.safeMixin(this.options, options); 
			
			this.set("name", this.options.name); 
			this._set("title", this.options.title); 
			this._set("content", this.options.content); 
			this.set("visible", this.options.visible);
			
			this.watch("visible", this._visible);
		}, 
		
		startup: function() {
			if (!this.name) {
              this.destroy();
              console.log('StyleEditor::name required');
            }
			
			this._init();
		}, 
		
		_init: function () {
            this._visible();
            this.set("loaded", true);
            this.emit("load", {});
        },
		
		_setTitleAttr: function(title) {
			this._set("title", title);	
			this._title.innerHTML = title;
		},
		//_setTitleAttr: {node: "_title", type: "innerHTML"}; 

		_setContentAttr: function(content) {
			this._set("content", content);	
			this._content.value = content;
			this._content.innerHTML = content;
		},
		
		save: function() {
			console.log("save the changes"); 
			
			this.set("content", this._content.value); 
					
			this.emit("save", {
				"name": this.name, 
				"title": this.title, 
				"content": this.content
			}); 
		}, 
		
		cancel: function() {
			console.log("discard any change"); 
			
			this.emit("cancel", {
				"name": this.name
			});	
		},
		
        _visible: function () {
            if (this.get("visible")) {
                domStyle.set(this.domNode, 'display', 'block');
            } else {
                domStyle.set(this.domNode, 'display', 'none');
            }
        }		
	}); 
	
	ready(function() {
		console.log("Widget StyleEditor is ready"); 
	}); 
	
	return editor; 
});