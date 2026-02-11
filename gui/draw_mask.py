"""
Filename: draw_mask.py
Author: Michele Lissoni
Date: 2026-02-11
"""

"""

The QClassiPyDrawMask class handles the "Draw mask" tab.

"""

from qgis.PyQt.QtCore import Qt, QMetaType, QVariant
from qgis.PyQt.QtWidgets import QWidget, QFileDialog, QColorDialog, QMessageBox, QInputDialog
from qgis.PyQt.QtGui import QColor, QFont

from qgis.core import *
import qgis.utils

import os
import time
import numpy as np
import pandas as pd

import shapely
from osgeo import gdal

from ..core.polyimage import PolyImage
from ..utils.buffer_selection import BufferSelectionTool
from ..core.gdal_tools import rasterizeLayer
from .table_dock import TableDockFrames
from ..ui.all_uis import Ui_QClassiPyDrawMask

from .constants import Directories, Priorities, Colors

COMPLETED_PRIORITY = Priorities.Completed

layer_dir = Directories.Layer

default_color = Colors.Default
null_color = QColor(default_color)
null_color.setAlpha(0)
frame_color = Colors.Frame
qcolorlist = Colors.Colorlist

# Function to support random loading of the tiles, currently disabled.
'''        
def priorityChoice(df, priority_col = 'priority', avoid = COMPLETED_PRIORITY, must=1):

    if not np.isin(priority_col, list(df.columns)) :
        raise ValueError("The dataframe should contain at least the priority_col column.")
        
    df_indices = np.arange(len(df), dtype=int)
    
    if avoid is not None and avoid!=must :
        df_indices = np.flatnonzero(df[priority_col]!=avoid)
        df = df.iloc[df_indices, :]
    elif avoid is not None and avoid==must :
        raise ValueError("'avoid' and 'must' must be different.")
        
    if must is not None and np.sum(df[priority_col] == must) > 0):
        df = df.loc[df[priority_col]==must, :]
        df_indices = df_indices[np.flatnonzero(df[priority_col]==must)]
        random_index = df_indices[np.argsort(np.random.rand(len(df)))[0]]
    else:

        unique_priorities = np.unique(df[priority_col])
        priority = np.sort(unique_priorities)[0]
        
        df = df.loc[df[priority_col]==priority, :]
        df_indices = df_indices[np.flatnonzero(df[priority_col]==priority)]
        random_index = df_indices[np.argsort(np.random.rand(len(df)))[0]]
        
    return random_index    
'''        

