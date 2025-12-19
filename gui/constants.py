import os
import numpy as np

from qgis.PyQt.QtGui import QColor

class Directories:

    Plugin = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
    
    Layer = os.path.join(Plugin, 'layers')
    
    Icon = os.path.join(Plugin, 'icons')
    
    Font = os.path.join(Plugin, 'fonts')
    
class Priorities:

    Completed = 0
    Uncompleted = 1
    
class Colors:

    Default = QColor("white")
    
    Colorlist = np.array([QColor(colorstr) for colorstr in np.loadtxt(os.path.join(Directories.Plugin, 'gui', 'colorlist.txt'), dtype=str)])
    
    Brush = QColor("orange")
    
    Frame = QColor("orange")
    
    Tile_Bounds = QColor("red") 
    
    Completed = QColor(255,0,0,255)
    Uncompleted = QColor(0,165,0,255)

 
    
    
