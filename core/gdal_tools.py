import os
import numpy as np
from osgeo import gdal, ogr, osr
from packaging.version import Version

gdal_version = Version(gdal.__version__)

gdal_uints = {1: gdal.GDT_Byte,
             2: gdal.GDT_UInt16,
             4: gdal.GDT_UInt32}             
if gdal_version >= Version('3.5') :
    gdal_uints[8] = gdal.GDT_UInt64

gdal_ints = {2: gdal.GDT_Int16,
             4: gdal.GDT_Int32}
if gdal_version >= Version('3.5') :
    gdal_ints[8] = gdal.GDT_Int64
if gdal_version >= Version('3.7') :
    gdal_ints[1] = gdal.GDT_Int8

gdal_floats = {4: gdal.GDT_Float32,
               8: gdal.GDT_Float64}
if gdal_version>=Version('3.11') :
    gdal_ints[2] = gdal.GDT_Float16    

def generateTiff(outfile, band_dict, transform, shape, crs, metadata = None):

    out_ext = os.path.splitext(outfile)[1]
    if out_ext != '.tif' and out_ext != '.tiff' :
        raise ValueError("The outfile should have a .tif or .tiff extension.")
        
    band_names = list(band_dict.keys())
    dtype = band_dict[band_names[0]].dtype
       
    I=1
    while(I<len(band_names)):
        if band_dict[band_names[I]].dtype != dtype :
            raise ValueError("All arrays in `band_dict` should have the same dtype.")  
        I+=1 

    if np.issubdtype(dtype, np.unsignedinteger) :
        type_dict = gdal_uints
    elif np.issubdtype(dtype, np.signedinteger) :
        type_dict = gdal_ints
    elif np.issubdtype(dtype, np.floating) :
        type_dict = gdal_floats
    else:
        raise RuntimeError(f"The dtype should be a recognized Int, UInt or Float, not {dtype}.")
        
    type_sizes = np.sort(np.array(list(type_dict.keys()), dtype=int))
    dtype_size = np.array([1], dtype=dtype).itemsize
    gdal_dtype = type_dict[type_sizes[min(np.searchsorted(type_sizes, dtype_size), len(type_sizes)-1)]]
    
    height, width = shape
    
    driver = gdal.GetDriverByName("GTiff")
    ds = driver.Create(
        outfile,
        width,
        height,
        len(band_names),
        gdal_dtype,
        options=["COMPRESS=LZW"]
    )                
    
    ds.SetGeoTransform(transform)
    ds.SetProjection(crs)
    
    for i, band_name in enumerate(band_names):
        band = ds.GetRasterBand(i+1)
        band.WriteArray(band_dict[band_name])
        band.SetDescription(band_name)
    
    if metadata is not None :
        ds.SetMetadata(metadata)
    
    ds.FlushCache()
    
    ds = None
    
