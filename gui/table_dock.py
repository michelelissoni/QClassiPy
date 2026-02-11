"""
Filename: table_dock.py
Author: Michele Lissoni
Date: 2026-02-11
"""

"""

The TableDockFrames class handles the dock widget for the tile choice.

"""

from qgis.PyQt.QtWidgets import QWidget, QAbstractItemView, QTableWidgetItem

from qgis.PyQt.QtGui import QFont, QColor
from qgis.PyQt.QtCore import Qt, pyqtSignal 

from qgis.core import *
from qgis.gui import QgsDockWidget

import qgis.utils

import os
import numpy as np
import pandas as pd

from osgeo import gdal, ogr, osr
import shapely

from ..core.gdal_tools import AffineTransformer
from ..ui.all_uis import Ui_TableDock

from .constants import Directories, Colors, Priorities

layer_dir = Directories.Layer

class TableDock(QgsDockWidget):

    """

    TableDock is the parent of TableDockFrames. It creates a dock widget
    containing a table with data taken from a Pandas dataframe and allows
    the user to choose a row and feed it to the parent script.

    """

    finished = pyqtSignal()

    def __init__(self, df, first_column = None, font = QFont()):
    
        """ Initialization """
    
        if not issubclass(type(df), pd.core.frame.DataFrame) :
            raise ValueError('A Pandas dataframe (or child class) is required.')
    
        super(TableDock, self).__init__()
        
        self.ui = Ui_TableDock()
        self.ui.setupUi(self)
        for child_widget in self.findChildren(QWidget):
            child_widget.setFont(font)
        
        columns = np.array(list(df.columns))
        
        # The column that should go first
        
        if first_column is not None :
            try:
                right_col_index = np.flatnonzero(columns==first_column)[0]
                col_indices = np.append(right_col_index, np.delete(np.arange(len(columns), dtype=int), right_col_index))
                df = df.iloc[:, col_indices]
                columns = columns[col_indices]
            except:
                raise ValueError("The 'first_column' should be either None or a column of the dataframe.")
        
        columns = columns.astype(str)
                
        self.ui.list_table.setColumnCount(len(columns))
        self.ui.list_table.setRowCount(len(df))
        self.ui.list_table.setHorizontalHeaderLabels(columns)
        
        # Rows are selectable, one at a time
        
        self.ui.list_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.ui.list_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        
        # Set up alignments
        
        for i in range(0,len(df)):
            for j in range(0,len(columns)):
                item = QTableWidgetItem(str(df.iloc[i,j]))
                
                if j == 0 :
                    item.setTextAlignment(Qt.AlignVCenter | Qt.AlignRight)
                else:
                    item.setTextAlignment(Qt.AlignVCenter | Qt.AlignHCenter)
                    
                item.setFlags(item.flags() | ~Qt.ItemIsEditable) # Table is not editable
                
                self.ui.list_table.setItem(i, j, item)
                
        # Connect Ok/Cancel buttons
                
        self.ui.buttonBox.accepted.connect(lambda: self.signalSelected(True))
        self.ui.buttonBox.rejected.connect(lambda: self.signalSelected(False))
        self.selectedRow = None
                
    def signalSelected(self, accepted):
    
        """ React to OK/Cancel buttons """
    
        # If OK, set the selectedRow attribute to the selected row index
        # This attribute is then used to get the index by the parent script
    
        if accepted and len(self.ui.list_table.selectedIndexes())>0 :
            self.selectedRow = int(self.ui.list_table.selectedIndexes()[0].row())
        else:
            self.selectedRow = None
            
        self.close()
        
    def getRow(self):
    
        """ Return the selectedRow attribute """
    
        return self.selectedRow
        
    def closeEvent(self, event):
    
        """ Custom signal """
    
        self.finished.emit() # Custom signal to trigger the treatment of the selected row
        
        event.accept()

