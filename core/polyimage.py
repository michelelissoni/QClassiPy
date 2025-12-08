import os
import gc

import numpy as np
import pandas as pd

import shapely
from osgeo import osr, ogr, gdal

from .gdal_tools import generateTiff, AffineTransformer

def pixelsToPolys(transform, shape, return_frame=False):

    assert len(transform) == 6
    assert len(shape) == 2
    assert np.issubdtype(type(shape[0]), np.integer) and np.issubdtype(type(shape[1]), np.integer)
    
    if(transform[2]==0 and transform[4]==0): # A more efficient computation
    
        x_bounds = np.linspace(transform[0], transform[0]+transform[1]*shape[1], shape[1]+1)
        y_bounds = np.linspace(transform[3], transform[3]+transform[5]*shape[0], shape[0]+1)

        geom_list = []
        
        for i in range(0, shape[0]):
            for j in range(0, shape[1]):
                geometry = shapely.Polygon([
                [x_bounds[j], y_bounds[i]],
                [x_bounds[j+1], y_bounds[i]],
                [x_bounds[j+1], y_bounds[i+1]],
                [x_bounds[j], y_bounds[i+1]],
                [x_bounds[j], y_bounds[i]]
                ])
        
                geom_list.append(geometry)
                
        frame = shapely.Polygon([
        [x_bounds[0], y_bounds[0]],
        [x_bounds[-1], y_bounds[0]],
        [x_bounds[-1], y_bounds[-1]],
        [x_bounds[0], y_bounds[-1]],
        [x_bounds[0], y_bounds[0]]
        ])
        
    else:

        transformer = AffineTransformer(transform)
        
        px_corners = np.reshape(np.mgrid[0:shape[0]+1, 0:shape[1]+1], (2, (shape[0]+1)*(shape[1]+1)))
        
        poly_x, poly_y = transformer.xy(px_corners[1,:], px_corners[0,:])
        
        del px_corners
        
        geom_list = []
        
        for i in range(0, shape[0]):
            for j in range(0, shape[1]):
            
                poly = shapely.Polygon([[poly_x[i*(shape[1]+1)+j], poly_y[i*(shape[1]+1)+j]],
                                        [poly_x[i*(shape[1]+1)+(j+1)], poly_y[i*(shape[1]+1)+(j+1)]],
                                        [poly_x[(i+1)*(shape[1]+1)+(j+1)], poly_y[(i+1)*(shape[1]+1)+(j+1)]],
                                        [poly_x[(i+1)*(shape[1]+1)+j], poly_y[(i+1)*(shape[1]+1)+j]],
                                        [poly_x[i*(shape[1]+1)+j], poly_y[i*(shape[1]+1)+j]]])

                geom_list.append(poly)
                
        frame = shapely.Polygon([
                                 [poly_x[0], poly_y[0]],
                                 [poly_x[shape[1]], poly_y[shape[1]]],
                                 [poly_x[-1], poly_y[-1]],
                                 [poly_x[shape[0]*(shape[1]+1)], poly_y[shape[0]*(shape[1]+1)]],
                                 [poly_x[0], poly_y[0]]
                                ])
                                
        del poly_x, poly_y
        gc.collect()
    
    if(return_frame):
        return geom_list, frame
    else:
        return geom_list

