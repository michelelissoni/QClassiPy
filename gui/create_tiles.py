"""
Filename: create_tiles.py
Author: Michele Lissoni
Date: 2026-02-10
"""

"""

The QClassiPyCreateTiles class handles the "Create tiles" tab.

"""

from qgis.PyQt.QtWidgets import QWidget, QAbstractItemView, QTableWidgetItem, QFileDialog
from qgis.PyQt.QtGui import QColor, QFont
from qgis.PyQt.QtCore import Qt, QTimer

from qgis.core import *
from qgis.gui import QgsMapTool, QgsProjectionSelectionDialog, QgsDockWidget

import qgis.utils

import os
import gc
import numpy as np
import pandas as pd

import shapely
from osgeo import gdal

from ..core.positions import gridPositions
from ..core.gdal_tools import generateTiff, AffineTransformer, CoordTransformXY
from ..ui.all_uis import Ui_QClassiPyCreateTiles

from .constants import Directories, Colors

layer_dir = Directories.Layer

bounds_color = QColor(Colors.Tile_Bounds)

class QClassiPyCreateTiles(QWidget):
    
    def __init__(self, parent = None, font = QFont()):
    
        """Initialization"""
    
        super(QClassiPyCreateTiles, self).__init__(parent = parent)
        
        self.ui = Ui_QClassiPyCreateTiles()
        self.ui.setupUi(self)

        for child_widget in self.findChildren(QWidget):
            child_widget.setFont(font)
        
        self.ui.crs_wkt.textChanged.connect(lambda: self.boundConvert(True)) # Other CRS WKT 
        self.ui.crs_predef.clicked.connect(self.predefCRS) # Predefined button
        self.ui.crs_wkt.setEnabled(False)
        self.ui.crs_predef.setEnabled(False)
        self.ui.bounds_box.setEnabled(False)
        
        with open(os.path.join(layer_dir, 'browsedir.txt'), 'r') as infile:
            browse_dir = infile.read()
            self.browse_dir = browse_dir if os.path.isdir(browse_dir) else ""
        
        self.ui.raster_browse.clicked.connect(self.rasterBrowse) # Choose raster, browse button
        self.ui.raster_select.clicked.connect(self.rasterSelect) # Choose raster, select button
        
        self.tile_mask_shape = None # Mask shape
        self.tile_mask_crs = None # Mask CRS
        self.tile_mask_transform = None # Mask transform
        self.tile_mask_transformer = None # Mask AffineTransformer
        
        self.bounds_layer = None # Tile bounds frame
        self.bounds_crs = None # Tile bounds CRS
        self.tile_bounds = None # Tile bounds
        self.invalid_bounds = True
        
        # Hiding error messages
        
        self.ui.raster_err.setHidden(True) 
        self.ui.crs_err.setHidden(True)
        self.ui.mask_saveerr.setHidden(True)
        self.ui.list_saveerr.setHidden(True)
        self.ui.bounds_err.setHidden(True)
        self.ui.saved_message.setHidden(True)
        
        # Tile size
        
        self.ui.tile_width.editingFinished.connect(lambda: self.WHCheck('width')) # Width
        self.ui.tile_height.editingFinished.connect(lambda: self.WHCheck('height')) # Height
        
        self.ui.save_tiles.clicked.connect(self.saveTiles) # SAVE button
        self.ui.save_tiles.setEnabled(False) 
        self.saved_tmr = None    
        
        # Mask bands table
        
        self.ui.band_table.setRowHeight(0,20)
        self.ui.band_table.setColumnWidth(0,70)
        self.ui.band_table.setSelectionMode(QAbstractItemView.MultiSelection)
        self.ui.band_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        
        # Add/remove band buttons 
        
        self.ui.band_add.clicked.connect(self.addBand)
        self.ui.band_rm.clicked.connect(self.rmBand)
        self.ui.band_table.itemChanged.connect(self.editBand)        
        
        # Mask and tile list browse buttons
        
        self.ui.mask_savebrowse.clicked.connect(lambda: self.saveBrowse('mask'))
        self.ui.list_savebrowse.clicked.connect(lambda: self.saveBrowse('list'))        
        
    def rasterBrowse(self):
    
        """Choose raster browse button"""
    
        fname=QFileDialog.getOpenFileName(self, "Open file", self.browse_dir, "")
        self.browse_dir = os.path.split(fname[0])[0]
        self.ui.raster_choose.setText(fname[0])
        self.ui.raster_err.setHidden(True)
        
    def rasterSelect(self):
    
        """Choose raster select button"""
    
        self.ui.raster_err.setHidden(True)
        
        # Open raster
        
        try:
            assert os.path.exists(self.ui.raster_choose.text())
            tile_ds = gdal.Open(self.ui.raster_choose.text())        
        except:        
            self.ui.raster_err.setHidden(False)
            return
            
        band_num = self.ui.band_table.rowCount()
        band_names = [self.ui.band_table.item(row, 0).text() for row in range(0,band_num)]
        
        transform = tile_ds.GetGeoTransform()
        crs = tile_ds.GetProjection()
        shape = (tile_ds.RasterYSize, tile_ds.RasterXSize)
        
        # Remove previous bounds frame           
    
        if self.bounds_layer is not None :

            self.bounds_layer.committedGeometriesChanges.disconnect()
            QgsProject.instance().removeMapLayer(self.bounds_layer.id())
            self.bounds_layer = None
            
        # Set mask parameters

        self.tile_mask_crs = crs
        self.tile_mask_transform = transform
        self.tile_mask_shape = (tile_ds.RasterYSize, tile_ds.RasterXSize)

        tile_ds = None

        self.tile_mask_transformer = AffineTransformer(transform)        
        
        # Enable save button and Bounds group box
        
        self.ui.save_tiles.setEnabled(True)
        self.ui.bounds_box.setEnabled(True)
        
        self.ui.crs_wkt.textChanged.disconnect()
        self.ui.crs_wkt.setText("")
        self.ui.crs_wkt.textChanged.connect(lambda: self.boundConvert(True)) 
        
        self.ui.crs_wkt.setEnabled(False)
        self.ui.crs_predef.setEnabled(False)
        self.ui.crs_err.setHidden(True)    
        
        try:
            self.ui.pixel_bounds.toggled.disconnect()
            self.ui.raster_bounds.toggled.disconnect()
            self.ui.other_bounds.toggled.disconnect()
        except:
            pass
        
        # Write bound coordinates
        
        self.ui.topleft_y.setText("0")
        self.ui.topleft_x.setText("0")
        self.ui.bottomright_y.setText(str(self.tile_mask_shape[0]))
        self.ui.bottomright_x.setText(str(self.tile_mask_shape[1]))
        self.ui.topleft_y.setCursorPosition(0)
        self.ui.topleft_x.setCursorPosition(0)
        self.ui.bottomright_x.setCursorPosition(0)
        self.ui.bottomright_y.setCursorPosition(0)
        
        # Store tile bounds
        
        self.tile_bounds = [0, 0, self.tile_mask_shape[0], self.tile_mask_shape[1]]
        self.invalid_bounds = False
        
        # Create bounds frame
        
        bounds_layer=QgsVectorLayer("Polygon", 'Tile bounds', "memory")
        bounds_layer.setCrs(QgsCoordinateReferenceSystem(self.tile_mask_crs))
        
        bounds_feat=QgsFeature()
        bounds_feat.setGeometry(QgsGeometry.fromPolygonXY([[QgsPointXY(*self.tile_mask_transformer.xy(self.tile_bounds[0], self.tile_bounds[1])),
                                                            QgsPointXY(*self.tile_mask_transformer.xy(self.tile_bounds[0], self.tile_bounds[3])),
                                                            QgsPointXY(*self.tile_mask_transformer.xy(self.tile_bounds[2], self.tile_bounds[3])),
                                                            QgsPointXY(*self.tile_mask_transformer.xy(self.tile_bounds[2], self.tile_bounds[1])),
                                                            QgsPointXY(*self.tile_mask_transformer.xy(self.tile_bounds[0], self.tile_bounds[1]))]]))
        bounds_layer.dataProvider().addFeature(bounds_feat)
        
        bounds_symbol=QgsSymbol.defaultSymbol(bounds_layer.geometryType())
        bounds_fill = QColor(bounds_color)
        bounds_fill.setAlpha(0)
        bounds_symbol.setColor(bounds_fill)
        bounds_symbol.symbolLayer(0).setStrokeWidth(1)
        bounds_symbol.symbolLayer(0).setStrokeColor(bounds_color)
        bounds_renderer = QgsSingleSymbolRenderer(bounds_symbol)
        bounds_layer.setRenderer(bounds_renderer)
        bounds_layer.triggerRepaint()

        QgsProject.instance().addMapLayer(bounds_layer)
        self.bounds_layer = bounds_layer        
        self.bounds_layer.committedGeometriesChanges.connect(self.boundPolyEdit)
        
        # Hide error messages
        
        self.ui.crs_err.setHidden(True)
        self.ui.mask_saveerr.setHidden(True)
        self.ui.list_saveerr.setHidden(True)
        self.ui.bounds_err.setHidden(True)
        
        # Connect responses to CRS changes
        
        self.ui.pixel_bounds.setChecked(True)
        
        self.ui.pixel_bounds.toggled.connect(self.boundConvert)
        self.ui.raster_bounds.toggled.connect(self.boundConvert)
        self.ui.other_bounds.toggled.connect(self.boundConvert)
        
        # Connect responses to bound coordinate changes
        
        self.ui.topleft_y.editingFinished.connect(self.boundCheck)
        self.ui.topleft_x.editingFinished.connect(self.boundCheck)
        self.ui.bottomright_x.editingFinished.connect(self.boundCheck)
        self.ui.bottomright_y.editingFinished.connect(self.boundCheck)
        
    def boundConvert(self, checked):
    
        """CRS changes"""
    
        if not checked :
            return
            
        # Pixel coordinates
            
        if self.ui.pixel_bounds.isChecked() :
        
            topleft_y, topleft_x, bottomright_y, bottomright_x = self.tile_bounds
            
            self.bounds_crs = None
            
            self.ui.crs_wkt.setEnabled(False)
            self.ui.crs_predef.setEnabled(False)
            self.ui.crs_err.setHidden(True)
            
        # Raster CRS
            
        elif self.ui.raster_bounds.isChecked() :
        
            # Convert bounds to raster CRS
            topleft_x, topleft_y = self.tile_mask_transformer.xy(self.tile_bounds[0], self.tile_bounds[1])
            bottomright_x, bottomright_y = self.tile_mask_transformer.xy(self.tile_bounds[2], self.tile_bounds[3])
            
            self.bounds_crs = self.tile_mask_crs  
            
            self.ui.crs_wkt.setEnabled(True)
            
            self.ui.crs_wkt.textChanged.disconnect()
            self.ui.crs_wkt.setText(self.tile_mask_crs)
            self.ui.crs_wkt.textChanged.connect(lambda: self.boundConvert(True)) 
            self.ui.crs_wkt.setReadOnly(True)       
            self.ui.crs_predef.setEnabled(False)
            self.ui.crs_err.setHidden(True)
            
        # Other CRS
            
        elif self.ui.other_bounds.isChecked() :
        
            # Convert bounds to raster CRS
            topleft_x, topleft_y = self.tile_mask_transformer.xy(self.tile_bounds[0], self.tile_bounds[1])
            bottomright_x, bottomright_y = self.tile_mask_transformer.xy(self.tile_bounds[2], self.tile_bounds[3])
        
            self.ui.crs_wkt.setEnabled(True)
            self.ui.crs_wkt.setReadOnly(False)
            self.ui.crs_predef.setEnabled(True)
            
            new_crs = self.ui.crs_wkt.toPlainText()
            
            if new_crs=="" :
            
                # If "Other CRS WKT" is empty, use raster CRS
            
                self.bounds_crs = self.tile_mask_crs
                self.ui.crs_wkt.textChanged.disconnect()
                self.ui.crs_wkt.setText(self.tile_mask_crs)
                self.ui.crs_wkt.textChanged.connect(lambda: self.boundConvert(True)) 
                
            else:
            
                # If "Other CRS WKT" is not empty, try to convert coordinates to other CRS, else display error
            
                try:
                
                    mask_to_other = CoordTransformXY(self.tile_mask_crs, new_crs)
                    topleft_x, topleft_y = mask_to_other.transform(topleft_x, topleft_y)
                    bottomright_x, bottomright_y = mask_to_other.transform(bottomright_x, bottomright_y)
                    
                except:
                    self.ui.topleft_y.setEnabled(False)
                    self.ui.topleft_x.setEnabled(False)
                    self.ui.bottomright_x.setEnabled(False)
                    self.ui.bottomright_y.setEnabled(False)
                    self.ui.crs_err.setHidden(False)
                    return
                    
                self.bounds_crs = new_crs
                self.ui.crs_err.setHidden(True)
                
        # Write bound coordinates 
                
        self.ui.topleft_y.setEnabled(True)
        self.ui.topleft_x.setEnabled(True)
        self.ui.bottomright_x.setEnabled(True)
        self.ui.bottomright_y.setEnabled(True)
                    
        self.ui.topleft_y.setText(str(topleft_y))
        self.ui.topleft_x.setText(str(topleft_x))
        self.ui.bottomright_x.setText(str(bottomright_x))
        self.ui.bottomright_y.setText(str(bottomright_y))
        
        self.ui.topleft_y.setCursorPosition(0)
        self.ui.topleft_x.setCursorPosition(0)
        self.ui.bottomright_x.setCursorPosition(0)
        self.ui.bottomright_y.setCursorPosition(0)      
            
    def boundCheck(self):
    
        """Bounds edited"""

        # Retrieve bounds in pixel coordinates

        topleft_y = float(self.ui.topleft_y.text())
        topleft_x = float(self.ui.topleft_x.text())
        bottomright_y = float(self.ui.bottomright_y.text())
        bottomright_x = float(self.ui.bottomright_x.text())
        
        if self.bounds_crs is not None :
        
            other_to_mask = CoordTransformXY(self.bounds_crs, self.tile_mask_crs)
            
            topleft_x, topleft_y = other_to_mask.transform(topleft_x, topleft_y) 
            topleft_y, topleft_x = self.tile_mask_transformer.rowcol(topleft_x, topleft_y)
            
            bottomright_x, bottomright_y = other_to_mask.transform(bottomright_x, bottomright_y)  
            bottomright_y, bottomright_x = self.tile_mask_transformer.rowcol(bottomright_x, bottomright_y)
            
        topleft_y = max(0, int(topleft_y))
        topleft_x = max(0, int(topleft_x))
        bottomright_y = min(self.tile_mask_shape[0], int(bottomright_y))
        bottomright_x = min(self.tile_mask_shape[1], int(bottomright_x))

        if topleft_y >= bottomright_y or topleft_x >= bottomright_x :
            raise ValueError
            
        self.tile_bounds = [topleft_y, topleft_x, bottomright_y, bottomright_x]
        self.invalid_bounds = False
        self.ui.bounds_err.setHidden(True)
        
        # Modify bounds frame
        
        bounds_geometry = QgsGeometry.fromPolygonXY([[QgsPointXY(*self.tile_mask_transformer.xy(self.tile_bounds[0], self.tile_bounds[1])),
                                                      QgsPointXY(*self.tile_mask_transformer.xy(self.tile_bounds[0], self.tile_bounds[3])),
                                                      QgsPointXY(*self.tile_mask_transformer.xy(self.tile_bounds[2], self.tile_bounds[3])),
                                                      QgsPointXY(*self.tile_mask_transformer.xy(self.tile_bounds[2], self.tile_bounds[1])),
                                                      QgsPointXY(*self.tile_mask_transformer.xy(self.tile_bounds[0], self.tile_bounds[1]))]])
        
        
        self.bounds_layer.committedGeometriesChanges.disconnect()
        self.bounds_layer.startEditing()                                   
        self.bounds_layer.changeGeometry(1, bounds_geometry)
        self.bounds_layer.commitChanges()
        self.bounds_layer.committedGeometriesChanges.connect(self.boundPolyEdit)

    def boundPolyEdit(self):
    
        """Bounds changed by modifying frame"""
    
        bounds_geometry = shapely.from_wkt(self.bounds_layer.getGeometry(1).asWkt()).exterior.coords.xy
        
        bounds_row, bounds_col = self.tile_mask_transformer.rowcol(np.array(bounds_geometry[0]), np.array(bounds_geometry[1]))
        
        tile_bounds = [int(np.ceil(np.amin(bounds_row))), int(np.ceil(np.amin(bounds_col))), int(np.ceil(np.amax(bounds_row))), int(np.ceil(np.amax(bounds_col)))]
        
        self.tile_bounds = tile_bounds
        
        self.boundConvert(True)
        
    def predefCRS(self):
    
        """Predefined button clicked, writing CRS WKT"""
    
        dialog = QgsProjectionSelectionDialog()
        dialog.exec_()

        crs = dialog.crs()
        wkt = crs.toWkt()
        
        self.ui.crs_wkt.setText(wkt)
        
    def addBand(self):
    
        """Add band to Mask bands table"""
    
        self.ui.band_table.itemChanged.disconnect()
    
        band_num=self.ui.band_table.rowCount()
        band_names = [self.ui.band_table.item(row, 0).text() for row in range(0,band_num)]
        
        self.ui.band_table.insertRow(band_num)
        self.ui.band_table.setRowHeight(band_num,20) 
        
        band_index = 2
        while('mask'+str(band_index) in band_names):
            band_index += 1
            
        new_band_name = 'mask'+str(band_index)
        
        new_band_item=QTableWidgetItem(new_band_name)
        new_band_item.setFlags(new_band_item.flags() | Qt.ItemIsEditable)
            
        self.ui.band_table.setItem(band_num, 0, new_band_item)
        band_names.append(new_band_name)
        
        self.ui.band_table.itemChanged.connect(self.editBand)
            
    def rmBand(self):
    
        """Remove band from Mask bands table"""
    
        if self.ui.band_table.rowCount()==1 :
            return
    
        self.ui.band_table.itemChanged.disconnect()
    
        selected_indexes=self.ui.band_table.selectedIndexes()
        selected_rows=np.unique(np.array([index.row() for index in selected_indexes],dtype=int))
        
        if len(selected_rows)==self.ui.band_table.rowCount() :
            selected_rows = selected_rows[1:]
    
        for row in selected_rows:
            self.ui.band_table.removeRow(row)
            
        self.ui.band_table.itemChanged.connect(self.editBand)
        
    def editBand(self):
    
        """Edit band names in Mask bands table"""

        band_num=self.ui.band_table.rowCount()
        band_names = [self.ui.band_table.item(row, 0).text() for row in range(0,band_num)]
        
    def saveBrowse(self, path_type):
    
        """Browse for the mask and tile list paths"""
    
        if path_type=='mask' :
            fname=QFileDialog.getSaveFileName(self, "Save file", os.path.join(self.browse_dir, 'mask.tif'), "TIF (*.tif *.tiff)")
            self.ui.mask_save.setText(fname[0])
            self.ui.mask_saveerr.setHidden(True)  
            
        elif path_type=='list' :
            fname=QFileDialog.getSaveFileName(self, "Save file", os.path.join(self.browse_dir, 'tiles.csv'), "CSV (*.csv)")
            self.ui.list_save.setText(fname[0])
            self.ui.list_saveerr.setHidden(True)   
        
        self.browse_dir = os.path.split(fname[0])[0]  
        
    def WHCheck(self, dim):
    
        """Check that the width and height inputs are numbers"""
    
        if dim=='width' :
            try:
                width = int(self.ui.tile_width.text())
            except:
                self.ui.tile_width.setText("224")
        elif dim=='height' :
            try:
                height = int(self.ui.tile_height.text())
            except:
                self.ui.tile_height.setText("224")
        
    def saveTiles(self):
    
        """Save tile list and mask"""
    
        if self.invalid_bounds :
            self.ui.bounds_err.setHidden(False)
            return
            
        # Check mask path
            
        if self.ui.mask_path_box.isChecked() :
    
            mask_path = self.ui.mask_save.text()
            mask_dir, mask_filename = os.path.split(mask_path)
                
            if not os.path.isdir(mask_dir) or mask_filename == "" or os.path.splitext(mask_filename)[1] not in ['.tif', '.tiff'] :
                self.ui.mask_saveerr.setHidden(False)
                return
                
        else:
            mask_path = self.ui.raster_choose.text()
            
        saved_list = False
        saved_mask = False
            
        # Save list
            
        if self.ui.list_path_box.isChecked() :
        
            list_path = self.ui.list_save.text()
            list_dir, list_filename = os.path.split(list_path)
                    
            if not os.path.isdir(list_dir) or list_filename == "" or os.path.splitext(list_filename)[1] != '.csv' :
                self.ui.list_saveerr.setHidden(False)
                return
                
            tile_height = int(self.ui.tile_height.text())
            tile_width = int(self.ui.tile_width.text())
            height_spacing = int((1-self.ui.height_overlap.value()/100)*tile_height)
            width_spacing = int((1-self.ui.width_overlap.value()/100)*tile_width)
            
            # Generate tile positions

            pos_y, pos_x = gridPositions(np.array([self.tile_bounds[0], self.tile_bounds[2]], dtype=int),
                                         np.array([self.tile_bounds[1], self.tile_bounds[3]], dtype=int),
                                         np.array([tile_height, tile_width], dtype=int),
                                         start = None,
                                         spacing = np.array([height_spacing, width_spacing], dtype=int)
                                         )
                                         
            pos_center_y = pos_y + tile_height/2
            pos_center_x = pos_x + tile_width/2
                                     
            # Retain only tile positions inside the bounds frame    
            
            bounds_geometry = shapely.from_wkt(self.bounds_layer.getGeometry(1).asWkt()).exterior.coords.xy
            bounds_y, bounds_x = self.tile_mask_transformer.rowcol(np.array(bounds_geometry[0]), np.array(bounds_geometry[1]))

            contained = shapely.contains_xy(shapely.Polygon(np.hstack([np.array(bounds_x)[:,np.newaxis], np.array(bounds_y)[:,np.newaxis]])), pos_center_x, pos_center_y)
                                         
            positions = pd.DataFrame({'y': pos_y[contained],
                                      'x': pos_x[contained]})
                                      
            positions['height'] = tile_height
            positions['width'] = tile_width
            positions['filename'] = mask_path
            positions['priority'] = 1
            
            positions.to_csv(list_path, index=False)
            
            saved_list = True
        
        # Save mask
        
        if self.ui.mask_path_box.isChecked() :

            band_num=self.ui.band_table.rowCount()        
            band_names = [self.ui.band_table.item(row, 0).text() for row in range(0,band_num)]
            
            band_dict = dict()
            band_values_dict = dict()
            
            # Default symbology
            
            for band_name in band_names:
            
                band_values_dict[band_name] = {0: ['NULL', '#ffffff', True],
                                               1: ['', '#ffffff', False]}
                                               
                band_dict[band_name] = np.zeros(self.tile_mask_shape, dtype=np.uint8)
                                               
            metadata = dict()
            metadata['qclassipy_values'] = str(band_values_dict)   
            
            # Generate mask GeoTIFF  

            generateTiff(mask_path, 
                         band_dict, 
                         self.tile_mask_transform, 
                         self.tile_mask_shape, 
                         self.tile_mask_crs, 
                         metadata = metadata)
            
            saved_mask = True
        
        # "Saved" message
        
        if saved_list or saved_mask :
            
            self.ui.saved_message.setHidden(False)
            
            self.saved_tmr = QTimer()
            self.saved_tmr.setSingleShot(True)
            self.saved_tmr.timeout.connect(lambda: self.ui.saved_message.setHidden(True))
            self.saved_tmr.start(1000)
                
    def closeEvent(self, event):
    
        """Close tab"""

        if self.bounds_layer is not None :
        
            self.bounds_layer.rollBack()
            self.bounds_layer.committedGeometriesChanges.disconnect()
            QgsProject.instance().removeMapLayer(self.bounds_layer.id())
            self.bounds_layer = None
        
        event.accept()