class TableDockFrames(TableDock):

    """

    TableDockFrames creates a table from a tile list, where each row is
    linked with frame polygons on the QGIS canvas, so that selecting a polygon
    simultaneously selects a table row and viceversa.

    """

    def __init__(self, df, avoid_value = Priorities.Completed, font = QFont()):
    
        """ Initialization """
    
        columns = list(df.columns)
        if not np.all(np.isin(['filename','priority'], columns)) :
            return KeyError("The dataframe must contain the columns 'filename','priority'.")
            
        positions_present = np.all(np.isin(['y','x','height','width'], columns))
            
        super(TableDockFrames, self).__init__(df, first_column = 'filename', font = font)
        
        filenames = np.unique(df['filename'])
        
        gsr_list = []
        allfile_rows = np.zeros(0, dtype=int)
        self.raster_layers = []
        
        # Create frame file
        
        frame_file = os.path.join(layer_dir, 'frames.gpkg')
        layer_name = 'frames'
        
        driver = ogr.GetDriverByName("GPKG")
        if os.path.exists(frame_file):
            driver.DeleteDataSource(frame_file)
        ds = driver.CreateDataSource(frame_file)
        
        # Multiple raster files can in theory be contained in the list
        # In practice, it's almost always just one.
        
        for i in range(0, len(filenames)):
            filename = filenames[i]
            
            # Semi-transparent raster file in the background
            
            raster_layer = QgsRasterLayer(filename, "mask"+str(i))
            raster_layer.setOpacity(0.25)
            QgsProject.instance().addMapLayer(raster_layer)
            self.raster_layers.append(raster_layer)            
            
            file_rows = np.flatnonzero(df['filename']==filename)
            allfile_rows = np.append(allfile_rows, file_rows)
            
            file_ds = gdal.Open(filename)
            file_crs = file_ds.GetProjection()
            height = file_ds.RasterYSize
            width = file_ds.RasterXSize
            
            file_transform = file_ds.GetGeoTransform()
            
            affine_transformer = AffineTransformer(file_transform)
            
            if i == 0 :
            
                # CRS of the frames
                srs = osr.SpatialReference()
                srs.ImportFromWkt(file_crs)
                
            else:
                src_srs = osr.SpatialReference()
                src_srs.ImportFromWkt(file_crs)                
                
            
                                
            if positions_present :
            
                # If the x, y, height, width rows are present, they are used to define frame bounds
                
                x_starts = df['x'].iloc[file_rows].values
                x_ends = x_starts + df['width'].iloc[file_rows].values
                
                y_starts = df['y'].iloc[file_rows].values
                y_ends = y_starts + df['height'].iloc[file_rows].values
                
            else:
            
                # Otherwise, the bounds of the rasters are used
            
                x_starts = np.array([0])
                y_starts = np.array([0])
                x_ends = np.array([width])
                y_ends = np.array([height])
                
            x_starts, y_starts = affine_transformer.xy(y_starts, x_starts)
            x_ends, y_ends = affine_transformer.xy(y_ends, x_ends)
            
            # Frame polygons
            
            frame_list = shapely.to_wkb(np.array([
                                   shapely.Polygon([(x_starts[i], y_starts[i]), 
                                   (x_starts[i], y_ends[i]),
                                   (x_ends[i], y_ends[i]), 
                                   (x_ends[i], y_starts[i]), 
                                   (x_starts[i], y_starts[i])]) 
                                   for i in range(0,len(x_starts))
                                   ]))
                                   
            frame_ogr = [ogr.CreateGeometryFromWkb(frame) for frame in frame_list]
            
            if i == 0 :
                gsr_list = gsr_list + frame_ogr 
            else:
                coord_transformation = osr.CoordinateTransformation(src_srs, srs)
                reprojected_ogr = []
                for frame in frame_ogr:
                    frame_clone = frame.Clone()
                    frame_clone.Transform(coord_transformation)
                    reprojected_ogr.append(frame_clone)
                    
                gsr_list = gsr_list + reprojected_ogr
                
        # Create frame layer and define attributes
                        
        layer = ds.CreateLayer(layer_name, srs, ogr.wkbPolygon)
        
        df = df.iloc[allfile_rows,:]
        
        field_conversion = dict()
        for col_name in columns:
        
            if np.issubdtype(df[col_name].values.dtype, np.integer) :
                field_type = ogr.OFTInteger
                field_conversion[col_name] = int
            elif np.issubdtype(df[col_name].values.dtype, np.floating) :
                field_type = ogr.OFTReal
                field_conversion[col_name] = float
            else:
                field_type = ogr.OFTString
                field_conversion[col_name] = str
                
            layer.CreateField(ogr.FieldDefn(col_name, field_type))
            
        # Define the frame features and their attributes
            
        for i in range(0,len(df)):
        
            feature = ogr.Feature(layer.GetLayerDefn())
            
            feature.SetGeometry(gsr_list[i])
            
            J = 0
            for j, col_name in enumerate(columns):
            
                feature.SetField(j, field_conversion[col_name](df[col_name].iloc[i]))
                
            layer.CreateFeature(feature)
            del feature
            
        ds = None
        
        # Open frame layer in QGIS
        
        allframes_layer = QgsVectorLayer(frame_file+"|layername="+layer_name, "image_frames", "ogr")
        
        nonavoid_color = QColor(Colors.Uncompleted) # Uncompleted frame color
        avoid_color = QColor(Colors.Completed) # Completed frame color
        
        nonavoid_fill = QColor(nonavoid_color)
        nonavoid_fill.setAlpha(25)
        
        avoid_fill = QColor(avoid_color)
        avoid_fill.setAlpha(25)
        
        frame_symbol=QgsSymbol.defaultSymbol(allframes_layer.geometryType())
        frame_renderer=QgsRuleBasedRenderer(frame_symbol)
        
        # Completed and Uncompleted symbology
        
        rule=frame_renderer.rootRule().children()[0].clone()
        rule.setLabel('Complete')
        rule.setFilterExpression("priority="+str(avoid_value))
        rule.symbol().setColor(avoid_fill)
        rule.symbol().symbolLayer(0).setStrokeWidth(0.5)
        rule.symbol().symbolLayer(0).setStrokeColor(avoid_color)
        frame_renderer.rootRule().appendChild(rule)
        
        rule=frame_renderer.rootRule().children()[0].clone()
        rule.setLabel('Incomplete')
        rule.setFilterExpression("priority!="+str(avoid_value))
        rule.symbol().setColor(nonavoid_fill)
        rule.symbol().symbolLayer(0).setStrokeWidth(0.5)
        rule.symbol().symbolLayer(0).setStrokeColor(nonavoid_color)
        frame_renderer.rootRule().appendChild(rule)
        
        frame_renderer.rootRule().removeChildAt(0)
        
        allframes_layer.setRenderer(frame_renderer)
        allframes_layer.triggerRepaint()

        QgsProject.instance().addMapLayer(allframes_layer)
    
        self.allframes_layer = allframes_layer
        
        self.ui.list_table.itemSelectionChanged.connect(self.tableGroupSelection) # If the row is selected, select the frame
        self.allframes_layer.selectionChanged.connect(self.layerGroupSelection) # If the frame is selected, select the row
        
        self.ui.list_table.selectRow(0)
        self.selected_row_tmp = 0
        
        self.ui.buttonBox.accepted.connect(self.removeFrames)
        self.ui.buttonBox.rejected.connect(self.removeFrames)
        
    def tableGroupSelection(self):

        """If the row is selected, select the frame"""

        self.allframes_layer.selectionChanged.disconnect(self.layerGroupSelection)
        self.allframes_layer.removeSelection()

        selected_row = self.ui.list_table.selectedIndexes()[0].row() if len(self.ui.list_table.selectedIndexes())>0 else self.selected_row_tmp
        self.selected_row_tmp = selected_row
        
        self.allframes_layer.select(selected_row)
        self.allframes_layer.selectionChanged.connect(self.layerGroupSelection)
            
    def layerGroupSelection(self):
    
        """If the frame is selected, select the row"""
    
        self.ui.list_table.itemSelectionChanged.disconnect(self.tableGroupSelection)
        self.ui.list_table.clearSelection()
        
        selected_features=self.allframes_layer.selectedFeatures()
        selected_ids=[feat.id() - 1 for feat in selected_features]
        
        if len(selected_ids) > 1 :
            # If more than one frame is selected, keep selected only the first
        
            selected_row = selected_ids[0]
            self.selected_row_tmp = selected_row
            self.allframes_layer.selectionChanged.disconnect(self.layerGroupSelection)
            self.allframes_layer.removeSelection()
            self.allframes_layer.select(selected_row)
            self.ui.list_table.selectRow(selected_row)
            self.allframes_layer.selectionChanged.connect(self.layerGroupSelection)
        elif len(selected_ids) == 1 :
            selected_row = selected_ids[0]
            self.selected_row_tmp = selected_row
            self.ui.list_table.selectRow(selected_row)
        else:
            # Make sure one frame is always selected
        
            self.allframes_layer.selectionChanged.disconnect(self.layerGroupSelection)
            self.allframes_layer.select(self.selected_row_tmp)
            self.ui.list_table.selectRow(self.selected_row_tmp)
            self.allframes_layer.selectionChanged.connect(self.layerGroupSelection)
        
        self.ui.list_table.scrollToItem(self.ui.list_table.item(self.selected_row_tmp, 0), QAbstractItemView.PositionAtCenter)
        self.ui.list_table.itemSelectionChanged.connect(self.tableGroupSelection)
        
    def removeFrames(self):
    
        """Remove frame layer and raster layer"""
    
        for raster_layer in self.raster_layers:
            try:
                QgsProject.instance().removeMapLayer(raster_layer.id())
            except:
                pass
            
        try:
            QgsProject.instance().removeMapLayer(self.allframes_layer.id())
        except:
            pass
        
    def closeEvent(self, event):
    
        """Close"""
    
        self.removeFrames()
        
        super(TableDockFrames, self).closeEvent(event)