def rasterizeLayer(
    vector_path,           # QgsVectorLayer
    attribute,            # attribute name to burn
    out_shape,            # (height, width)
    transform,
    crs, 
    layer_name = None,  # GDAL geotransform
    nodata = 0,
    tmp_output_path = "temporary_raster.tif",
    priority = None,
    dtype = np.uint8
):
    height, width = out_shape
    x0, px_w, rot_x, y0, rot_y, px_h = transform

    # Compute extent string (QGIS expects xmin,xmax,ymin,ymax)
    xmin = x0
    xmax = x0 + px_w * width
    ymax = y0
    ymin = y0 + px_h * height   # px_h is negative for north-up rasters

    extent_str = f"{xmin},{xmax},{ymin},{ymax}"
    
    drv = gdal.GetDriverByName("GTiff")   
    
    out_ds = drv.Create(tmp_output_path, width, height, 1, gdal.GDT_Float32)
    out_ds.SetGeoTransform(transform)
    out_ds.SetProjection(crs)
    
    band = out_ds.GetRasterBand(1)
    band.Fill(float(nodata))
    band.SetNoDataValue(float(nodata))

    if priority is not None:
        priority_field = priority[0]
        priority_values = priority[1]
    else:
        priority_field = ''
        priority_values = []
    
    vds = ogr.Open(vector_path)
    vl = vds.GetLayer(layer_name)
    
    priority_values_sql = '('+', '.join([str(priority_value) for priority_value in priority_values])+')'
    
    vl.SetAttributeFilter(f"{priority_field} NOT IN "+priority_values_sql)
              
    gdal.RasterizeLayer(out_ds, [1],
                   vl,
                   options = ["ALL_TOUCHED=FALSE", 
                              f"ATTRIBUTE={attribute}"])
                              
    for i in range(0,len(priority_values)):
    
        priority_value = priority_values[len(priority_values) - 1 - i]

        vl.SetAttributeFilter(f"{priority_field} = {priority_value}")

        gdal.RasterizeLayer(out_ds, [1],
                       vl,
                       options = ["ALL_TOUCHED=FALSE", 
                                  f"ATTRIBUTE={attribute}"])
        
    vl = None
    vds = None
        
    out_ds.FlushCache()
    out_ds = None
    
    # Return GDAL dataset (easier to convert to NumPy)
    ds = gdal.Open(tmp_output_path)
    array = ds.GetRasterBand(1).ReadAsArray()
    
    ds = None
    os.remove(tmp_output_path)
    
    array = array.astype(dtype)

    return array

class AffineTransformer:

    def __init__(self, transform):
    
        self.fwd_matrix = np.array([[transform[0], transform[1], transform[2]],
                                    [transform[3], transform[4], transform[5]]])
                                    
        inv_transform = gdal.InvGeoTransform(transform)
        
        self.inv_matrix = np.array([[inv_transform[0], inv_transform[1], inv_transform[2]],
                                    [inv_transform[3], inv_transform[4], inv_transform[5]]])
                                    
    def xy(self, rows, cols):
    
        try:
            length = len(rows)
            scalar = False
        except:
            scalar = True
            length = 1
            rows = np.array([rows])
            cols = np.array([cols])
            
        if len(rows) != len(cols) or len(rows) == 0 :
            raise ValueError("Inputs of different length.")
            
        inputs = np.vstack([np.ones((1,length)), cols[np.newaxis,:], rows[np.newaxis,:]])
            
        x, y = np.matmul(self.fwd_matrix, inputs)
        
        if scalar :
            x = x[0]
            y = y[0]
        
        return x, y
        
    def rowcol(self, x, y):
    
        try:
            length = len(x)
            scalar = False
        except:
            scalar = True
            length = 1
            x = np.array([x])
            y = np.array([y])
            
        if len(x) != len(y) or len(x) == 0 :
            raise ValueError("Inputs of different length.")
            
        inputs = np.vstack([np.ones((1,length)), x[np.newaxis,:], y[np.newaxis,:]])
            
        cols, rows = np.matmul(self.inv_matrix, inputs)
        
        if scalar :
            cols = cols[0]
            rows = rows[0]
        
        return rows, cols
        
class CoordTransformXY:

    def __init__(self, src_crs, dst_crs):
    
        src_srs = osr.SpatialReference()
        src_srs.ImportFromWkt(src_crs)
        dst_srs = osr.SpatialReference()
        dst_srs.ImportFromWkt(dst_crs)
        
        self.src_srs = src_srs
        self.src_geog = src_srs.IsGeographic()
        self.dst_srs = dst_srs
        self.dst_geog = dst_srs.IsGeographic()
        
        self.transformer = osr.CoordinateTransformation(src_srs, dst_srs)
        
    def transform(self, x, y):
    
        if self.src_geog :
            input_x = y
            input_y = x
        else:
            input_x = x
            input_y = y
            
        output_x, output_y, _ = self.transformer.TransformPoint(input_x, input_y)
        
        if self.dst_geog :
        
            return output_y, output_x
            
        else:
        
            return output_x, output_y
