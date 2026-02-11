"""
Filename: table_dock.py
Author: Michele Lissoni
Date: 2026-02-10
"""

"""
Some important constants.
"""

import os
import numpy as np

from qgis.PyQt.QtGui import QColor

class Directories:

    Plugin = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..') # Root
    
    Layer = os.path.join(Plugin, 'layers') # Data layers 
    
    Icon = os.path.join(Plugin, 'icons') # Icons
    
    Font = os.path.join(Plugin, 'fonts') # Fonts
    
class Priorities:

    """
    How to interpret the priority column in the tile list.
    """

    Completed = 0
    Uncompleted = 1
    
class Colors:

    Default = QColor("white") # Null value 
    
    Colorlist = np.array([QColor(colorstr) for colorstr in np.loadtxt(os.path.join(Directories.Plugin, 'gui', 'colorlist.txt'), dtype=str)]) # Color list
    
    Brush = QColor("orange") # Brush track
    
    Frame = QColor("orange") # Frame around the polyimage
    
    Tile_Bounds = QColor("red") # Tile bounds when choosing the tile positions in Create tiles
    
    Completed = QColor(255,0,0,255) # Completed tiles
    Uncompleted = QColor(0,165,0,255) # Uncompleted tiles

 
    
    
