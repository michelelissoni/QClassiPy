"""
Filename: polyimage.py
Author: Michele Lissoni
Date: 2026-02-10
"""

"""

PolyArray class, which acts as a bridge between a raster
and its representation in vector format, where each pixel becomes a polygon.
The changes to the polygon representation are sent to the PolyArray, which then
translates them back into a raster.

PolyImage is a child class of PolyArray, ensures that the pixel polygons trace the pixel boundaries.

"""

import os
import gc

import numpy as np
import pandas as pd

import shapely
from osgeo import osr, ogr, gdal

from .gdal_tools import generateTiff, AffineTransformer

def pixelsToPolys(transform, shape, return_frame=False):

    """
    Generate the polygons corresponding to a raster's pixels.
    
    Arguments:
    - transform (tuple): the raster geotransform.
    - shape (tuple): the raster 2D shape.
    
    Keywords:
    - return_frame (bool): if True, a frame polygon delimiting the raster's bounds is also returned.
    
    Returns: 
    - geom_list: the list of pixel polygons, row-wise (C order)
    - frame: the raster frame polygon, if `return_frame` is True
    """

    assert len(transform) == 6
    assert len(shape) == 2
    assert np.issubdtype(type(shape[0]), np.integer) and np.issubdtype(type(shape[1]), np.integer)
    
    # Compute the polygon geometries

    if transform[2] == 0 and transform[4] == 0 :
    
        # A more efficient computation if the raster is aligned with the coordinate axes
    
        # Compute the pixel corners
        
        x_bounds = np.linspace(transform[0], transform[0]+transform[1]*shape[1], shape[1]+1)
        y_bounds = np.linspace(transform[3], transform[3]+transform[5]*shape[0], shape[0]+1)

        geom_list = []
        
        # Iteration over the pixels to generate the polygons
        
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
                
        # Generate the frame
                
        frame = shapely.Polygon([
        [x_bounds[0], y_bounds[0]],
        [x_bounds[-1], y_bounds[0]],
        [x_bounds[-1], y_bounds[-1]],
        [x_bounds[0], y_bounds[-1]],
        [x_bounds[0], y_bounds[0]]
        ])
        
    else:

        # Computation if the raster is not aligned with the coordinate axes.

        # Compute the pixel corners

        transformer = AffineTransformer(transform)
        
        px_corners = np.reshape(np.mgrid[0:shape[0]+1, 0:shape[1]+1], (2, (shape[0]+1)*(shape[1]+1)))
        
        poly_x, poly_y = transformer.xy(px_corners[1,:], px_corners[0,:])
        
        del px_corners
        
        geom_list = []
        
        # Iteration over the pixels to generate the polygons
        
        for i in range(0, shape[0]):
            for j in range(0, shape[1]):
            
                poly = shapely.Polygon([[poly_x[i*(shape[1]+1)+j], poly_y[i*(shape[1]+1)+j]],
                                        [poly_x[i*(shape[1]+1)+(j+1)], poly_y[i*(shape[1]+1)+(j+1)]],
                                        [poly_x[(i+1)*(shape[1]+1)+(j+1)], poly_y[(i+1)*(shape[1]+1)+(j+1)]],
                                        [poly_x[(i+1)*(shape[1]+1)+j], poly_y[(i+1)*(shape[1]+1)+j]],
                                        [poly_x[i*(shape[1]+1)+j], poly_y[i*(shape[1]+1)+j]]])

                geom_list.append(poly)

        # Generate the frame
                
        frame = shapely.Polygon([
                                 [poly_x[0], poly_y[0]],
                                 [poly_x[shape[1]], poly_y[shape[1]]],
                                 [poly_x[-1], poly_y[-1]],
                                 [poly_x[shape[0]*(shape[1]+1)], poly_y[shape[0]*(shape[1]+1)]],
                                 [poly_x[0], poly_y[0]]
                                ])
                                
        del poly_x, poly_y
        gc.collect()
    
    if return_frame :
        return geom_list, frame
    else:
        return geom_list

