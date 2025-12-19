import numpy as np
import gc

def gridPositions(ylims, xlims, image_size, start = None, spacing=0.9):
    
    if not(len(ylims)==2 and np.issubdtype(type(ylims[0]), np.integer) and np.issubdtype(type(ylims[1]), np.integer)) :
        raise ValueError("'ylims' must be a sequence of integers of length 2.")

    if not(len(xlims)==2 and np.issubdtype(type(xlims[0]), np.integer) and np.issubdtype(type(xlims[1]), np.integer)) :
        raise ValueError("'xlims' must be a sequence of integers of length 2.")
        
    if isinstance(image_size, int) :
        image_size_y = image_size
        image_size_x = image_size
    elif len(image_size)==2 and np.issubdtype(type(image_size[0]), np.integer) and np.issubdtype(type(image_size[1]), np.integer) :
        image_size_y = image_size[0]
        image_size_x = image_size[1]
    else:
        raise ValueError("'image_size' must be an integer or a sequence of integers of length 2.")

    if isinstance(spacing, float) and spacing < 1 :
        spacing_y = int(spacing*image_size_y)
        spacing_x = int(spacing*image_size_x)
    elif isinstance(spacing, int):
        spacing_y = spacing
        spacing_x = spacing
    elif len(spacing) == 2 and np.issubdtype(type(spacing[0]), np.integer) and np.issubdtype(type(spacing[1]), np.integer) :
        spacing_y = spacing[0]
        spacing_x = spacing[1]
    else:
        raise ValueError("'spacing' value not valid.")

    if start is None :
        start_y = np.random.randint(ylims[0],ylims[1]-image_size_y)
        start_x = np.random.randint(xlims[0],xlims[1]-image_size_x)
    elif len(start)==2 and np.issubdtype(type(start[0]), np.integer) and start[0] >= ylims[0] and start[0] < ylims[1]-image_size_y and np.issubdtype(type(start[1]), np.integer)  and start[1] >= xlims[0] and start[1] < xlims[1]-image_size_x :
        start_y = start[0]
        start_x = start[1]
    else:
        raise ValueError("'start' must be either None or a sequence of two integers within the grid limits.")
    
    x_starts = np.append(np.arange(start_x, xlims[1]-image_size_x, spacing_x, dtype=int), np.arange(start_x, xlims[0], -spacing_x, dtype=int))
    x_starts = np.unique(np.append([xlims[0],xlims[1]-image_size_x], x_starts))
    y_starts = np.append(np.arange(start_y, ylims[1]-image_size_y, spacing_y, dtype=int), np.arange(start_y, ylims[0], -spacing_y, dtype=int))
    y_starts = np.unique(np.append([ylims[0],ylims[1]-image_size_y], y_starts))

    pos_y = np.repeat(y_starts, len(x_starts))
    pos_x = np.tile(x_starts, len(y_starts))

    return pos_y, pos_x

def positionOverlaps(x_min, y_min, height, width):

    x_min = np.array(x_min)
    y_min = np.array(y_min)
    height = np.array(height)
    width = np.array(width)
    
    if not len(x_min)==len(y_min)==len(height)==len(width) or len(x_min.shape) !=1 :
        raise ValueError("The arrays must be 1D and all the same length")

    y_max = y_min + height
    x_max = x_min + width
    
    x_between = ((x_min[:,np.newaxis]>=x_min[np.newaxis,:]) & (x_min[:,np.newaxis]<x_max[np.newaxis,:])) | ((x_max[:,np.newaxis]>=x_min[np.newaxis,:]) & (x_max[:,np.newaxis]<x_max[np.newaxis,:]))
    y_between = ((y_min[:,np.newaxis]>=y_min[np.newaxis,:]) & (y_min[:,np.newaxis]<y_max[np.newaxis,:])) | ((y_max[:,np.newaxis]>=y_min[np.newaxis,:]) & (y_max[:,np.newaxis]<y_max[np.newaxis,:]))

    overlap = x_between & y_between
    del x_between
    del y_between
    gc.collect()
    
    overlap = overlap | np.transpose(overlap)
        
    overlap[np.arange(len(x_min), dtype=int), np.arange(len(x_min), dtype=int)] = False
    
    overlap, overlapping = np.nonzero(overlap)
    
    overlap_list = []
    
    for i in range(0,len(x_min)):
        overlap_list.append(list(overlapping[overlap==i]))
        
    return overlap_list