class PolyArray:
    def __init__(self, band_arrays, geometries, band_names=None, crs=None):
        """
        Initialize a PolyArray object.
        
        Parameters:
        - band_arrays (dict): A dictionary mapping band names to 2D NumPy arrays (y, x).
        - geometries (list): A list of Shapely geometries of length (y * x), corresponding to (y, x) indices.
        """
        
        value_err_message = "band_arrays must be either a dictionary mapping band names to 2D NumPy arrays or a 3D NumPy array with the first dimension being the bands."
        
        if(isinstance(band_arrays, np.ndarray)):
            if(band_arrays.ndim!=3):
                raise ValueError(value_err_message)

            if(not(np.issubdtype(band_arrays.dtype, np.floating) or np.issubdtype(band_arrays.dtype, np.integer))):
                raise TypeError("Only numeric dtypes (int, float) are acceptable.")
        
            if(band_names is None):
                band_names = np.arange(band_arrays.shape[0],dtype=int).astype(str)
            elif(len(band_names)!= band_arrays.shape[0]):
                raise ValueError("The band names must have the same length as the 3D array's first dimension.")
            
            band_dict = dict()
            for i in range(0, len(band_names)):
                band_dict[band_names[i]] = band_arrays[i,:,:]
        
            self.bands = band_dict
            self.band_names = band_names
            self.height, self.width = band_arrays.shape[1], band_arrays.shape[2]
        
        elif(isinstance(band_arrays,dict)):
            if(not all(isinstance(v, np.ndarray) and v.ndim == 2 for v in band_arrays.values())):
                raise ValueError(value_err_message)
        
            first_arr = next(iter(band_arrays.values()))
            first_shape = first_arr.shape
            first_dtype = first_arr.dtype
            if(not all(v.shape == first_shape for v in band_arrays.values())):
                raise ValueError("All bands must have the same (y, x) shape.")    

            if(not(np.issubdtype(first_dtype, np.floating) or np.issubdtype(first_dtype, np.integer))):
                raise TypeError("Only numeric dtypes (int, float) are acceptable.")
     
            self.bands = band_arrays
            self.band_names = list(band_arrays.keys())
            self.height, self.width = first_shape
                
        else:
            raise ValueError(value_err_message)
        
        if(len(geometries) != self.height * self.width):
            raise ValueError("Geometries list must have length equal to y * x.")
        
        self.geometries = geometries

        self.crs = crs
    
    def _create_new_instance(self, band_arrays, geometries, band_names=None, crs=None):
    
        return self.__class__(band_arrays, geometries, band_names=band_names, crs=crs)
    
    def __getitem__(self, key):
        """
        Retrieves a portion of the array, along with corresponding geometries.
        
        Supports:
        - poly_array["band_name", y, x]
        - poly_array["band_name", y_slice, x_slice]
        - poly_array[:, y_slice, x_slice] (returns a new PolyArray with selected bands)
        """

        if(not(isinstance(key, tuple))):
            raise TypeError("Invalid key format. Use ('band_name', y, x) or (:, y_slice, x_slice).")
        
        band_key, y_slice, x_slice = key
        
        if(isinstance(band_key, slice) and (band_key.start is not None or band_key.stop is not None or band_key.step is not None)):
            raise TypeError("Invalid key format. Use ('band_name', y, x) or (:, y_slice, x_slice).")
        elif(isinstance(band_key, slice)):
            band_names = self.band_names
        elif(isinstance(band_key, int) or isinstance(band_key, str)):
            band_names = [band_key]
        else:
            band_names = list(band_key)
        
        if(not(np.all(np.isin(band_names, self.band_names)))):
            bad_names= band_names[np.flatnonzero(~np.isin(band_names, self.band_names))]
            raise KeyError(f"Bands {bad_names} not found.")
        
        if(isinstance(y_slice,int)):
            y_slice = slice(y_slice, y_slice+1, 1)
        if(isinstance(x_slice,int)):
            x_slice = slice(x_slice, x_slice+1, 1)
        
        new_band_arrays = {name: self.bands[name][y_slice, x_slice] for name in band_names}
        
        # Compute new geometries
        y_indices, x_indices = np.mgrid[0:self.height, 0:self.width]
        y_indices = y_indices[y_slice,x_slice]
        x_indices = x_indices[y_slice,x_slice]
        flat_indices = (y_indices * self.width + x_indices).flatten()
        new_geometries = [self.geometries[i] for i in flat_indices]
        
        return self._create_new_instance(new_band_arrays, new_geometries, crs=self.crs)
    
    def __setitem__(self, key, value):
        """
        Set values in the array while keeping geometries unchanged.
        
        Supports:
        - poly_array["band_name", y, x] = value
        - poly_array["band_name", y_slice, x_slice] = value
        """
        if(not(isinstance(key, tuple))):
            raise TypeError("Invalid key format. Use ('band_name', y, x) or (:, y_slice, x_slice).")
        
        band_key, y_slice, x_slice = key
        
        if(not(isinstance(band_key, (int,str)))):
            raise KeyError("Only a single band name can be given as argument.")
        elif(not(band_key in self.band_names)):
            raise KeyError("Band name not found.")

        self.bands[band_key][y_slice, x_slice] = value
    
    def __repr__(self):
        """
        String representation of the PolyArray object.
        """
        return f"PolyArray(bands={self.band_names}, shape=({self.height}, {self.width}), num_geometries={len(self.geometries)})"
    
    def add_band(self, bands, band_arrays=None, dtype=None, replace = True, inplace = False):

        if(dtype is None and band_arrays is not None):
            dtype = band_arrays.dtype
        elif(dtype is None and band_arrays is None):
            dtype = np.float64
    
        if(isinstance(bands, dict)):
            band_names = list(bands.keys())
        else:
            if(isinstance(bands, (str, int))):
                band_names = [bands]
                
                if(band_arrays is not None and (band_arrays.ndim!=2 or band_arrays.shape[0]!=self.height or band_arrays.shape[1]!=self.width)):
                    raise ValueError(f"Expected a 2D NumPy array with dimensions ({self.height},{self.width}).")
                elif(band_arrays is not None):
                    bands = {bands: band_arrays.astype(dtype)}
                else:
                    bands = {bands: np.zeros((self.height, self.width), dtype=dtype)}
            else:
                band_names = bands

                if(band_arrays is not None and (band_arrays.ndim!= 3 or band_arrays.shape[0]!=len(band_names) or band_arrays.shape[1]!=self.height or band_arrays.shape[2]!=self.width)):
                    raise ValueError(f"Expected 3D NumPy array with dimensions ({len(band_names)},{self.height},{self.width})")
        
                bands = dict()
                for i in range(0,len(band_names)):
                    if(band_arrays is None):
                        bands[band_names[i]] = np.zeros((self.height, self.width), dtype=dtype)
                    else:
                        bands[band_names[i]] = band_arrays[i,:,:].astype(dtype)
                    
        if(replace):
            new_bands = {**self.bands, **bands}
        else:
            bands_isin = np.flatnonzero(np.isin(band_names, self.band_names))
            if(len(bands_isin)>0):
                raise ValueError(f"The following bands already exist: {[band_names[band_index] for band_index in bands_isin]}")
        
        if(inplace):
            self.bands = new_bands
            self.band_names = list(new_bands.keys())
            return
        else:
            return self._create_new_instance(new_bands, self.geometries, crs=self.crs) 
    
    def to_gpkg(self, outfile, layer_name = 'pixelpolys', dissolve_by = None, simplify_tolerance = None, null_values=[]):
    
        if(os.path.splitext(outfile)[1]!='.gpkg'):
            raise ValueError("The outfile should have a .gpkg extension.")

        driver = ogr.GetDriverByName("GPKG")
        driver.DeleteDataSource(outfile)
        ds = driver.CreateDataSource(outfile)
        
        srs = osr.SpatialReference()
        srs.ImportFromWkt(self.crs)
        
        band_dict = {band_name: self.bands[band_name].flatten() for band_name in self.band_names}
        
        df = pd.DataFrame(band_dict)
        df['geometry'] = self.geometries
        df['ax0'] = np.repeat(np.arange(self.height, dtype=int), self.width) 
        df['ax1'] = np.tile(np.arange(self.width, dtype=int), self.height)
        
        if(isinstance(null_values, dict)):
            null_keys = np.array(list(null_values.keys()))
            null_keys = null_keys[np.isin(null_keys, self.band_names)]
            
            bool_keep = np.ones(len(df), dtype=bool)
            
            for key in null_keys:
                null_value = null_values[key]
                try:
                    len_null_value = len(null_value)
                except:
                    null_value = [null_value]
                
                bool_keep = bool_keep & ~np.isin(df[key].values, null_value)
                
        else:
            bool_keep = np.zeros(len(df), dtype=bool)
            
            try:
                len_null_values = len(null_values)
            except:
                null_values = [null_values]
            
            for band in self.band_names:
                bool_keep = bool_keep | ~np.isin(df[band].values, null_values) 
        
        df = df.loc[bool_keep, :]
        
        if(len(df)==0):
            return False
        
        dissolve = np.isin(dissolve_by, self.band_names)
        
        layer = ds.CreateLayer(layer_name, srs, ogr.wkbPolygon)
        
        field_conversion = {}
        
        for band_name in self.band_names:
        
            if(np.issubdtype(df[band_name].dtype, np.integer)):
                field_type = ogr.OFTInteger 
                field_conversion[band_name] = int
            else:
                field_type = ogr.OFTReal
                field_conversion[band_name] = float
            layer.CreateField(ogr.FieldDefn(band_name, field_type))
        
        if(dissolve):
        
            unique_values, unique_indices = np.unique(df[dissolve_by], return_index=True)
            
            df_dissolve = df.drop(['ax0', 'ax1'], axis=1).iloc[unique_indices, :]
            
            dissolve_geometries = []
            
            for i, unique_value in enumerate(unique_values):
            
                dissolve_geometry = shapely.unary_union(df.loc[df[dissolve_by]==unique_value, 'geometry'].values)
                dissolve_geometries.append(dissolve_geometry)
                
            df_dissolve['geometry'] = dissolve_geometries
            
            df = df_dissolve
            
        else:
        
            layer.CreateField(ogr.FieldDefn('ax0', ogr.OFTInteger))
            layer.CreateField(ogr.FieldDefn('ax1', ogr.OFTInteger))
            
        if(simplify_tolerance is not None):
        
            df['geometry'] = [shapely.simplify(df['geometry'].iloc[i], simplify_tolerance) for i in range(0,len(df))]
            
        wkb_geometries = shapely.to_wkb(df['geometry'].values)
        df = df.drop('geometry', axis=1)
            
        for i in range(0,len(df)):
        
            feature = ogr.Feature(layer.GetLayerDefn())
            ogr_geometry = ogr.CreateGeometryFromWkb(wkb_geometries[i])
            
            feature.SetGeometry(ogr_geometry)
            
            J = 0
            for band_name in self.band_names:
            
                feature.SetField(J, field_conversion[band_name]((df[band_name].iloc[i])))
                J+=1
                
            if(not(dissolve)):
                feature.SetField(J, int(df['ax0'].iloc[i]))
                feature.SetField(J+1, int(df['ax1'].iloc[i]))
            
            layer.CreateFeature(feature)
            del feature
            
        del df
        del wkb_geometries
        ds = None
        gc.collect()

        return True

    def to_numpy(self):
    
        arr = np.stack(list(self.bands.values()))
        return arr