class PolyArray:

    """
    Parent class of PolyImage, associates the cells of a multi-band raster 
    with geometries.
    """

    def __init__(self, band_arrays, geometries, band_names=None, crs=None):
        """
        Initialize a PolyArray object.
        
        Arguments:
        - band_arrays (dict or np.array): either a dictionary mapping band names to 2D NumPy arrays (y, x) of identical shape,
                                          or a 3D NumPy array, where axis 0 contains the bands,
                                          axis 1 is the y-axis and axis 2 the x-axis.
        - geometries (list or np.array): a sequence of Shapely geometries of length (y * x), corresponding to (y, x) indices.
        
        Keywords:
        - band_names (list or np.array): a sequence of string band names, to be provided if `band_arrays` is a 3D array. 
                                         If not provided, the band indices are used.
        - crs:  raster coordinate system, in WKT format. 
        """
        
        # Check parameters and assign attributes
        # The data are stored in the self.bands attribute,
        # a dictionary mapping band names to 2D NumPy arrays.
        
        value_err_message = "`band_arrays` must be either a dictionary mapping band names to 2D NumPy arrays or a 3D NumPy array with the first dimension being the bands."
        
        if isinstance(band_arrays, np.ndarray ):
            if band_arrays.ndim != 3 :
                raise ValueError(value_err_message)

            if not(np.issubdtype(band_arrays.dtype, np.floating) or np.issubdtype(band_arrays.dtype, np.integer)):
                raise TypeError("Only numeric dtypes (int, float) are acceptable.")
        
            if band_names is None :
                band_names = np.arange(band_arrays.shape[0],dtype=int).astype(str) # Default band names
                
            elif len(band_names) != band_arrays.shape[0] :
                raise ValueError("The band names must have the same length as the 3D array's first dimension.")
            
            band_dict = dict()
            for i in range(0, len(band_names)):
                band_dict[band_names[i]] = band_arrays[i,:,:]
                
            # Storing the data in attributes
        
            self.bands = band_dict # The data
            self.band_names = band_names # The band names
            self.height, self.width = band_arrays.shape[1], band_arrays.shape[2] # The raster shape
        
        elif isinstance(band_arrays,dict) :
            if not all(isinstance(v, np.ndarray) and v.ndim == 2 for v in band_arrays.values()) :
                raise ValueError(value_err_message)
        
            first_arr = next(iter(band_arrays.values()))
            first_shape = first_arr.shape
            first_dtype = first_arr.dtype
            if not all(v.shape == first_shape for v in band_arrays.values()) :
                raise ValueError("All bands must have the same (y, x) shape.")    

            if not(np.issubdtype(first_dtype, np.floating) or np.issubdtype(first_dtype, np.integer)) :
                raise TypeError("Only numeric dtypes (int, float) are acceptable.")
                
            # Storing the data in attributes
     
            self.bands = band_arrays # The data
            self.band_names = list(band_arrays.keys()) # The band names
            self.height, self.width = first_shape # The raster shape
                
        else:
            raise ValueError(value_err_message)
        
        if len(geometries) != self.height * self.width :
            raise ValueError("Geometries list must have length equal to y * x.")
        
        self.geometries = geometries

        self.crs = crs
    
    def _create_new_instance(self, band_arrays, geometries, band_names=None, crs=None):
        """
        Create new instance of PolyArray (same parameters as __init__())
        """
        return self.__class__(band_arrays, geometries, band_names=band_names, crs=crs)
    
    def __getitem__(self, key):
        """
        Retrieve a portion of the array, along with corresponding geometries.
        
        Supports:
        - poly_array["band_name", y, x]
        - poly_array["band_name", y_slice, x_slice]
        - poly_array[:, y_slice, x_slice] (returns a new PolyArray with selected bands)
        """

        if not isinstance(key, tuple):
            raise TypeError("Invalid key format. Use ('band_name', y, x) or (:, y_slice, x_slice).")
        
        band_key, y_slice, x_slice = key
        
        if isinstance(band_key, slice) and (band_key.start is not None or band_key.stop is not None or band_key.step is not None) :
            raise TypeError("Invalid key format. Use ('band_name', y, x) or (:, y_slice, x_slice).")
        elif isinstance(band_key, slice) :
            band_names = self.band_names
        elif isinstance(band_key, int) or isinstance(band_key, str) :
            band_names = [band_key]
        else:
            band_names = list(band_key)
        
        if not np.all(np.isin(band_names, self.band_names)) :
            bad_names= band_names[np.flatnonzero(~np.isin(band_names, self.band_names))]
            raise KeyError(f"Bands {bad_names} not found.")
        
        if isinstance(y_slice,int) :
            y_slice = slice(y_slice, y_slice+1, 1)
        if isinstance(x_slice,int) :
            x_slice = slice(x_slice, x_slice+1, 1)
        
        # New band_arrays dictionary        
        new_band_arrays = {name: self.bands[name][y_slice, x_slice] for name in band_names}
        
        # Retrieve new geometries
        y_indices, x_indices = np.mgrid[0:self.height, 0:self.width]
        y_indices = y_indices[y_slice,x_slice]
        x_indices = x_indices[y_slice,x_slice]
        flat_indices = (y_indices * self.width + x_indices).flatten()
        new_geometries = [self.geometries[i] for i in flat_indices]
        
        # Create new instance of PolyArray
        return self._create_new_instance(new_band_arrays, new_geometries, crs=self.crs)
    
    def __setitem__(self, key, value):
        """
        Set values in the array while keeping geometries unchanged.
        
        Supports:
        - poly_array["band_name", y, x] = value
        - poly_array["band_name", y_slice, x_slice] = value
        """
        
        if not isinstance(key, tuple):
            raise TypeError("Invalid key format. Use ('band_name', y, x) or (:, y_slice, x_slice).")
        
        band_key, y_slice, x_slice = key
        
        if not isinstance(band_key, (int,str)) :
            raise KeyError("Only a single band name can be given as argument.")
        elif not band_key in self.band_names :
            raise KeyError("Band name not found.")

        self.bands[band_key][y_slice, x_slice] = value
    
    def __repr__(self):
        """
        String representation of the PolyArray object.
        """
        return f"PolyArray(bands={self.band_names}, shape=({self.height}, {self.width}), num_geometries={len(self.geometries)})"
    
    def add_band(self, bands, band_arrays=None, dtype=None, replace = True, inplace = False):
        """
        Add band to the PolyArray.
        
        Arguments:
        - bands (dict|list|np.array|str|int): either a dictionary mapping band names to 2D NumPy arrays (y, x) of identical shape,
                                              or, to create empty bands set to 0 everywhere, a sequence of band names, 
                                              or a single scalar band name (int or str).

        Keywords:
        - band_arrays (np.array) : if `bands` is a sequence, a 3D NumPy array with axis 0 of same length. If it is a scalar, a 2D array.
                                   By default, an array containing zeros is generated.
        - dtype : dtype of the new bands. Default: float64.
        - replace (bool): if True, bands with the same names as those provided are replaced. Raises an error otherwise.
        - inplace (bool): if True, operation is performed inplace.
        
        Returns:
        - if `inplace` is False, a new PolyArray object with the new bands added. 
        """

        if dtype is None and band_arrays is not None :
            dtype = band_arrays.dtype
        elif dtype is None and band_arrays is None :
            dtype = np.float64
    
        if isinstance(bands, dict) :
            band_names = list(bands.keys())
        else:
            # If bands is not a dict, create a dict from band_names and band_arrays
        
            if isinstance(bands, (str, int)) :
                band_names = [bands]
                
                if band_arrays is not None and (band_arrays.ndim != 2 or band_arrays.shape[0] != self.height or band_arrays.shape[1] != self.width) :
                    raise ValueError(f"Expected a 2D NumPy array with dimensions ({self.height},{self.width}).")
                elif band_arrays is not None :
                    bands = {bands: band_arrays.astype(dtype)}
                else:
                    bands = {bands: np.zeros((self.height, self.width), dtype=dtype)}
            else:
                band_names = bands

                if band_arrays is not None and (band_arrays.ndim != 3 or band_arrays.shape[0] != len(band_names) or band_arrays.shape[1] != self.height or band_arrays.shape[2] != self.width) :
                    raise ValueError(f"Expected 3D NumPy array with dimensions ({len(band_names)},{self.height},{self.width})")
        
                bands = dict()
                for i in range(0,len(band_names)):
                    if band_arrays is None :
                        bands[band_names[i]] = np.zeros((self.height, self.width), dtype=dtype)
                    else:
                        bands[band_names[i]] = band_arrays[i,:,:].astype(dtype)
        
        # Replace existing bands
        if replace :
            new_bands = {**self.bands, **bands}
        else:
            bands_isin = np.flatnonzero(np.isin(band_names, self.band_names))
            if len(bands_isin)>0 :
                raise ValueError(f"The following bands already exist: {[band_names[band_index] for band_index in bands_isin]}")
        
        
        if inplace :
            self.bands = new_bands
            self.band_names = list(new_bands.keys())
            return
        else:
            return self._create_new_instance(new_bands, self.geometries, crs=self.crs) 
    
    def to_gpkg(self, outfile, layer_name = 'pixelpolys', dissolve_by = None, keep_only_dissolve_band = True, simplify_tolerance = None, null_values=[]):
        """
        Save a GeoPackage file containing the raster's polygon representation, 
        with the band values stored in the attribute table row of each pixel polygon.
        
        Arguments:
        - outfile (str): the GeoPackage file name.
        
        Keywords:
        - layer_name (str) : the vector layer name in the GeoPackage.
        - dissolve_by (str): if set to a band name, the contiguous polygons with equal value in that band are merged.
        - keep_only_dissolve_band (bool): if True and dissolve_by is set to a band name, only that band will be kept 
                                          in the attribute table of the vector layer.
        - simplify_tolerance (float): if set, the polygons are simplified. The higher this value, the smaller the number of vertices. 
        - null_values (dict or sequence or scalar): set to a sequence or scalar, pixels containing the stored values in all bands are 
                                                    not converted to polygons. Can also be set to a dictionary, mapping the null values 
                                                    of each band to the band names. In this case, a pixel containing a null value in the 
                                                    corresponding bands is not converted to a polygon. If `dissolve_by` is set to a band 
                                                    name and `keep_only_dissolve_band` is True, only the values in the dissolve band are filtered.
                                                    
        Returns:
        - feature_count: the number of polygons created. 
        """
    
        if os.path.splitext(outfile)[1] != '.gpkg' :
            raise ValueError("The outfile should have a .gpkg extension.")

        driver = ogr.GetDriverByName("GPKG")
        driver.DeleteDataSource(outfile)
        ds = driver.CreateDataSource(outfile)
        
        srs = osr.SpatialReference()
        crs = self.crs if self.crs is not None else ""
        srs.ImportFromWkt(crs)
        
        band_names = self.band_names
        
        band_dict = {band_name: self.bands[band_name].flatten() for band_name in band_names}
        
        # Store the band values into a dataframe, each row corresponds to a pixel
        
        df = pd.DataFrame(band_dict)
        df['geometry'] = self.geometries # Geometries
        df['ax0'] = np.repeat(np.arange(self.height, dtype=int), self.width) # y-axis coordinate
        df['ax1'] = np.tile(np.arange(self.width, dtype=int), self.height) # x-axis coordinate
        
        # Filter the null values
        
        if isinstance(null_values, dict) :
        
            if dissolve_by is not None and keep_only_dissolve_band :
                null_values = {dissolve_by: null_values[dissolve_by]} if dissolve_by in null_values else dict()
        
            null_keys = np.array(list(null_values.keys()))
            null_keys = null_keys[np.isin(null_keys, band_names)]
            
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
            
            for band in band_names:
                bool_keep = bool_keep | ~np.isin(df[band].values, null_values)
        
        dissolve = np.isin(dissolve_by, band_names)
        
        if dissolve and keep_only_dissolve_band:
            band_names = [dissolve_by]
        
        # Create vector layer, define fields.
        
        layer = ds.CreateLayer(layer_name, srs, ogr.wkbPolygon)
        
        field_conversion = {}
        
        for band_name in band_names:
        
            if np.issubdtype(df[band_name].dtype, np.integer) :
                field_type = ogr.OFTInteger 
                field_conversion[band_name] = int
            else:
                field_type = ogr.OFTReal
                field_conversion[band_name] = float
            layer.CreateField(ogr.FieldDefn(band_name, field_type))
            
        df = df.loc[bool_keep, :]
        
        if len(df) == 0 :
            return 0
        
        # Dissolve geometries if `dissolve_by` was set to a band name
        
        if dissolve :
        
            unique_values, unique_indices = np.unique(df[dissolve_by], return_index=True)
            
            dissolve_geometries = []
            df_indices = np.zeros(0, dtype=int)
            
            # Dissolve geometries for each unique value
            
            for i, unique_value in enumerate(unique_values):
            
                dissolve_geometry = shapely.unary_union(df.loc[df[dissolve_by]==unique_value, 'geometry'].values)
                if isinstance(dissolve_geometry, shapely.geometry.multipolygon.MultiPolygon) :
                    
                    # Split non-contiguous polygons with the same value
                    dissolve_geometry = list(dissolve_geometry.geoms)
                    
                else:
                    dissolve_geometry = [dissolve_geometry]
                dissolve_geometries = dissolve_geometries + dissolve_geometry
                df_indices = np.append(df_indices, np.repeat(unique_indices[i], len(dissolve_geometry)))
                
            df_dissolve = df.drop(['ax0', 'ax1'], axis=1).iloc[df_indices, :]
            
            if keep_only_dissolve_band:
                df_dissolve = df_dissolve.loc[:, [dissolve_by]]
            
            df_dissolve['geometry'] = dissolve_geometries
            
            df = df_dissolve
            
        else:
        
            layer.CreateField(ogr.FieldDefn('ax0', ogr.OFTInteger))
            layer.CreateField(ogr.FieldDefn('ax1', ogr.OFTInteger))
            
        # Simplify geometries
            
        if simplify_tolerance is not None :
        
            df['geometry'] = [shapely.simplify(df['geometry'].iloc[i], simplify_tolerance) for i in range(0,len(df))]
            
        df['wkb_geom'] = shapely.to_wkb(df['geometry'].values)
        df = df.drop('geometry', axis=1)
        
        # Write geometries to layer
        
        layer.StartTransaction()
            
        for _, row in df.iterrows():
        
            feature = ogr.Feature(layer.GetLayerDefn())
            ogr_geometry = ogr.CreateGeometryFromWkb(row.loc['wkb_geom'])
            
            feature.SetGeometry(ogr_geometry)
            
            J = 0
            for band_name in band_names:
            
                feature.SetField(J, field_conversion[band_name]((row.loc[band_name])))
                J+=1
                
            if not dissolve :
                feature.SetField(J, int(row.loc['ax0']))
                feature.SetField(J+1, int(row.loc['ax1']))
            
            layer.CreateFeature(feature)
            feature = None
            
        layer.CommitTransaction()
        
        feature_count = len(df)
       
        del df
        ds = None
        gc.collect()

        return feature_count

    def to_numpy(self):
        """
        Convert the bands to a single 3D NumPy array.
        """
        arr = np.stack(list(self.bands.values()))
        return arr

