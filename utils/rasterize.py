import os
import numpy as np
import processing
from osgeo import gdal, ogr
import gc

def rasterizeLayer(
    vector_path,           # QgsVectorLayer
    attribute,            # attribute name to burn
    out_shape,            # (height, width)
    transform, 
    layer_name = None,  # GDAL geotransform
    nodata = 0,
    tmp_output_path = "temporary_raster.tif",
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
    
    band = out_ds.GetRasterBand(1)
    band.Fill(float(nodata))
    band.SetNoDataValue(float(nodata))
    
    vds = ogr.Open(vector_path)
    vl = vds.GetLayer(layer_name)

    gdal.RasterizeLayer(out_ds, [1],
                   vl,
                   options = ["ALL_TOUCHED=TRUE", f"ATTRIBUTE={attribute}"])
    
    out_ds.FlushCache()
    out_ds = None
    vds = None
    
    # Return GDAL dataset (easier to convert to NumPy)
    ds = gdal.Open(tmp_output_path)
    array = ds.GetRasterBand(1).ReadAsArray()
    
    ds = None
    os.remove(tmp_output_path)
    
    array = array.astype(dtype)

    return array