class PolyImage(PolyArray):

    def __init__(self, band_arrays, transform, crs, metadata = {}, band_names = None):

        if(isinstance(band_arrays, dict)):
            band_names0 = list(band_arrays.keys())
            band_array = band_arrays[band_names0[0]]
            shape = band_array.shape
            dtype = band_array.dtype
            assert len(shape)==2
            for i in range(1,len(band_names0)):
                band_array = band_arrays[band_names0[i]]
                assert band_array.shape==shape
                assert band_array.dtype==dtype
            band_count = len(band_arrays)
        else:
            assert len(band_arrays.shape)==3
            shape = (band_arrays.shape[1], band_arrays.shape[2])
            dtype = band_arrays.dtype
            band_count = band_arrays.shape[0]
        
        resolution = (transform[1], transform[5])
        
        geometries, frame = pixelsToPolys(transform, shape, return_frame=True)

        super(PolyImage, self).__init__(band_arrays, geometries, band_names = band_names, crs=crs)
        
        self.transform = transform
        self.metadata = metadata
        self.dtype = dtype
        self.frame = frame
    
    def __repr__(self):
        """
        String representation of the PolyImage object.
        """
        return f"PolyImage(bands={self.band_names}, shape=({self.height}, {self.width}), num_geometries={len(self.geometries)})"
    
    def _create_new_instance(self, band_arrays, geometries, crs=None):
    
        new_image = object.__new__(self.__class__)
        super(PolyImage, new_image).__init__(band_arrays, geometries, band_names = None, crs=crs)
        
        new_shape = band_arrays[list(band_arrays.keys())[0]].shape
        
        top_left_x, top_left_y = top_left_poly.exterior.coords.xy
        transform = (top_left_x[0], self.transform[1], self.transform[2], top_left_y[0], self.transform[4], self.transform[5])
        
        transformer = AffineTransformer(transform)
        
        frame_x, frame_y = transformer.xy(np.array([0, new_shape[1]+1, new_shape[1]+1, 0, 0]), np.array([0, 0, new_shape[0]+1, new_shape[0]+1, 0]))
        
        new_frame = shapely.Polygon(np.hstack([frame_x[:,np.newaxis], frame_y[:,np.newaxis]]))        

        new_image.transform = transform
        new_image.metadata = self.metadata
        new_image.dtype = self.dtype
        new_image.frame = new_frame
        
        return new_image

    def add_band(self, bands, band_arrays=None, replace = True, inplace = False):

        dtype = self.dtype

        return super(PolyImage, self).add_band(bands, band_arrays=band_arrays, dtype=dtype, replace=replace, inplace=inplace)
    
    def __getitem__(self, key):
    
        if isinstance(key, tuple):
            band_key, y_slice, x_slice = key
        
            if((not(isinstance(y_slice, int)) and not(isinstance(y_slice, slice))) or (not(isinstance(x_slice, int)) and not(isinstance(x_slice, slice)))):
                raise IndexError("Only integers or slices are acceptable as y and x indices.")
            elif((isinstance(y_slice, slice) and y_slice.step!=1 and y_slice.step is not None) or (isinstance(x_slice, slice) and x_slice.step!=1 and x_slice.step is not None)):
                raise IndexError(f"Slices must have step 1 or None, but these have step {y_slice.step},{x_slice.step}.")
            
            return super(PolyImage, self).__getitem__(key)
        
        else:
            raise TypeError("Invalid key format. Use ('band_name', y, x) or (:, y_slice, x_slice).")
    
    def to_tiff(self, outfile):
    
        generateTiff(outfile, self.bands, self.transform, (self.height, self.width), self.crs, metadata = self.metadata)
