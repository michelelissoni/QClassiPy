"""
Filename: merge_masks.py
Author: Michele Lissoni
Date: 2026-02-11
"""

"""

The QClassiPyMergeMasks class handles the "Merge masks" tab.

"""

from qgis.PyQt.QtWidgets import QWidget, QFileDialog
from qgis.PyQt.QtGui import QColor, QFont
from qgis.PyQt.QtCore import QTimer

import os
import time
import gc
import ast
import warnings

import numpy as np
import pandas as pd

from osgeo import gdal

from ..core.positions import positionOverlaps
from ..core.polyimage import PolyImage
from ..core.gdal_tools import generateTiff
from ..ui.all_uis import Ui_QClassiPyMergeMasks

from .constants import Directories, Priorities, Colors

COMPLETED_PRIORITY = Priorities.Completed
UNCOMPLETED_PRIORITY = Priorities.Uncompleted

layer_dir = Directories.Layer

default_color = QColor(Colors.Default)
colorlist = Colors.Colorlist

class QClassiPyMergeMasks(QWidget):

    def __init__(self, parent = None, font = QFont()):
    
        """Initialization"""
    
        super(QClassiPyMergeMasks, self).__init__(parent = parent)
        
        self.ui = Ui_QClassiPyMergeMasks()
        self.ui.setupUi(self)
        for child_widget in self.findChildren(QWidget):
            child_widget.setFont(font)
        
        self.ui.list1_err.setHidden(True)
        self.ui.list2_err.setHidden(True)
        
        self.ui.list_saveerr.setHidden(True)
        self.ui.mask_saveerr.setHidden(True)
        
        self.ui.shape_err.setHidden(True)
        self.ui.tile_err.setHidden(True)
        
        self.ui.list1_browse.clicked.connect(lambda: self.listBrowse(1))
        self.ui.list2_browse.clicked.connect(lambda: self.listBrowse(2))
        
        self.ui.list_savebrowse.clicked.connect(lambda: self.saveBrowse('list'))
        self.ui.mask_savebrowse.clicked.connect(lambda: self.saveBrowse('mask'))
        
        self.ui.list1_change_file.clicked.connect(lambda: self.listChangeFile(1))
        self.ui.list2_change_file.clicked.connect(lambda: self.listChangeFile(2))
        
        self.ui.merge_button.clicked.connect(self.mergeMasks) # MERGE button
        self.ui.merged_message.setHidden(True)
        
        self.merged_tmr = QTimer()
        self.merged_tmr.setSingleShot(True)
        self.merged_tmr.timeout.connect(lambda: self.ui.merged_message.setHidden(True))
        
        with open(os.path.join(layer_dir, 'browsedir.txt'), 'r') as infile:
            browse_dir = infile.read()
            self.browse_dir = browse_dir if os.path.isdir(browse_dir) else ""  
        
    def listBrowse(self, num):
    
        """Input tile lists browse"""
    
        fname, _ = QFileDialog.getOpenFileName(self, "Open file", self.browse_dir, "CSV (*.csv)")
        browse_dir = os.path.split(fname)[0]
        if os.path.isdir(browse_dir) :
            self.browse_dir =  browse_dir

        if num == 1 :
            self.ui.list1_load.setText(fname)
            self.ui.list1_err.setHidden(True)
        elif num == 2 :
            self.ui.list2_load.setText(fname)
            self.ui.list2_err.setHidden(True)
            
        self.ui.shape_err.setHidden(True)
        self.ui.tile_err.setHidden(True)
            
    def saveBrowse(self, path_type):
    
        """Merged outputs (mask and tile list) browse"""
    
        if path_type == 'mask' :
            fname, _ = QFileDialog.getSaveFileName(self, "Save file", os.path.join(self.browse_dir, 'mask.tif'), "TIF (*.tif *.tiff)")
            self.ui.mask_save.setText(fname)
            self.ui.mask_saveerr.setHidden(True)  
            
        elif path_type=='list' :
            fname, _ = QFileDialog.getSaveFileName(self, "Save file", os.path.join(self.browse_dir, 'list.csv'), "CSV (*.csv)")
            self.ui.list_save.setText(fname)
            self.ui.list_saveerr.setHidden(True)   
        
        self.browse_dir = os.path.split(fname)[0] 
        
    def listCheck(self, list_filename):
    
        """Check that the tile lists contain all the columns"""
        
        file_df = None
        valid = True
        try:
            file_df = pd.read_csv(list_filename)
        except:
            return False, False, None
        
        if not all( np.isin(['filename','priority','x', 'y', 'width', 'height'], list(file_df.columns)) ) :
            return False, False, file_df
        
        filename = np.unique(file_df['filename'])
        
        valid_except_filename = len(filename)==1
            
        filename = str(filename[0])
            
        valid = os.path.exists(filename)
            
        return valid, valid_except_filename, file_df        
        
    def listChangeFile(self, num):
    
        """Update mask path"""
    
        if num == 1 :
            self.ui.list1_err.setHidden(True)
            list_filename = self.ui.list1_load.text()
        elif num == 2 :
            self.ui.list2_err.setHidden(True)
            list_filename = self.ui.list2_load.text()
            
        self.ui.shape_err.setHidden(True)
        self.ui.tile_err.setHidden(True)
            
        time.sleep(0.5) # Pause so that if the new list is not valid, the user can see the error message disappear and reappear.
    
        valid, valid_except_filename, file_df = self.listCheck(list_filename)
        
        if not valid_except_filename :
            if num == 1 :
                self.ui.list1_err.setHidden(False)
            elif num == 2 :
                self.ui.list2_err.setHidden(False)

            return
        
        fname, _ = QFileDialog.getOpenFileName(self, "Open file", self.browse_dir, "TIF (*.tif *.tiff)")
        
        browse_dir = os.path.split(fname)[0]
        if os.path.isdir(browse_dir) :
            self.browse_dir =  browse_dir
            
        file_df['filename'] = fname
        
        file_df.to_csv(list_filename, index=False)
        
    def listsMasksCompatible(self):
    
        """Check if the two lists are compatible and open their raster files"""
    
        self.ui.list1_err.setHidden(True)
        self.ui.list2_err.setHidden(True)
        self.ui.shape_err.setHidden(True)
        self.ui.tile_err.setHidden(True)
    
        valid1, _, list1_df = self.listCheck(self.ui.list1_load.text())        
        valid2, _, list2_df = self.listCheck(self.ui.list2_load.text())
        
        # Open mask 1
        
        try:
            assert os.path.exists(list1_df['filename'].iloc[0])
            mask_ds = gdal.Open(list1_df['filename'].iloc[0])
            mask1 = mask_ds.ReadAsArray()
            shape1 = mask1.shape
            if mask_ds.RasterCount == 1 and len(shape1) == 2 :
                mask1 = mask1[np.newaxis, :, :]
                shape1 = mask1.shape
            
            transform = mask_ds.GetGeoTransform()
            crs = mask_ds.GetProjection()
            band_names1 = [mask_ds.GetRasterBand(i+1).GetDescription() for i in range(0,shape1[0])]
            
            metadata1 = mask_ds.GetMetadata()
            
            mask_ds = None
            
        except:
            valid1 = False
        
        # Open mask 2

        try:
            assert os.path.exists(list2_df['filename'].iloc[0])
            mask_ds = gdal.Open(list2_df['filename'].iloc[0])
            mask2 = mask_ds.ReadAsArray()
            shape2 = mask2.shape
            
            if mask_ds.RasterCount == 1 and len(shape2) == 2 :
                mask2 = mask2[np.newaxis, :, :]
                shape2 = mask2.shape
            
            band_names2 = [mask_ds.GetRasterBand(i+1).GetDescription() for i in range(0,shape2[0])]
            
            metadata2 = mask_ds.GetMetadata()
            
            mask_ds = None
            
        except:
            valid2 = False
            
        if not valid1 :
            self.ui.list1_err.setHidden(False)
            
        if not valid2 :
            self.ui.list2_err.setHidden(False)
            
        if not valid1 or not valid2 :
            return False, None, None, None, None, None, None, None, None, None, None
            
        # Check if masks have the same shape
            
        masks_compatible = shape1==shape2 and mask1.dtype == mask2.dtype
        if not masks_compatible :
            self.ui.shape_err.setHidden(False)
        
        # Check if the two lists have the same tiles
        
        list1_df = list1_df.sort_values(['x','y'], ignore_index=True)
        list2_df = list2_df.sort_values(['x','y'], ignore_index=True)
            
        lists_compatible = list1_df.loc[:,['x','y','height','width']].equals(list2_df.loc[:,['x','y','height','width']])
            
        if not lists_compatible :
            self.ui.tile_err.setHidden(False)
            return False, None, None, None, None, None, None, None, None, None, None
        
        return True, mask1, band_names1, metadata1, list1_df, mask2, band_names2, metadata2, list2_df, transform, crs
            
    def mergeMasks(self):
    
        """Merge masks"""
    
        # Check if lists and masks are compatible
        compatible, mask1, band_names1, metadata1, list1_df, mask2, band_names2, metadata2, list2_df, transform, crs = self.listsMasksCompatible()
    
        if not compatible :
            return
        
        mask_savepath = self.ui.mask_save.text()
        list_savepath = self.ui.list_save.text()
        
        save_error = False
        if not os.path.isdir(os.path.split(mask_savepath)[0]) or os.path.splitext(mask_savepath)[1] not in ['.tif','.tiff'] :
            self.ui.mask_saveerr.setHidden(False)
            save_error = True
            
        if not os.path.isdir(os.path.split(list_savepath)[0]) or os.path.splitext(list_savepath)[1] != '.csv' :
            self.ui.list_saveerr.setHidden(False)
            save_error = True
            
        if save_error :
            return
        
        
        # Check which tiles overlap (see QClassiPy/core/positions.py)
        overlaps = positionOverlaps(list1_df['y'].values, list1_df['x'].values, list1_df['height'].values, list1_df['width'].values)
            
        # Check which tiles have been completed in list 1 and not 2, 2 and not 1, both 1 and 2    
        
        completed_1not2 = list1_df.index.values[(list1_df['priority']==COMPLETED_PRIORITY) & (list2_df['priority']!=COMPLETED_PRIORITY)]
        completed_2not1 = list1_df.index.values[(list1_df['priority']!=COMPLETED_PRIORITY) & (list2_df['priority']==COMPLETED_PRIORITY)]
        completed_1and2 = list1_df.index.values[(list1_df['priority']==COMPLETED_PRIORITY) & (list2_df['priority']==COMPLETED_PRIORITY)]
        completed_1 = np.append(completed_1not2, completed_1and2)
        completed_2 = np.append(completed_2not1, completed_1and2)
        
        cols1 = list1_df.columns.values
        cols2 = list2_df.columns.values
        cols_2not1 = cols2[~np.isin(cols2, cols1)]
        cols_1and2 = cols1[np.isin(cols1, cols2)]
        
        final_list = list1_df.copy()
        final_list.loc[:, cols_2not1] = list2_df.loc[:, cols_2not1] # Add any additional columns in list 2
        
        final_list.loc[completed_2not1, cols_1and2] = list2_df.loc[completed_2not1, cols_1and2] # For the completed tiles in list 2 only, 
                                                                                                # the columns have the list 2 values
        
        
        # The final list has an 'overlap' column, indicating whether a given tile had an overlap
        # between two completed tiles from different lists. It also has a 'tile_list' column,
        # indicating where the values in the final mask come from for each tile.
        
        final_list['overlap'] = False 
        final_list['tile_list'] = np.ones(len(final_list), dtype=int)*(-1) # 'tile_list' is set to -1 for uncompleted tiles
        
        final_list.loc[completed_1and2, 'overlap'] = True
        
        for index in completed_1not2:
            final_list.loc[index, 'overlap'] = np.any(np.isin(overlaps[index], completed_2))
        for index in completed_2not1:
            final_list.loc[index, 'overlap'] = np.any(np.isin(overlaps[index], completed_1))
        
        final_list.loc[final_list['overlap'], 'priority'] = COMPLETED_PRIORITY        
        
        final_list.loc[completed_1, 'tile_list'] = 1
        final_list.loc[completed_2not1, 'tile_list'] = 2
        
        final_mask = mask1.copy() # The final mask is the same as mask 1 everywhere except in the tiles completed only in list 2
        
        for index in completed_2not1:
            x = int(list2_df.loc[index, 'x'])
            y = int(list2_df.loc[index, 'y'])
            height = int(list2_df.loc[index, 'height'])
            width = int(list2_df.loc[index, 'width'])
            
            final_mask[:, y:y+height, x:x+width] = mask2[:, y:y+height, x:x+width]
            
        # Transferring again the values for the completed tiles in list 1, so that
        # in overlapping areas mask 1 has priority.
            
        for index in completed_1:
            x = int(list1_df.loc[index, 'x'])
            y = int(list1_df.loc[index, 'y'])
            height = int(list1_df.loc[index, 'height'])
            width = int(list1_df.loc[index, 'width'])
            
            final_mask[:, y:y+height, x:x+width] = mask1[:, y:y+height, x:x+width]

        # Band names for mask 1 prevail, unless one band has an empty name in mask 1, then the mask 2 name is used.
            
        band_names = []
        
        valid_bands1 = True
        valid_bands2 = True
        
        for i in range(0,len(band_names1)):
            valid_band1 = band_names1[i]!=""
            valid_band2 = band_names2[i]!=""
            if valid_band1 :
                band_names.append(band_names1[i])
            elif valid_band2 :
                band_names.append(band_names2[i])
            else:
                band_names.append(str(i+1))
                
            valid_bands1 = valid_bands1 and valid_band1
            valid_bands2 = valid_bands2 and valid_band2
            
        valid_bands1 = valid_bands1 and len(band_names1)==len(set(band_names1))
        valid_bands2 = valid_bands2 and len(band_names2)==len(set(band_names2))
        
        band_names1 = band_names1 if valid_bands1 else band_names
        band_names2 = band_names2 if valid_bands2 else band_names
        
        # QClassiPy symbology: mask 1 prevails, but if the symbology in mask 2 encompasses values
        # not predicted in mask 2, they are added  
        
        empty_band_values_dict = {band_name: {} for band_name in band_names}  
        
        if 'qclassipy_values' in metadata1 and valid_bands1:
            try:
                band_values_dict1 = ast.literal_eval(metadata1['qclassipy_values'])
            except:
                warnings.warn("Potentially harmful code in the `qclassipy_values` slot of the metadata of mask 1.")
                band_values_dict1 = empty_band_values_dict.copy()
        else:
            band_values_dict1 = empty_band_values_dict.copy()   
        
        if 'qclassipy_values' in metadata2 and valid_bands2:
            try:
                band_values_dict2 = ast.literal_eval(metadata2['qclassipy_values'])
            except:
                warnings.warn("Potentially harmful code in the `qclassipy_values` slot of the metadata of mask 2.")
                band_values_dict2 = empty_band_values_dict.copy()
        else:
            band_values_dict2 = empty_band_values_dict.copy()  
        
        final_band_values_dict = dict()
        
        for i, band_name in enumerate(band_names):
        
            uniq_values_final = np.unique(final_mask[i,:,:])
        
            band_name1 = band_names1[i]
            band_name2 = band_names2[i]
        
            values_dict1 = band_values_dict1[band_name1]
            values_dict2 = band_values_dict2[band_name2]
            
            values_in_dicts = np.unique(list(values_dict1.keys())+list(values_dict2.keys()))
            
            uniq_values_final = np.unique(np.append(uniq_values_final, values_in_dicts))
            
            final_values_dict = dict()
            
            null_value = None
            
            for j, value in enumerate(uniq_values_final):
                if value in values_dict1 :
                    is_null_value = values_dict1[value][2]
                    category_name = values_dict1[value][0] if not is_null_value else ""
                    if is_null_value :
                        null_value = value
                # If a value is not in symbology 1 but is in symbology 2, it prevails
                elif value in values_dict2 :
                    is_null_value = values_dict2[value][2]
                    category_name = values_dict2[value][0] if not is_null_value else ""
                    if is_null_value and null_value is None :
                        null_value = value
                else:
                    is_null_value = False
                    category_name = ""
                
                category_color = str(colorlist[j].name())
                final_values_dict[value] = [category_name, category_color, is_null_value]
            
            # Set new null value if none is found in the symbologies
            if null_value is None :
                null_value = 0 if 0 not in values_in_dicts else np.amax(uniq_values_final) + 1
            final_values_dict[null_value] = ["NULL", str(default_color.name()), True]
                
            final_band_values_dict[band_name] = final_values_dict        
        
        # Metadata, copied from mask 1
        final_metadata = metadata1.copy()
        final_metadata['qclassipy_values'] = str(final_band_values_dict)
        
        final_mask_dict = {band_names[i]: final_mask[i,:,:] for i in range(0,len(band_names))}
        final_mask_shape = (final_mask.shape[1], final_mask.shape[2])
        del final_mask
        gc.collect()
        
        # Save final mask
        
        generateTiff(mask_savepath,
                     final_mask_dict,
                     transform,
                     final_mask_shape, 
                     crs, 
                     metadata = final_metadata)
        
        # Save final list
        
        final_list.to_csv(list_savepath, index = False)
        
        self.ui.merged_message.setHidden(False)
        
        self.merged_tmr.start(1000)
        
