"""
Filename: positions.py
Author: Michele Lissoni
Date: 2026-02-10
"""

"""

Tools to handle the tile positions.

- gridPositions: generates tile locations.

- positionOverlaps: ascertains which tiles overlap.

"""

import numpy as np
import gc

def gridPositions(ylims, xlims, image_size, start = None, spacing=0.9):

    """
    Generate tile locations on a 2D grid.
    
    Arguments:
    - ylims, xlims (tuples): the limits of the grid portion along the row and column axes where the tiles will be generated.
    - image_size (tuple): dimensions of the tile along the row and column axes.
                   
    Keywords:
    - start (tuple): a (row, col) coordinate where a tile will have its corner. If not set, the tiles are initialized from a random location.
    - spacing (float): the fraction of the tile size between the side of a tile and the beginning of the next one. 
                       If for example `start = (10,12)`, `image_size=(100,200)` and `spacing=0.9`, the tiles will have their upper-left corners
                       in the cells (10+n*90,12+m*180), where n and m are integers that can assume any value (positive, negative or zero) such that
                       the tiles are contained within the `ylims` and `xlims`.
    
    Returns: 
    - pos_y, pos_x: row and col coordinates of the tile upper-left corners.
    """
    
    # Check input data
   
    if not(len(ylims)==2 and np.issubdtype(type(ylims[0]), np.integer) and np.issubdtype(type(ylims[1]), np.integer)) :
        raise ValueError("'ylims' must be a sequence of integers of length 2.")

    if not(len(xlims)==2 and np.issubdtype(type(xlims[0]), np.integer) and np.issubdtype(type(xlims[1]), np.integer)) :
        raise ValueError("'xlims' must be a sequence of integers of length 2.")
        
    # Tile size 
      
    if isinstance(image_size, int) :
        image_size_y = image_size
        image_size_x = image_size
    elif len(image_size)==2 and np.issubdtype(type(image_size[0]), np.integer) and np.issubdtype(type(image_size[1]), np.integer) :
        image_size_y = image_size[0]
        image_size_x = image_size[1]
    else:
        raise ValueError("`image_size` must be an integer or a sequence of integers of length 2.")

    # Tile spacing in grid integer units

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
        raise ValueError("`spacing` value not valid.")

    # Starting point

    if start is None :
        start_y = np.random.randint(ylims[0],ylims[1]-image_size_y)
        start_x = np.random.randint(xlims[0],xlims[1]-image_size_x)
    elif len(start)==2 and np.issubdtype(type(start[0]), np.integer) and start[0] >= ylims[0] and start[0] < ylims[1]-image_size_y and np.issubdtype(type(start[1]), np.integer)  and start[1] >= xlims[0] and start[1] < xlims[1]-image_size_x :
        start_y = start[0]
        start_x = start[1]
    else:
        raise ValueError("'start' must be either None or a sequence of two integers within the grid limits.")
    
    # Define positions
    
    x_starts = np.append(np.arange(start_x, xlims[1]-image_size_x, spacing_x, dtype=int), np.arange(start_x, xlims[0], -spacing_x, dtype=int))
    x_starts = np.unique(np.append([xlims[0],xlims[1]-image_size_x], x_starts))
    y_starts = np.append(np.arange(start_y, ylims[1]-image_size_y, spacing_y, dtype=int), np.arange(start_y, ylims[0], -spacing_y, dtype=int))
    y_starts = np.unique(np.append([ylims[0],ylims[1]-image_size_y], y_starts))

    pos_y = np.repeat(y_starts, len(x_starts))
    pos_x = np.tile(x_starts, len(y_starts))

    return pos_y, pos_x

def positionOverlaps(x_min, y_min, height, width):

    """
    Check which tiles overlap.
    
    Arguments:
    - x_min, y_min : the upper left corners of the tiles along the column and rows axis.
    - height, width : the heights and widths of the tiles, same length as `x_min` and `y_min`.
    
    Returns: 
    - overlap_list : a list of the same length as `x_min`, at each index it contains a list of the tiles (in terms of tile indices) 
                     with which the tile at that index overlaps.
    """

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
