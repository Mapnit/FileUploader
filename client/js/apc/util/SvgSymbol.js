/**
 * Created by kdb086 on 7/17/2015.
 */
define(["dojo/_base/declare"], function(declare) {

    var symCreator = declare("SvgSymbol", null, {
    });

    // static tags
    symCreator._svgStart = '<svg overflow="hidden" width="30" height="30">'; 
    symCreator._svgEnd = '</svg>'; 
    symCreator._svgDef = '<defs></defs>'; 
    // static templates
	symCreator._CircleTemplate = '<circle fill="${fillColor}" fill-opacity="${fillAlpha}" stroke="${strokeColor}" stroke-opacity="${strokeAlpha}" stroke-width="${strokeWidth}" stroke-linecap="butt" stroke-linejoin="miter" stroke-miterlimit="4" cx="0" cy="0" r="${size}" fill-rule="evenodd" stroke-dasharray="none" dojoGfxStrokeStyle="solid" transform="matrix(1.00000000,0.00000000,0.00000000,1.00000000,15.00000000,15.00000000)"/>';
	symCreator._SquareTemplate = '<path fill="${fillColor}" fill-opacity="${fillAlpha}" stroke="${strokeColor}" stroke-opacity="${strokeAlpha}" stroke-width="${strokeWidth}" stroke-linecap="butt" stroke-linejoin="miter" stroke-miterlimit="4" d="M-${size} -${size} L${size} -${size} L${size} ${size} L-${size} ${size} Z" stroke-dasharray="none" transform="matrix(1.00000000,0.00000000,0.00000000,1.00000000,15.00000000,15.00000000)"></path>';
    symCreator._DiamondTemplate = '<path fill="${fillColor}" fill-opacity="${fillAlpha}" stroke="${strokeColor}" stroke-opacity="${strokeAlpha}" stroke-width="${strokeWidth}" stroke-linecap="butt" stroke-linejoin="miter" stroke-miterlimit="4" d="M-${width} 0 L0 ${height} L${width} 0 L0 -${height} Z" stroke-dasharray="none" transform="matrix(1.00000000,0.00000000,0.00000000,1.00000000,15.00000000,15.00000000)"></path>';
    symCreator._CrossTemplate = '<path fill="${fillColor}" fill-opacity="${fillAlpha}" stroke="${strokeColor}" stroke-opacity="${strokeAlpha}" stroke-width="${strokeWidth}" stroke-linecap="butt" stroke-linejoin="miter" stroke-miterlimit="4" d="M-${size} 0 L${size} 0 M0 -${size} L0 ${size}" stroke-dasharray="none" transform="matrix(1.00000000,0.00000000,0.00000000,1.00000000,15.00000000,15.00000000)"></path>';
    symCreator._XxxTemplate = '<path fill="${fillColor}" fill-opacity="${fillAlpha}" stroke="${strokeColor}" stroke-opacity="${strokeAlpha}" stroke-width="${strokeWidth}" stroke-linecap="butt" stroke-linejoin="miter" stroke-miterlimit="4" d="M-${size} -${size} L${size} ${size} M${size} -${size} L-${size} ${size}" stroke-dasharray="none" transform="matrix(1.00000000,0.00000000,0.00000000,1.00000000,15.00000000,15.00000000)"></path>';	
	symCreator._LineTemplate = '<path fill="none" fill-opacity="0" stroke="${strokeColor}" stroke-opacity="${strokeAlpha}" stroke-width="${strokeWidth}" stroke-linecap="butt" stroke-linejoin="miter" stroke-miterlimit="4" path="M -10,5 L 10,-5 E" d="M-10 5L 10-5" stroke-dasharray="${dashPattern}" dojoGfxStrokeStyle="${dashGfxValue}" transform="matrix(1.00000000,0.00000000,0.00000000,1.00000000,15.00000000,15.00000000)"></path>';
    symCreator._PolygonTemplate = '<path fill="${fillColor}" fill-opacity="${fillAlpha}" stroke="${strokeColor}" stroke-opacity="${strokeAlpha}" stroke-width="${strokeWidth}" stroke-linecap="butt" stroke-linejoin="miter" stroke-miterlimit="4" path="M -10,-10 L 10,0 L 10,10 L -10,10 L -10,-10 E" d="M-10-10L 10 0L 10 10L-10 10L-10-10" fill-rule="evenodd" stroke-dasharray="${dashPattern}" dojoGfxStrokeStyle="${dashGfxValue}" transform="matrix(1.00000000,0.00000000,0.00000000,1.00000000,15.00000000,15.00000000)"/>';
	// static patterns
	symCreator._LineDashPattern = "5,5"; 
	symCreator._LineDashGfxValue = "dash"; 
	symCreator._LineSolidPattern = "none"; 
	symCreator._LineSolidGfxValue = "solid"; 

    // static functions
    symCreator.formatRGB = function (rgb) {
        return "rgb(" + (isNaN(rgb[0])?0:rgb[0]) 
				+ ", " + (isNaN(rgb[1])?0:rgb[1]) 
				+ ", " + (isNaN(rgb[2])?0:rgb[2]) + ")";
    };

    symCreator.formatAlpha = function(alpha) {
        alpha = isNaN(alpha)?255:alpha; 
        return alpha / 255;
    };

    symCreator.calculateStrokeWidth = function(width) {
        width = isNaN(width)?1:width; 
        //return Math.max(width / 3, 1);
		return Math.max(width, 1);
    };

    symCreator.calculatePointSize = function(size) {
        size = isNaN(size)?1:size;
        return Math.max(size / 1.5, 1);
    }

    symCreator.toPointIcon = function(size, fillRGB, fillAlpha, strokeRGB, strokeAlpha, strokeWidth, style) {
		var def, size = symCreator.calculatePointSize(size);
		switch(style.toLowerCase()) {
			case "circle":
				def = symCreator._CircleTemplate;				
				break;
			case "square":
				def = symCreator._SquareTemplate;
				break;
			case "diamond":
				def = symCreator._DiamondTemplate;
				break;
			case "cross":
				def = symCreator._CrossTemplate;
				break;
			case "x":
				def = symCreator._XxxTemplate;
				break;
			default:
				def = symCreator._CircleTemplate;
		}        

        def = def.replace("${fillColor}", symCreator.formatRGB(fillRGB?fillRGB:[0,0,0]));
        def = def.replace("${fillAlpha}", symCreator.formatAlpha(isNaN(fillAlpha)?255:fillAlpha));
        def = def.replace("${strokeColor}", symCreator.formatRGB(strokeRGB?strokeRGB:[0,0,0]));
        def = def.replace("${strokeAlpha}", symCreator.formatAlpha(isNaN(strokeAlpha)?255:strokeAlpha));
        def = def.replace("${strokeWidth}", symCreator.calculateStrokeWidth(strokeWidth));
        def = def.replace(/\$\{size\}/g, size);
		def = def.replace(/\$\{width\}/g, size);
		def = def.replace(/\$\{height\}/g, Number(size) * 1.2);

        return symCreator._svgStart + symCreator._svgDef + def + symCreator._svgEnd;
    }

    symCreator.toLineIcon = function(strokeRGB, strokeAlpha, strokeWidth, dashOrSolid) {
        var def = symCreator._LineTemplate;

        def = def.replace("${strokeColor}", symCreator.formatRGB(strokeRGB?strokeRGB:[0,0,0]));
        def = def.replace("${strokeAlpha}", symCreator.formatAlpha(isNaN(strokeAlpha)?255:strokeAlpha));
        def = def.replace("${strokeWidth}", symCreator.calculateStrokeWidth(strokeWidth));
		def = def.replace("${dashPattern}", dashOrSolid==="dash"?this._LineDashPattern:this._LineSolidPattern);
		def = def.replace("${dashGfxValue}", dashOrSolid==="dash"?this._LineSolidGfxValue:this._LineDashGfxValue);

        return symCreator._svgStart + symCreator._svgDef + def + symCreator._svgEnd;
    }

    symCreator.toPolygonIcon = function(fillRGB, fillAlpha, strokeRGB, strokeAlpha, strokeWidth, dashOrSolid) {
        var def = symCreator._PolygonTemplate;

        def = def.replace("${fillColor}", symCreator.formatRGB(fillRGB?fillRGB:[0,0,0]));
        def = def.replace("${fillAlpha}", symCreator.formatAlpha(isNaN(fillAlpha)?255:fillAlpha));
        def = def.replace("${strokeColor}", symCreator.formatRGB(strokeRGB?strokeRGB:[0,0,0]));
        def = def.replace("${strokeAlpha}", symCreator.formatAlpha(isNaN(strokeAlpha)?255:strokeAlpha));
        def = def.replace("${strokeWidth}", symCreator.calculateStrokeWidth(strokeWidth));
		def = def.replace("${dashPattern}", dashOrSolid==="dash"?this._LineDashPattern:this._LineSolidPattern);
		def = def.replace("${dashGfxValue}", dashOrSolid==="dash"?this._LineSolidGfxValue:this._LineDashGfxValue);

        return symCreator._svgStart + symCreator._svgDef + def + symCreator._svgEnd;
    }

    symCreator.parseSymbolInfo = function(esriSymbolJson) {

        if (esriSymbolJson && esriSymbolJson["type"]) {

            var symbolType = esriSymbolJson["type"]; 
            if (symbolType === "esriSMS") {
                 /* point */
				var pointStyle; 
				switch(esriSymbolJson["style"]) {
					case "esriSMSCircle":
						pointStyle = "circle";
						break; 
					case "esriSMSSquare":
						pointStyle = "square";
						break; 
					case "esriSMSDiamond":
						pointStyle = "diamond";
						break; 
					case "esriSMSCross":
						pointStyle = "cross"; 
						break; 
					case "esriSMSX":
						pointStyle = "x"; 
						break; 
				}
                return symCreator.toPointIcon(esriSymbolJson["size"], 
                    esriSymbolJson["color"], esriSymbolJson["color"][3],
                    esriSymbolJson["outline"]["color"], esriSymbolJson["outline"]["color"][3],
                    esriSymbolJson["outline"]["width"], pointStyle);

            } else if (symbolType === "esriSLS") {
                /* line */
				var lineStyle = esriSymbolJson["style"]==="esriSLSDash"?"dash":"solid"; 
                return symCreator.toLineIcon(esriSymbolJson["color"], esriSymbolJson["color"][3],
                    esriSymbolJson["width"], lineStyle);

            } else if (symbolType === "esriSFS") {
                /* polygon */
				var outlineStyle = esriSymbolJson["outline"]["style"]==="esriSLSDash"?"dash":"solid"; 
                return symCreator.toPolygonIcon(esriSymbolJson["color"], esriSymbolJson["color"][3],
                    esriSymbolJson["outline"]["color"], esriSymbolJson["outline"]["color"][3],
                    esriSymbolJson["outline"]["width"], outlineStyle);
            }
        }

        /* totally transparent */
        return symCreator.toLineIcon([255, 255, 255], 0, 0);

    }

    return symCreator;

});