class PolyImage(PolyArray):

    """
    The PolyImage class creates a PolyArray where the geometries are pixel boundaries obtained from a raster transform.
    """

    def __init__(self, band_arrays, transform, crs, metadata = {}, band_names = None):
        """
        Initialize a PolyImage object.
        
        Arguments:
        - band_arrays (dict or np.array): either a dictionary mapping band names to 2D NumPy arrays (y, x) of identical shape,
                                          or a 3D NumPy array, where axis 0 contains the bands,
                                          axis 1 is the y-axis and axis 2 the x-axis.
        - transform (tuple): raster transform, the geometries will be generated from this.
        - crs (str): the raster coordinate system, in WKT format.
        
        Keywords:
        - metadata (dict): metadata to be stored in PolyImage, typically coming from the original raster.
        - band_names (list | np.array): sequence of band names, if `band_arrays` is an array. 
        """

        if isinstance(band_arrays, dict) :
            band_names0 = list(band_arrays.keys())
            band_array = band_arrays[band_names0[0]]
            shape = band_array.shape
            dtype = band_array.dtype
            assert len(shape) == 2
            for i in range(1,len(band_names0)):
                band_array = band_arrays[band_names0[i]]
                assert band_array.shape == shape
                assert band_array.dtype == dtype # Unlike in PolyArray, all bands here must have the same data type
            band_count = len(band_arrays)
        else:
            assert len(band_arrays.shape) == 3
            shape = (band_arrays.shape[1], band_arrays.shape[2])
            dtype = band_arrays.dtype
            band_count = band_arrays.shape[0]
        
        resolution = (transform[1], transform[5])
        
        # Transform pixels into polygons
        geometries, frame = pixelsToPolys(transform, shape, return_frame=True)

        # Initialize PolyArray
        super(PolyImage, self).__init__(band_arrays, geometries, band_names = band_names, crs=crs)
        
        self.transform = transform
        self.metadata = metadata
        self.dtype = dtype
        self.frame = frame # Polygon tracing the boundaries of the raster
    
    def __repr__(self):
        """
        String representation of the PolyImage object.
        """
        return f"PolyImage(bands={self.band_names}, shape=({self.height}, {self.width}), num_geometries={len(self.geometries)})"
    
    def _create_new_instance(self, band_arrays, geometries, crs=None):
        """
        Create new instance of PolyImage (overloads equivalent method in PolyArray)
        """    
        new_image = object.__new__(self.__class__)
        
        # Create new PolyArray
        super(PolyImage, new_image).__init__(band_arrays, geometries, band_names = None, crs=crs)
        
        new_shape = band_arrays[list(band_arrays.keys())[0]].shape
        
        # Compute transform of new PolyImage
        
        top_left_x, top_left_y = top_left_poly.exterior.coords.xy
        transform = (top_left_x[0], self.transform[1], self.transform[2], top_left_y[0], self.transform[4], self.transform[5])
        
        transformer = AffineTransformer(transform)
        
        # Create frame of new PolyImage
        
        frame_x, frame_y = transformer.xy(np.array([0, new_shape[1]+1, new_shape[1]+1, 0, 0]), np.array([0, 0, new_shape[0]+1, new_shape[0]+1, 0]))
        
        new_frame = shapely.Polygon(np.hstack([frame_x[:,np.newaxis], frame_y[:,np.newaxis]]))        

        new_image.transform = transform
        new_image.metadata = self.metadata
        new_image.dtype = self.dtype
        new_image.frame = new_frame
        
        return new_image

    def add_band(self, bands, band_arrays=None, replace = True, inplace = False):
        """
        Add new band to PolyImage (overloads equivalent method in PolyArray, ensures dtype is the same)
        """   
        dtype = self.dtype

        return super(PolyImage, self).add_band(bands, band_arrays=band_arrays, dtype=dtype, replace=replace, inplace=inplace)
    
    def __getitem__(self, key):
        """
        Retrieve a portion of the image (overloads equivalent method in PolyArray, checks that slice step is 1)
        """ 
        if isinstance(key, tuple):
            band_key, y_slice, x_slice = key
        
            if (not isinstance(y_slice, int)  and not isinstance(y_slice, slice)) or (not isinstance(x_slice, int) and not isinstance(x_slice, slice)):
                raise IndexError("Only integers or slices are acceptable as y and x indices.")
            elif (isinstance(y_slice, slice) and y_slice.step!=1 and y_slice.step is not None) or (isinstance(x_slice, slice) and x_slice.step!=1 and x_slice.step is not None) :
                raise IndexError(f"Slices must have step 1 or None, but these have step {y_slice.step},{x_slice.step}.")
            
            return super(PolyImage, self).__getitem__(key)
        
        else:
            raise TypeError("Invalid key format. Use ('band_name', y, x) or (:, y_slice, x_slice).")
    
    def to_tiff(self, outfile):
        """
        Convert PolyImage to TIFF file.
        """
        generateTiff(outfile, self.bands, self.transform, (self.height, self.width), self.crs, metadata = self.metadata)