class QClassiPyDrawMask(QWidget):
    
    def __init__(self, parent = None, font = QFont()):
    
        """Initialization"""
    
        super(QClassiPyDrawMask, self).__init__(parent = parent)
        
        self.ui = Ui_QClassiPyDrawMask()
        self.ui.setupUi(self)

        self.best_font = font
        for child_widget in self.findChildren(QWidget):
            child_widget.setFont(font)
        
        self.just_started = True # Needed to distinguish case in which the plugin is closed without ever loading a file
        self.ui.classify_box.setEnabled(False) # Classify box is initialized when a raster is loaded
        
        # Retrieve previous browse directory if possible
        with open(os.path.join(layer_dir, 'browsedir.txt'), 'r') as infile:
            browse_dir = infile.read()
            self.browse_dir = browse_dir if os.path.isdir(browse_dir) else ""    
        
        self.ui.img_browse.clicked.connect(self.imgBrowse) # Load image browse
        self.ui.img_select.clicked.connect(self.loadImg) # Load image select
        
        self.ui.list_browse.clicked.connect(self.listBrowse) # Load tile list browse
        self.ui.list_manual.clicked.connect(self.loadManual) # Choose tile
        self.ui.list_change_file.clicked.connect(self.listChangeFile) # Update mask path
        '''self.list_refresh.clicked.connect(self.loadRandom)''' # Random selection
        
        self.file_df = None # Tile list
        self.file_row = None # List row for chosen tile
        self.img_filename = None # Raster filename
        self.list_filename = None # Tile list filename
        
        self.manual_table = None # Table widget for tile choice
        
        self.categories = None # Symbology
        
        # Hide error messages
        
        self.ui.file_err.setHidden(True)
        self.ui.coord_err.setHidden(True)
        self.ui.list_err.setHidden(True)
        self.ui.list_path_err.setHidden(True)
        
    def imgBrowse(self):
    
        """Load image browse"""
    
        fname, _ = QFileDialog.getOpenFileName(self, "Open file", self.browse_dir, "")
        browse_dir = os.path.split(fname)[0]
        if os.path.isdir(browse_dir) :
            self.browse_dir =  browse_dir
            
        self.ui.img_fileload.setText(fname)
        self.ui.file_err.setHidden(True)
        
        self.ui.img_X_edit.setText("")
        self.ui.img_Y_edit.setText("")
        self.ui.img_height_edit.setText("")
        self.ui.img_width_edit.setText("")
        
    def listBrowse(self):
    
        """Load tile list browse"""
    
        fname, _ = QFileDialog.getOpenFileName(self, "Open file", self.browse_dir, "CSV (*.csv)")
        browse_dir = os.path.split(fname)[0]
        if os.path.isdir(browse_dir) :
            self.browse_dir =  browse_dir
            
        self.ui.list_load.setText(fname)
        self.ui.list_err.setHidden(True)
        self.ui.list_path_err.setHidden(True)
        
    def loadImg(self):
    
        """Load image select"""
    
        img_filename = self.ui.img_fileload.text()
        
        self.reset(img_filename) # The reset() method loads a new polyimage
        
        self.file_df = None
        self.file_row = None
        self.list_filename = None
        self.ui.list_load_group.setChecked(False)
        
    def listCheck(self, list_filename):
    
        """Check if tile list is valid"""
        
        # File exists
        
        file_df = None
        valid = True
        try:
            file_df = pd.read_csv(list_filename)
        except:
            return False, False, False, None
        
        # Columns are present
        
        if not all( np.isin(['filename','priority'], list(file_df.columns)) ):
            return False, False, False, file_df
            
        img_coords_present = all(np.isin(['x', 'y', 'width', 'height'], list(file_df.columns)))
        
        valid = True
        valid_except_filename = True
        
        # Check if x, y, height and width column contain integers
        
        if img_coords_present :
            x_type = file_df['x'].to_numpy().dtype
            y_type = file_df['y'].to_numpy().dtype
            width_type = file_df['width'].to_numpy().dtype
            height_type = file_df['height'].to_numpy().dtype
            
            if not(np.issubdtype(x_type, np.integer) and np.issubdtype(y_type, np.integer) and np.issubdtype(width_type, np.integer) and np.issubdtype(height_type, np.integer)) :
                valid = False
                valid_except_filename = False
        
        # Check if filename(s) in tile list exist
        
        for filename in np.unique(file_df['filename']):
            
            filename = str(filename)
            filename_exists = os.path.exists(filename)
            try:
                gdal.Open(filename)
                filename_opens = True
            except:
                filename_opens = False
            
            valid = valid and filename_exists and filename_opens 
            
        return valid, valid_except_filename, img_coords_present, file_df
        
    def listChangeFile(self):
    
        """Update mask path: useful when the tile list and mask have been copied from a different device"""
    
        self.ui.list_err.setHidden(True)
        self.ui.list_path_err.setHidden(True)
        time.sleep(0.5) # Pause so that if the new list is not valid, the user can see the error message disappear and reappear.
    
        list_filename = self.ui.list_load.text()
        valid, valid_except_filename, coords_present, file_df = self.listCheck(list_filename) # Check list with listCheck() method
        
        if not valid_except_filename :
            self.ui.list_err.setHidden(False)
            return
            
        # Browse for new mask path            
        fname, _ = QFileDialog.getOpenFileName(self, "Open file", self.browse_dir, "")
        
        browse_dir = os.path.split(fname)[0]
        if os.path.isdir(browse_dir) :
            self.browse_dir =  browse_dir
            
        file_df['filename'] = fname
            
        file_df.to_csv(list_filename, index=False) # Save tile list
        
    # Load random tile (disabled)    
    '''
    def loadRandom(self):
        
        list_filename = self.ui.list_load.text()
        valid, coords_present, file_df = self.listCheck(list_filename)
        
        if not valid :
            self.ui.list_err.setHidden(False)
            return
        else:
            self.ui.list_err.setHidden(True)            
             
        index = priorityChoice(file_df, priority_col='priority')
        
        self.finishLoad(index, file_df, coords_present, list_filename)
    '''
    
    def loadManual(self):
    
        """Choose tile"""
    
        self.ui.list_manual.clicked.disconnect() # Disable choose tile button until choice is finished
        list_filename = self.ui.list_load.text()
        valid, valid_except_filename, coords_present, file_df = self.listCheck(list_filename) # Check tile list with listCheck() method
        
        if not valid :
            if valid_except_filename :
                self.ui.list_path_err.setHidden(False)
            else:
                self.ui.list_err.setHidden(False)
            self.ui.list_manual.clicked.connect(self.loadManual)
            return
        else:
            self.ui.list_err.setHidden(True)
            self.ui.list_path_err.setHidden(True)
            
        # Create tile table (TableDockFrame class, see table_dock.py file)
        
        self.manual_table = TableDockFrames(file_df, avoid_value = COMPLETED_PRIORITY, font = self.best_font)
        
        # Connect tile table Ok/Cancel buttons to finishLoad() method, this will actually load the chosen tile 
        
        self.manual_table.finished.connect(lambda: self.finishLoad(self.manual_table.getRow(), file_df, coords_present, list_filename))
        
        qgis.utils.iface.actionSelectRectangle().trigger() # Activate rectangle select in QGIS, to select the tile in the map
        
        self.ui.img_load_group.setEnabled(False)
        self.ui.list_load_group.setEnabled(False)
        self.ui.classify_box.setEnabled(False)
        
        # Open the tile table
        qgis.utils.iface.addDockWidget(Qt.RightDockWidgetArea, self.manual_table)
        
    def finishLoad(self, row_num, file_df, coords_present, list_filename):
    
        """Load chosen tile"""
    
        self.manual_table = None
        self.ui.img_load_group.setEnabled(True)
        self.ui.list_load_group.setEnabled(True)
        
        # If the Cancel or Close buttons on the tile table were clicked, do nothing
    
        if row_num is None :
            if not self.just_started :
                self.ui.classify_box.setEnabled(True)
            self.ui.list_manual.clicked.connect(self.loadManual)
            return    
            
        # Write tile information in the Load image fields

        filename = file_df['filename'].iloc[row_num]
        
        if coords_present :
            self.ui.img_X_edit.setText(str(file_df['x'].iloc[row_num]))
            self.ui.img_Y_edit.setText(str(file_df['y'].iloc[row_num]))
            self.ui.img_width_edit.setText(str(file_df['width'].iloc[row_num]))
            self.ui.img_height_edit.setText(str(file_df['height'].iloc[row_num]))
        else:
            self.ui.img_X_edit.setText('')
            self.ui.img_Y_edit.setText('')    
            
        self.reset(filename) # The reset() method opens the polyimage
        
        self.file_df = pd.read_csv(list_filename) # Store tile list
        
        self.file_row = row_num
        self.list_filename = list_filename
        self.ui.img_fileload.setText(filename) # Load image filename
        
        self.ui.list_manual.clicked.connect(self.loadManual) # Reactivate choose tile button
        
    def reset(self, img_filename):
    
        """Load the polyimage"""
    
        if not self.just_started :
            dismantled = self.dismantle() # The dismantle() method removes a previously loaded polyimage
            if not dismantled  :
                return

        # Read the raster if it exists and is in a valid format

        try:
            assert os.path.exists(img_filename)
            img_ds = gdal.Open(img_filename)
            self.ui.file_err.setHidden(True)
        except:
            self.ui.file_err.setHidden(False)            
            return
            
        # Get tile bounds
            
        self.img_filename = img_filename
        
        X_string = self.ui.img_X_edit.text()
        Y_string = self.ui.img_Y_edit.text()
        height_string = self.ui.img_height_edit.text()
        width_string = self.ui.img_width_edit.text()
        
        self.ui.coord_err.setHidden(True)
        if X_string!='' and Y_string!='' and height_string!='' and width_string!='' :
            try:
                self.img_X = int(X_string)
                self.img_Y = int(Y_string)
                self.img_height = int(height_string)
                self.img_width = int(width_string)
            except:
                self.ui.coord_err.setHidden(False)
                return                
        else:
            self.img_X = 0
            self.img_Y = 0
            self.img_height = img_ds.RasterYSize
            self.img_width = img_ds.RasterXSize
            
            self.ui.img_X_edit.setText("0")
            self.ui.img_Y_edit.setText("0")
            self.ui.img_height_edit.setText(str(img_ds.RasterYSize))
            self.ui.img_width_edit.setText(str(img_ds.RasterXSize))
            
        # Open tile

        try:
            
            # Get raster values in the tile bounds
            array = img_ds.ReadAsArray(self.img_X, self.img_Y, self.img_width, self.img_height)
            if img_ds.RasterCount == 1 and len(array.shape) == 2 :
                array = array[np.newaxis, :, :]
            
            # Get raster transform, shape, CRS, metadata
            
            transform = img_ds.GetGeoTransform()
            top_left_x = transform[0] + transform[1]*self.img_X + transform[2]*self.img_Y
            top_left_y = transform[3] + transform[4]*self.img_X + transform[5]*self.img_Y
            transform = (top_left_x, transform[1], transform[2], top_left_y, transform[4], transform[5])
            
            shape = (self.img_height, self.img_width)
            
            crs = img_ds.GetProjection()
            metadata = img_ds.GetMetadata()
            
            # Check for QClassiPy color symbology
            
            qclassipy_metadata = 'qclassipy_values' in metadata # QClassiPy symbology
            qclassipy_metadata_dict = eval(metadata['qclassipy_values']) if qclassipy_metadata else dict()
            
            # Get band_names
            
            band_names = list()
            for i in range(0,img_ds.RasterCount):
                band = img_ds.GetRasterBand(i+1)
                band_name = band.GetDescription()
                band_name = str(i+1) if band_name=="" else band_name
                assert band_name not in band_names
                band_names.append(band_name)
                
                # Build QClassiPy symbology from built-in color table if present
                
                color_table = band.GetColorTable() if img_ds.RasterCount == 1 else None
                
                if not qclassipy_metadata and color_table is not None:
                    table_count = color_table.GetCount()
                    
                    band_color_dict = dict()
                    null_appeared = False
                    
                    for table_value in range(0,table_count):
                        r,g,b,alpha = color_table.GetColorEntry(table_value)
                        color_hex = str(QColor(r,g,b).name())
                        band_color_dict[table_value] = ['NULL', '#ffffff', True] if alpha==0 and not null_appeared else ['', color_hex, False]
                        null_appeared = alpha==0 or null_appeared
                        
                    qclassipy_metadata_dict[band_name] = band_color_dict
            
            metadata['qclassipy_values'] = str(qclassipy_metadata_dict) # Store QClassiPy symbology
            
            # Open PolyImage (see QClassiPy/core/polyimage.py)
            
            self.poly_img = PolyImage(array, transform, crs, metadata = metadata, band_names = band_names)
            
            img_ds = None
            
        except:
            self.ui.coord_err.setHidden(False)
            return 
            
        self.just_started = False
        self.img_saved = True # Changes saved variable
        self.ui.classify_box.setEnabled(True)
        
        # Numpy data type and data type readable by QGIS (not always the same)
        
        self.type_img = np.dtype(self.poly_img.dtype).type
        
        if np.issubdtype(self.type_img, np.integer) :
            self.type_qgis = int #
        elif np.issubdtype(self.type_img, np.floating) :
            self.type_qgis = float
        
        # Fill the Band dropdown menu
        
        band_names = self.poly_img.band_names
        self.ui.band_combo.addItems([str(band_name) for band_name in band_names])
        self.ui.band_combo.setCurrentIndex(0)
        
        # Generate GeoPackage containing pixel polygons

        img_gpkg_name = os.path.join(layer_dir, 'polyimage.gpkg')
        layer_name = 'pixelpolys'
        
        self.poly_img.to_gpkg(img_gpkg_name, layer_name = layer_name)
        
        # Open pixel polygons in QGIS
        
        layer = QgsVectorLayer(img_gpkg_name + "|layername=" + layer_name, "polyimage", "ogr")
        layer.setRenderer(QgsCategorizedSymbolRenderer())
        QgsProject.instance().addMapLayer(layer)
        
        self.layer = layer
        self.poly_mask = None
        
        # Enable editing Tools
        
        self.layer.selectionChanged.connect(self.drawSelection)
        self.ui.layer_select.toggled.connect(self.layerSelection) # Selection
        self.ui.layer_poly.toggled.connect(lambda: self.layerPoly(commit = True)) # Polygons 
        self.ui.layer_brush.toggled.connect(self.layerBrush) # Brush
        self.ui.layer_erase.toggled.connect(self.layerBrush) # Erase
        
        # Symbology
        
        categories = pd.DataFrame({'def': np.array([], dtype=str), # Draw value category name (e.g. water, forest, ejecta...)
                                        'index': np.array([], dtype=int), # Value index in Draw value dropdown
                                        'color': np.array([]), # Value color
                                        'null': np.array([], dtype=bool)}, # Is this the null value?
                                        index = pd.MultiIndex.from_arrays([np.array([]), np.array([], dtype=self.type_img)], 
                                                                          names=["band", "value"]) # Each row corresponds to a band and a band value
                                 )
                                        
        try:
            band_values_dict = eval(self.poly_img.metadata['qclassipy_values'])
            assert type(band_values_dict)==dict
        except:
            band_values_dict = dict()
            
       # Compose symbology
            
        for band_name in band_names:
        
            if band_name in band_values_dict :
                band_categories = band_values_dict[band_name]
                band_values = list(band_categories.keys())
            else:
                band_values = []
            
            other_band_values = np.unique(self.poly_img.bands[band_name])
            other_band_values = other_band_values[~np.isin(other_band_values, band_values)]
            
            null_value_appeared = False
            
            combo_index = 0
            
            for band_value in band_values:
                
                categories.loc[(band_name, band_value), 'index'] = int(combo_index) # Draw value dropdown index
                categories.loc[(band_name, band_value), 'def'] = str(band_categories[band_value][0]) # Draw value category name
                null_band_value = bool(band_categories[band_value][2]) and not null_value_appeared 
                
                # Draw value color
                categories.loc[(band_name, band_value), 'color'] = QColor(str(band_categories[band_value][1])) if not null_band_value else QColor(null_color)
                categories.loc[(band_name, band_value), 'null'] = null_band_value # Is null value?
                if null_band_value :
                    null_value = band_value
                
                null_value_appeared = null_value_appeared or null_band_value
                
                combo_index+=1
                
            # Establish a null value if none was already present in the symbology
                
            if not null_value_appeared :
                null_value = self.type_img(0) if 0 not in band_values else self.type_img(np.amax(band_values)+1)
                categories.loc[(band_name,null_value), ['def', 'index', 'color', 'null']] = ['NULL', int(combo_index), QColor(null_color), True]
                other_band_values = other_band_values[other_band_values!=null_value]
                combo_index += 1
            
            # Assign colors to band values that were not in the symbology 
                
            qcolorlist_update = qcolorlist[~np.isin(qcolorlist, categories.loc[(band_name,),:].loc[np.logical_not(categories.loc[(band_name,),'null']).values, 'color'])]
                
            for i, band_value in enumerate(other_band_values):
            
                categories.loc[(band_name, band_value), 'def'] = ''
                categories.loc[(band_name, band_value), 'index'] = int(combo_index)
                categories.loc[(band_name, band_value), 'color'] = QColor(qcolorlist_update[i])
                categories.loc[(band_name, band_value), 'null'] = False
                combo_index += 1
                
        self.categories = categories
                
        band_categories = categories.loc[(band_names[0],),:].sort_values('index', ascending=True) # Symbology for the chosen band
        
        # Fill Draw value dropdown
        self.ui.draw_value_def.addItems([str(band_value)+'|'+str(band_categories.loc[band_value, 'def']) for band_value in band_categories.index.values])
        
        # Set draw value
        draw_value = band_categories.loc[np.logical_not(band_categories['null']),:].index.values[0] if len(band_categories)>1 else band_categories.index.values[0]
        self.draw_value = self.type_img(draw_value)
        self.ui.draw_value_edit.setText(str(self.draw_value))
        self.ui.draw_value_def.setCurrentIndex(int(band_categories.loc[draw_value, 'index']))

        # Set null value
        self.null_value = self.type_img(band_categories.loc[band_categories['null'],:].index.values[0])
        self.ui.null_value_edit.setText(str(self.null_value))     
        
        self.ui.draw_value_def.currentIndexChanged.connect(self.changeOfValueCombo)
        self.ui.draw_value_def.lineEdit().editingFinished.connect(self.changeOfDef)
        
        if self.draw_value == self.null_value :
            self.setColorStyle()
        else:
            draw_color = self.categories.loc[(band_names[0], self.draw_value),'color']
            self.setColorStyle(draw_color)
            
        self.ui.draw_value_color.clicked.connect(self.changeOfColor) # Color button
        self.ui.rm_draw_value.clicked.connect(self.rmCategory) # Remove class button
        
        self.ui.draw_value_edit.editingFinished.connect(lambda: self.changeOfValue(change='draw')) # Draw value field
        self.ui.null_value_edit.editingFinished.connect(lambda: self.changeOfValue(change='null')) # Null value field
        self.ui.draw_value_edit.setEnabled(True)
        self.ui.brush_width.setEnabled(False)
        
        self.ui.band_combo.currentTextChanged.connect(lambda: self.changeOfValue(change='band')) # Band dropdown
        self.ui.brush_width.valueChanged.connect(self.layerBrush) # Brush width
        
        self.ui.opacity_slider.valueChanged.connect(self.viewSHP) # Opacity
        
        self.ui.save_button.clicked.connect(self.saveImage) # SAVE button
        
        self.viewSHP() # The viewSHP method refreshes the QGIS polyimage layer symbology
        
        # Frame around the polyimage
        
        # Create frame layer
        frame_layer=QgsVectorLayer("Polygon", 'Frame', "memory")
        frame_layer.setCrs(self.layer.crs())
        frame_layer.setExtent(self.layer.extent())
        
        frame_feat=QgsFeature()
        frame_feat.setGeometry(QgsGeometry.fromWkt(self.poly_img.frame.wkt))
        frame_layer.dataProvider().addFeature(frame_feat)
        
        # Set frame layer symbology
        frame_symbol=QgsSymbol.defaultSymbol(frame_layer.geometryType())
        frame_fill = QColor(frame_color)
        frame_fill.setAlpha(0)
        frame_symbol.setColor(frame_fill)
        frame_symbol.symbolLayer(0).setStrokeWidth(1)
        frame_symbol.symbolLayer(0).setStrokeColor(frame_color)
        frame_renderer = QgsSingleSymbolRenderer(frame_symbol)
        frame_layer.setRenderer(frame_renderer)
        frame_layer.triggerRepaint()

        QgsProject.instance().addMapLayer(frame_layer)
        self.frame_layer = frame_layer
        
        # Set QGIS canvas extent
        
        canvas = qgis.utils.iface.mapCanvas()
        map_crs = canvas.mapSettings().destinationCrs()
        layer_crs = layer.crs()
        frame_extent = self.frame_layer.extent()
        
        if map_crs != layer_crs :
            transform = QgsCoordinateTransform(layer_crs, map_crs, QgsProject.instance())
            frame_extent = transform.transformBoundingBox(frame_extent)
        
        canvas.setExtent(frame_extent)
        canvas.refresh()
        qgis.utils.iface.setActiveLayer(self.layer)
        
    def viewSHP(self):
    
        """Refresh QGIS polyimage layer symbology"""

        null_value = self.null_value # Null value
            
        band_name = self.poly_img.band_names[self.ui.band_combo.currentIndex()] # Band name
            
        values = np.unique(self.poly_img.bands[band_name]) # Pixel values in the polyimage
        valid_null_value = null_value in values
        values = np.delete(values, np.flatnonzero(values==null_value))
        values = np.append(null_value, np.sort(values))

        render_categories = np.array([]) # Categories from the QGIS layer renderer
        
        opacity = self.ui.opacity_slider.value()/100 # Opacity
        
        poly_mask_visible = self.ui.layer_poly.isChecked() and self.poly_mask is not None and self.poly_mask.featureCount() > 0
        
        if poly_mask_visible:
            render_categories_mask = np.array([]) # Categories for the polymask layer (if active)
        
        # Set symbology category for each unique value
        
        for value in values: 

            symbol = QgsSymbol.defaultSymbol(self.layer.geometryType())
            
            color = QColor(self.categories.loc[(band_name, value), "color"])
            
            symbol_opacity = 0 if value==null_value else opacity
            symbol.setColor(color)
            symbol.symbolLayer(0).setStrokeStyle(Qt.PenStyle.NoPen)                
            symbol.setOpacity(symbol_opacity)
            
            cat_item = QgsRendererCategory(self.type_qgis(value), symbol, str(value))        
            render_categories = np.append(render_categories, cat_item)
            
            # Polygon layer categories
            
            if poly_mask_visible and value != null_value:
            
                mask_symbol = QgsSymbol.defaultSymbol(self.poly_mask.geometryType())
                
                color.setAlpha(int(opacity*255))
                
                mask_symbol.setColor(color)
                
                color.setAlpha(255)
                mask_symbol.symbolLayer(0).setStrokeWidth(0.25)
                mask_symbol.symbolLayer(0).setStrokeColor(color)
                
                cat_item_mask = QgsRendererCategory(self.type_qgis(value), mask_symbol, str(value))   
                render_categories_mask = np.append(render_categories_mask, cat_item_mask)
            
        # Set polyimage renderer
            
        renderer = QgsCategorizedSymbolRenderer(band_name, list(render_categories))
        self.layer.setRenderer(renderer)
        self.layer.triggerRepaint()
                
        # Set polymask renderer
                
        if poly_mask_visible:
            
            mask_symbol = QgsSymbol.defaultSymbol(self.poly_mask.geometryType())
            
            color = QColor(default_color)
            color.setAlpha(int(opacity*255))
            mask_symbol.setColor(color)
            color.setAlpha(255)
            mask_symbol.symbolLayer(0).setStrokeWidth(0.25)
            mask_symbol.symbolLayer(0).setStrokeColor(color)
            
            cat_item_mask = QgsRendererCategory('', mask_symbol, '')   
            render_categories_mask = np.append(render_categories_mask, cat_item_mask)            
                
            mask_renderer = QgsCategorizedSymbolRenderer(band_name, list(render_categories_mask))
            self.poly_mask.setRenderer(mask_renderer)
            self.poly_mask.triggerRepaint()
            
    def rmCategory(self):
    
        """Remove class"""
    
        band_name = self.poly_img.band_names[self.ui.band_combo.currentIndex()]
    
        band_values = self.categories.loc[(band_name,),:].index.values
        
        if self.ui.rm_current.isChecked(): # Remove current class
        
            rm_values = np.array([self.draw_value], dtype = self.type_img)
            
        elif self.ui.rm_others.isChecked(): # Remove classes other than current
        
            rm_values = band_values[band_values != self.draw_value]
            
        elif self.ui.rm_absent.isChecked(): # Remove classes that are not in this tile
                                            # (though they may be present in the wider raster)
        
            present_values = np.unique(self.poly_img.bands[band_name])
            rm_values = band_values[~np.isin(band_values, present_values)]
            
        elif self.ui.rm_larger.isChecked(): # Remove classes with a value larger than the current one
        
            rm_values = band_values[band_values > self.draw_value]
        
        rm_values = rm_values[rm_values != self.null_value] # Classes to remove
    
        if len(rm_values) == 0:
            return
        
        # Change draw value to null value (the only class that is never removed)
        
        self.ui.draw_value_edit.setText(str(self.null_value))
        self.changeOfValue(change = 'draw')
        
        self.ui.draw_value_def.currentIndexChanged.disconnect()
        self.ui.draw_value_def.lineEdit().editingFinished.disconnect()
        
        # Remove classes from symbology

        self.categories.drop(zip(np.repeat(band_name, len(rm_values)), rm_values), axis=0, inplace=True)
        band_values = self.categories.loc[(band_name,),:].index.values
        self.categories.loc[(band_name,), 'index'] = np.arange(len(band_values), dtype=int)

        # Regenerate draw value dropdown

        self.ui.draw_value_def.clear()
        self.ui.draw_value_def.addItems([str(value)+'|'+str(self.categories.loc[(band_name,value), 'def']) for value in band_values])
        
        # Set the removed classes in the PolyImage to the null value
        
        band_array = self.poly_img.bands[band_name]
        
        change_indices = np.nonzero(np.isin(band_array, rm_values))
        band_array[change_indices] = self.null_value
        change_indices = change_indices[0]*self.poly_img.width + change_indices[1] + 1
        
        self.poly_img.bands[band_name] = band_array
        
        # Set the removed classes in the attribute table of the polyimage layer to the null value
        
        field_idx = self.layer.fields().indexOf(band_name)
        change_dict = {change_indices[i]: {field_idx: self.type_qgis(self.null_value)} for i in range(0,len(change_indices))}

        with edit(self.layer):
            self.layer.dataProvider().changeAttributeValues(change_dict)

        self.ui.draw_value_def.currentIndexChanged.connect(self.changeOfValueCombo)
        self.ui.draw_value_def.lineEdit().editingFinished.connect(self.changeOfDef)       
        
        self.ui.draw_value_edit.setText(str(self.null_value))
        self.changeOfValue(change = 'draw')

        self.viewSHP() # Regenerate symbology
            
    def drawSelection(self, *, draw_value=None):
    
        """Change value of selected pixel polygons, supports the Selection, Brush and Erase tools"""
    
        band_name = self.poly_img.band_names[self.ui.band_combo.currentIndex()]
        
        if draw_value is None :
            draw_value = self.draw_value
            
        # Get selected pixel polygons
    
        selected_features = self.layer.selectedFeatures()
        selected_ax0 = []
        selected_ax1 = []
        
        field_idx = self.layer.fields().indexOf(band_name)
        
        # Get select pixel coordinates
        
        changes_dict = dict()
        for feat in selected_features:
            selected_ax0.append(feat.attribute('ax0'))
            selected_ax1.append(feat.attribute('ax1'))
            changes_dict[feat.id()] = {field_idx: self.type_qgis(draw_value)}
            
        # Set selected pixels to draw value in the polyimage layer
            
        with edit(self.layer):
            self.layer.dataProvider().changeAttributeValues(changes_dict)
            
        # Set selected pixels to draw value in the PolyImage 
            
        self.poly_img[band_name, selected_ax0, selected_ax1] = draw_value
        
        self.layer.removeSelection()
        self.img_saved = False # Indicate unsaved changes
        
        self.viewSHP() # Regenerate symbology
        
    def layerSelection(self, toggled):
    
        """Connect selection of polyimage layer to drawSelection() method, which changes the values of the selected pixel polygons"""
    
        if toggled :
            qgis.utils.iface.actionSelectPolygon().trigger() 
            self.layer.selectionChanged.connect(self.drawSelection)
            self.ui.draw_value_edit.setEnabled(True)
            self.ui.brush_width.setEnabled(False)
        else:
            self.layer.selectionChanged.disconnect(self.drawSelection)
            
    def layerPoly(self, commit = True):
    
        """Create polymask layer"""
    
        band_name = self.poly_img.band_names[self.ui.band_combo.currentIndex()]
        
        # Remove previous polymask layer if present
        
        if self.poly_mask is not None :
            if commit:
                self.poly_mask.commitChanges()
            else:
                self.poly_mask.rollBack()
                
            self.poly_mask.committedGeometriesChanges.disconnect()
            self.poly_mask.committedFeaturesAdded.disconnect()
            self.poly_mask.committedFeaturesRemoved.disconnect()
            self.poly_mask.committedAttributeValuesChanges.disconnect()
            
            provider = self.poly_mask.dataProvider()
            path_to_gpkg = os.path.realpath(provider.dataSourceUri())
            provider.truncate()
            QgsProject.instance().removeMapLayer(self.poly_mask.id())
            os.remove(path_to_gpkg.split('|')[0])
            
            self.poly_mask = None    
        
        # Create new polymask layer
        
        if self.ui.layer_poly.isChecked() :
        
            self.ui.draw_value_edit.setEnabled(False)
            self.ui.brush_width.setEnabled(False)
        
            null_value = self.null_value        
            
            resolution = (np.sqrt(self.poly_img.transform[1]**2+self.poly_img.transform[4]**2) + np.sqrt(self.poly_img.transform[2]**2+self.poly_img.transform[5]**2))/2

            img_poly_name = os.path.join(layer_dir, 'polymask.gpkg')
            
            # Generate polygons over areas of uniform value with to_gpkg() method of the PolyImage class
            feature_count = self.poly_img.to_gpkg(img_poly_name, dissolve_by=band_name, null_values={band_name: null_value}, simplify_tolerance = resolution, layer_name = 'polymask')
            
            # Create QGIS layer
            
            poly_mask = QgsVectorLayer(img_poly_name + "|layername=polymask", "polymask", "ogr")
                
            QgsProject.instance().addMapLayer(poly_mask)        
            self.poly_mask = poly_mask
            qgis.utils.iface.setActiveLayer(self.poly_mask)
            
            self.viewSHP() # Generate symbology
            
            # Connect saved changes to polymask layer with drawPoly() method, which transfers the changes to the polyimage
            
            self.poly_mask.committedGeometriesChanges.connect(lambda layer_id, features: self.drawPoly(features, 'geometry'))
            self.poly_mask.committedFeaturesAdded.connect(lambda layer_id, features: self.drawPoly(features, 'added'))
            self.poly_mask.committedFeaturesRemoved.connect(lambda layer_id, features: self.drawPoly(features, 'removed'))
            self.poly_mask.committedAttributeValuesChanges.connect(lambda layer_id, features: self.drawPoly(features, 'attribute'))
        else:
            qgis.utils.iface.setActiveLayer(self.layer)
            
    def drawPoly(self, changed_features, change_type):
    
        """Transfer to the polyimage changes to the polymask layer"""
    
        band_name = self.poly_img.band_names[self.ui.band_combo.currentIndex()]
        
        null_value = self.null_value

        # Remove polygons where the band name attribute is empty or set to the null value

        request = QgsFeatureRequest().setFilterExpression(f'"{band_name}" = {null_value}')
        null_feat_ids = np.array([feat.id() for feat in self.poly_mask.getFeatures(request)], dtype=int)
        request = QgsFeatureRequest().setFilterExpression(f'"{band_name}" IS NULL')
        null_feat_ids = np.append(null_feat_ids, np.array([feat.id() for feat in self.poly_mask.getFeatures(request)], dtype=int))
        
        null_feat_ids = null_feat_ids[null_feat_ids >= 0]
        
        # Get features that have been changed
        
        if change_type == 'geometry' or change_type == 'attribute':
            feat_ids = list(changed_features.keys())
        elif change_type == 'added':
            feat_ids = [feat.id() for feat in changed_features]
        else:
            feat_ids = []
            
        feat_ids = np.array(feat_ids, dtype=int)
        feat_ids = feat_ids[~np.isin(feat_ids, null_feat_ids)]
            
        self.poly_mask.committedGeometriesChanges.disconnect()
        self.poly_mask.committedFeaturesAdded.disconnect()
        self.poly_mask.committedFeaturesRemoved.disconnect()
        self.poly_mask.committedAttributeValuesChanges.disconnect()
        
        # Priority field: ensures that the polygons that have been changed are drawn over those that have not been changed
        
        if Qgis.QGIS_VERSION_INT < 33800:
            priority_field = QgsField('priority_rasterize', QVariant.Int)
        else:
            priority_field = QgsField('priority_rasterize', QMetaType.Int)

        self.poly_mask.dataProvider().addAttributes([priority_field])
        self.poly_mask.updateFields()

        if len(null_feat_ids) > 0 :
            self.poly_mask.dataProvider().deleteFeatures(list(null_feat_ids))

        priority_idx = self.poly_mask.fields().indexOf('priority_rasterize')
        priority_dict = {feat_id: {priority_idx: 1} for feat_id in feat_ids}
        for feat in self.poly_mask.getFeatures():
            feat_id = feat.id()
            if feat_id not in feat_ids and feat_id not in null_feat_ids and feat_id >= 0:
                priority_dict[feat_id] = {priority_idx: 0}
        
        self.poly_mask.dataProvider().changeAttributeValues(priority_dict)
        
        # Burn polygons into raster with rasterizeLayer() function (see QClassiPy/core/gdal_tools.py)
        
        band_array = rasterizeLayer(os.path.join(layer_dir, 'polymask.gpkg'),
                                    band_name,
                                    (self.poly_img.height, self.poly_img.width),
                                    self.poly_img.transform,
                                    self.poly_img.crs,
                                    tmp_output_path = os.path.join(layer_dir, 'polymask_raster.tif'),
                                    layer_name = 'polymask',
                                    nodata = null_value,
                                    priority = ('priority_rasterize', [1]),
                                    dtype = self.type_img)
        
        self.poly_mask.dataProvider().deleteAttributes([priority_idx])
        self.poly_mask.updateFields()

        self.poly_mask.committedGeometriesChanges.connect(lambda layer_id, features: self.drawPoly(features, 'geometry'))
        self.poly_mask.committedFeaturesAdded.connect(lambda layer_id, features: self.drawPoly(features, 'added'))
        self.poly_mask.committedFeaturesRemoved.connect(lambda layer_id, features: self.drawPoly(features, 'removed'))
        self.poly_mask.committedAttributeValuesChanges.connect(lambda layer_id, features: self.drawPoly(features, 'attribute'))
                                    
        # Update symbology if new values have been inserted
                                    
        change_indices = np.nonzero(self.poly_img.bands[band_name]-band_array)
        change_values = band_array[change_indices]
        change_indices = change_indices[0]*self.poly_img.width + change_indices[1] + 1
        
        def_num = self.ui.draw_value_def.count()
        
        new_values = np.unique(change_values)
        new_values = new_values[~np.isin(new_values, self.categories.loc[(band_name,),:].index.values)]
        
        for new_value in new_values:
            qcolorlist_update = qcolorlist[~np.isin(qcolorlist, self.categories.loc[(band_name,),:].loc[np.logical_not(self.categories.loc[(band_name,),'null']).values, 'color'])]
            self.categories.loc[(band_name, new_value), ['def', 'color', 'null']] = ['', QColor(qcolorlist_update[0]), False]            
            self.categories.loc[(band_name, new_value), 'index'] = def_num
            self.ui.draw_value_def.addItem(str(new_value)+'|')
            def_num += 1
        
        self.poly_img.bands[band_name] = band_array # Update PolyImage
        
        # Update attribute table of polyimage layer
        
        field_idx = self.layer.fields().indexOf(band_name)
        change_dict = {change_indices[i]: {field_idx: self.type_qgis(change_values[i])} for i in range(0,len(change_indices))}
        
        with edit(self.layer):
            self.layer.dataProvider().changeAttributeValues(change_dict)

        self.img_saved = False # Indicate unsaved changes
            
        self.viewSHP()
        
    def layerBrush(self):

        """Activate Brush or Erase tool and connect selection of polyimage layer to drawSelection() method, 
        which changes the values of the selected pixel polygons"""
    
        brush_toggled = self.ui.layer_brush.isChecked()
        erase_toggled = self.ui.layer_erase.isChecked()
        
        if brush_toggled or erase_toggled :
        
            # The brush width is a multiple of the pixel resolution
        
            brush_width = self.ui.brush_width.value()
            
            resolution = (np.sqrt(self.poly_img.transform[1]**2+self.poly_img.transform[4]**2) + np.sqrt(self.poly_img.transform[2]**2+self.poly_img.transform[5]**2))/2

            self.ui.brush_width.setEnabled(True)
            
            if brush_toggled :
                draw_value = self.draw_value
                self.ui.draw_value_edit.setEnabled(True)
            else:
                draw_value = self.null_value
                self.ui.draw_value_edit.setEnabled(False)
            
            canvas = qgis.utils.iface.mapCanvas()
            
            # Brush tool, handled by the BufferSelectionTool class (see QClassiPy/utils/buffer_selection.py)
            
            tool = BufferSelectionTool(canvas, self.layer, resolution, buffer_size=brush_width)  
            tool.leftButtonReleased.connect(lambda: self.drawSelection(draw_value=draw_value)) # Connect tool to drawSelection()
            canvas.setMapTool(tool)       
            
    def changeOfValue(self, change):
    
        """Handle changes to the null value, the draw value or the band"""
    
        self.ui.draw_value_def.currentIndexChanged.disconnect()
    
        band_name = self.poly_img.band_names[self.ui.band_combo.currentIndex()]

        def_num = self.ui.draw_value_def.count()
        
        # Null value change
    
        if change == 'null' :
            try:
                new_null_value = self.type_img(self.ui.null_value_edit.text())
            except:
                self.ui.null_value_edit.setText(str(self.null_value))
                self.ui.draw_value_def.currentIndexChanged.connect(self.changeOfValueCombo)
                return

            # Modify symbology accordingly
                
            self.categories.loc[(band_name, self.null_value), ['def', 'color', 'null']] = ['', QColor(), False]            
            self.ui.draw_value_def.setItemText(int(self.categories.loc[(band_name, self.null_value), 'index']), str(self.null_value)+'|')
            
            if ~np.isin(new_null_value, self.categories.loc[(band_name,),:].index.values) :
                self.categories.loc[(band_name, new_null_value), ['def', 'color', 'null']] = ['NULL', QColor(null_color), True]
                self.categories.loc[(band_name, new_null_value), 'index'] = def_num
                self.ui.draw_value_def.addItem(str(new_null_value)+'|NULL')
            else:
                self.categories.loc[(band_name, new_null_value), ['def', 'color', 'null']] = ['NULL', QColor(null_color), True]
                self.ui.draw_value_def.setItemText(int(self.categories.loc[(band_name, new_null_value), 'index']), str(new_null_value)+'|NULL')

            qcolorlist_update = qcolorlist[~np.isin(qcolorlist, self.categories.loc[(band_name,),:].loc[np.logical_not(self.categories.loc[(band_name,),'null']).values, 'color'])]
            self.categories.loc[(band_name, self.null_value), 'color'] = QColor(qcolorlist_update[0])
            self.null_value = new_null_value
            
        # Draw value change
            
        elif change == 'draw' :
            try:
                new_draw_value = self.type_img(self.ui.draw_value_edit.text())
            except:
                self.ui.draw_value_edit.setText(str(self.draw_value))
                self.ui.draw_value_def.currentIndexChanged.connect(self.changeOfValueCombo)
                return
                
            self.draw_value = new_draw_value
            
            # If draw value is not among previously used one, create new symbology for this category

            if ~np.isin(new_draw_value, self.categories.loc[(band_name,),:].index.values) :
                qcolorlist_update = qcolorlist[~np.isin(qcolorlist, self.categories.loc[(band_name,),:].loc[np.logical_not(self.categories.loc[(band_name,),'null']).values, 'color'])]
                self.categories.loc[(band_name, new_draw_value), ['def', 'color', 'null']] = ['', QColor(qcolorlist_update[0]), False]            
                self.categories.loc[(band_name, new_draw_value), 'index'] = def_num
                self.ui.draw_value_def.addItem(str(new_draw_value)+'|')
                self.ui.draw_value_def.setCurrentIndex(def_num) 
            else:
                self.ui.draw_value_def.setCurrentIndex(int(self.categories.loc[(band_name, new_draw_value), 'index']))
                
        # Band change
                
        elif change == 'band' :
        
            self.ui.draw_value_def.clear()
            
            band_categories = self.categories.loc[(band_name,),:]
            
            band_values = band_categories.index.values
            
            # New draw values dropdown
            
            self.ui.draw_value_def.addItems([str(value)+'|'+str(band_categories.loc[value, 'def']) for value in band_values])
            
            new_draw_value = band_categories.loc[np.logical_not(band_categories['null']),:].index.values[0] if len(band_categories)>1 else band_categories.index.values[0]
            self.ui.draw_value_def.setCurrentIndex(int(band_categories.loc[new_draw_value, 'index']))
            self.ui.draw_value_edit.setText(str(self.type_img(new_draw_value)))
            self.draw_value = new_draw_value
            
            # New null value
            
            new_null_value = band_categories.loc[band_categories['null'], :].index.values[0]
            self.ui.null_value_edit.setText(str(self.type_img(new_null_value)))
            self.null_value = new_null_value
            
        if self.draw_value==self.null_value :
            self.setColorStyle()
        else:
            draw_color = self.categories.loc[(band_name, self.draw_value),'color']
            self.setColorStyle(draw_color)
            
        band_uniq_values = np.unique(self.poly_img.bands[band_name])
        valid_null_value = self.null_value in band_uniq_values

        if (self.ui.layer_brush.isChecked() or self.ui.layer_erase.isChecked()) and change != 'band' :
            self.layerBrush()
        elif self.ui.layer_poly.isChecked() :
            self.layerPoly(commit = False)
        else:
            pass
            
        self.viewSHP() # Regenerate symbology
        self.ui.draw_value_def.currentIndexChanged.connect(self.changeOfValueCombo)
        
    def changeOfValueCombo(self, current_index):
    
        """Change the draw value via the Draw value dropdown"""
    
        band_name = self.poly_img.band_names[self.ui.band_combo.currentIndex()]

        band_indices = self.categories.loc[(band_name,), 'index']
        draw_value = band_indices.loc[band_indices==current_index].index.values[0]
        
        self.ui.draw_value_edit.setText(str(draw_value))
        self.changeOfValue(change='draw')
        
    def changeOfDef(self):
    
        """Change the name of the draw value category by editing the dropdown"""
    
        new_def = self.ui.draw_value_def.currentText()
    
        current_index = self.ui.draw_value_def.currentIndex()
        
        band_name = self.poly_img.band_names[self.ui.band_combo.currentIndex()]

        band_indices = self.categories.loc[(band_name,), 'index']
        draw_value = self.draw_value
        
        if self.categories.loc[(band_name, draw_value),'null'] :
            self.ui.draw_value_def.setItemText(current_index, str(draw_value)+'|NULL')
            self.ui.draw_value_def.lineEdit().setText(str(draw_value)+'|NULL')
            return
        
        # The category name is separated from the number by a vertical bar (|). Put this in if not already there.
        
        try:
            draw_value_combo = self.type_img(new_def.split('|')[0])
            assert draw_value_combo==draw_value
            new_def = '|'.join(new_def.split('|')[1:])
        except:
            pass
            
        self.ui.draw_value_def.setItemText(current_index, str(draw_value)+'|'+new_def)
        self.ui.draw_value_def.lineEdit().setText(str(draw_value)+'|'+new_def)
            
        self.categories.loc[(band_name, draw_value), 'def'] = new_def
        
    def changeOfColor(self):
    
        """Color button"""
    
        current_index = self.ui.band_combo.currentIndex()
    
        band_name = self.poly_img.band_names[self.ui.band_combo.currentIndex()]
        
        band_indices = self.categories.loc[(band_name,), 'index']
        
        if self.draw_value == self.null_value :
            return
        
        new_color = QColorDialog.getColor()
        
        if not new_color.isValid() :
            return
        
        self.categories.loc[(band_name, self.draw_value), 'color'] = new_color
        
        self.setColorStyle(new_color)
        
        self.viewSHP() 
        
    def setColorStyle(self, new_color = None):
    
        """Change color of the Color button"""
    
        if new_color is None :
            self.ui.draw_value_color.setStyleSheet("")
        else:
            self.ui.draw_value_color.setStyleSheet(f"background-color: {new_color.name()};")
            
        font = self.ui.draw_value_color.font()
        font.setPointSize(11)
        self.ui.draw_value_color.setFont(font)
    
    def saveImage(self):
    
        """Save the polyimage changes to the original raster"""
    
        # Prepare QClassiPy symbology metadata
    
        band_values_dict = dict()
    
        for band_name in self.poly_img.band_names:
        
            band_categories = self.categories.loc[(band_name,),:]
            band_values_dict[band_name] = {band_value: [str(band_categories.loc[band_value, 'def']),
                                                        str(band_categories.loc[band_value, 'color'].name()),
                                                        bool(band_categories.loc[band_value, 'null'])] for band_value in band_categories.index.values}
                                              
        # Open raster
                                                        
        img_ds = gdal.Open(self.img_filename, gdal.GA_Update)
        
        if len(self.poly_img.band_names) != img_ds.RasterCount :
            raise RuntimeError(f"There should be {len(self.poly_img.band_names)} bands, not {img_ds.RasterCount}, in file {self.img_filename}")
        
        band_dict = dict()
        
        # Loop over the bands
        
        for i, band_name in enumerate(self.poly_img.band_names):
            raster_band = img_ds.GetRasterBand(i+1)
        
            # Retrieve the values from the PolyImage and put them in the raster at the tile position
        
            band_array = raster_band.ReadAsArray()
            band_array[self.img_Y:self.img_Y+self.img_height, self.img_X:self.img_X+self.img_width] = self.poly_img.bands[band_name]
            
            # Prepare color table, so that the raster will have the same colors set here if opened in QGIS.
            # Works only on single-band rasters.
            
            color_table = gdal.ColorTable()
            band_categories = self.categories.loc[(band_name,),:]
            band_values = band_categories.index.values
            
            for table_value in range(0,np.amax(band_values)+1):
                if table_value in band_values:
                    value_color = band_categories.loc[table_value, 'color']
                    is_null = bool(band_categories.loc[table_value, 'null'])
                    entry_alpha = 0 if is_null else 255
                    entry_color = (value_color.red(), value_color.green(), value_color.blue(), entry_alpha)
                else:
                    entry_color = (255,255,255,0)
                color_table.SetColorEntry(table_value, entry_color)

            if len(self.poly_img.band_names) == 1:
                raster_band.SetColorTable(color_table)
                raster_band.SetColorInterpretation(gdal.GCI_PaletteIndex)
            
            # Write values to raster
            
            raster_band.WriteArray(band_array)
            raster_band.SetDescription(band_name) # Set band name
            
        # Save metadata, including QClassiPy symbology
            
        metadata = img_ds.GetMetadata()
        metadata['qclassipy_values'] = str(band_values_dict)
        
        img_ds.SetMetadata(metadata)
        
        img_ds.FlushCache()
        
        img_ds = None
        
        self.img_saved = True
        
    def dismantle(self):
    
        """Close the polyimage"""
    
        self.ui.layer_select.setChecked(True)
    
        # Unsaved changes message
    
        if not self.img_saved :
    
            reply = QMessageBox.warning(
                self,
                "Save mask",
                "You have not saved your mask. Proceed anyway?",
                QMessageBox.Ok | QMessageBox.Cancel
            )
            
            nosave_proceed = reply== QMessageBox.Ok
        
            if not nosave_proceed :
                return False
                
        # Set tiles to Completed or Uncompleted
        
        if self.file_df is not None :
            previous_priority = self.file_df.loc[self.file_df.index.values[self.file_row],'priority']
            completeness_index = 1 if previous_priority==COMPLETED_PRIORITY else 0
            
            completeness_text, reply = QInputDialog.getItem(self,
                                                            "Tile completed",
                                                            "Is this tile complete?",
                                                            ["Incomplete", "Complete"],
                                                            completeness_index,
                                                            False)
                                                            
            if not reply :
                return False
                
            new_priority = COMPLETED_PRIORITY if completeness_text=="Complete" else COMPLETED_PRIORITY+1
            self.file_df.loc[self.file_df.index.values[self.file_row],'priority'] = new_priority
            self.file_df.to_csv(self.list_filename, index=False)        
        
        self.poly_img = None
            
        try:
            self.layer.selectionChanged.disconnect()
        except:
            pass
            
        # Remove polyimage and frame layers
            
        provider = self.layer.dataProvider()
        path_to_gpkg = os.path.realpath(provider.dataSourceUri())
        provider.truncate()
        QgsProject.instance().removeMapLayer(self.layer.id())
        QgsProject.instance().removeMapLayer(self.frame_layer.id())
        os.remove(path_to_gpkg.split('|')[0])

        self.layer = None
        self.frame_layer = None
        
        # Remove polymask layer if present
        
        try:
            self.poly_mask.committedGeometriesChanges.disconnect()
            self.poly_mask.committedFeaturesAdded.disconnect()
            self.poly_mask.committedFeaturesRemoved.disconnect()
            self.poly_mask.committedAttributeValuesChanges.disconnect()
            
            provider = self.poly_mask.dataProvider()
            path_to_gpkg = os.path.realpath(provider.dataSourceUri())
            provider.truncate()
            QgsProject.instance().removeMapLayer(self.poly_mask.id())
            os.remove(path_to_gpkg.split('|')[0])

            self.poly_mask = None
        except:
            pass
            
        # Disconnect all buttons
            
        self.ui.layer_select.toggled.disconnect()
        self.ui.layer_poly.toggled.disconnect()
        self.ui.layer_brush.toggled.disconnect()
        self.ui.layer_erase.toggled.disconnect()
        
        self.ui.draw_value_edit.editingFinished.disconnect()
        self.ui.null_value_edit.editingFinished.disconnect()
        self.ui.band_combo.currentTextChanged.disconnect()
        self.ui.band_combo.clear()
        self.ui.brush_width.valueChanged.disconnect()
        
        self.categories = None
        self.ui.draw_value_def.lineEdit().editingFinished.disconnect()
        self.ui.draw_value_def.currentIndexChanged.disconnect()
        self.ui.draw_value_def.clear()
        
        self.ui.draw_value_color.clicked.disconnect()
        self.ui.rm_draw_value.clicked.disconnect()
        
        self.ui.opacity_slider.valueChanged.disconnect()
        
        self.ui.save_button.clicked.disconnect()
        
        time.sleep(2)
        
        return True
        
    def closeEvent(self, event):
    
        """Close the tab"""
    
        if self.manual_table is not None :
        
            self.manual_table.close()
            self.manual_table = None

        dismantled = True
        
        if not self.just_started :
            dismantled = self.dismantle()    
                
        if dismantled :
            
            with open(os.path.join(layer_dir, 'browsedir.txt'), 'w') as outfile:
                outfile.write(self.browse_dir)
            
            event.accept()
        else:
            event.ignore()
