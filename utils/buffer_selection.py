"""
Filename: buffer_selection.py
Author: Michele Lissoni
Date: 2026-02-11
"""

"""

The BufferSelectionTool controls the brush and erase tools.

"""

from qgis.PyQt.QtCore import Qt, pyqtSignal, QPoint
from qgis.PyQt.QtGui import QColor

from qgis.core import QgsPoint, QgsGeometry, QgsVectorLayer, QgsWkbTypes
from qgis.gui import QgsMapTool, QgsRubberBand

import qgis.utils

from ..gui.constants import Colors

class BufferSelectionTool(QgsMapTool):

    leftButtonReleased = pyqtSignal()

    def __init__(self, canvas, layer, resolution, buffer_size=10):
    
        """Initialization"""
    
        super().__init__(canvas)
        self.canvas = canvas
        self.layer = layer # Layer which the brush will select
        self.buffer_size = buffer_size/2*resolution
        self.is_drawing = False
        self.points = []
        self.rubber_band = None
        self.buffer = None

    def canvasPressEvent(self, event):
    
        """When the left mouse button is pressed """
    
        if event.button() == Qt.LeftButton:
            self.is_drawing = True
            self.points = [] # Brush path (in layer coordinates)
            self.rubber_band = self.create_rubber_band() # Brush trace (in map coordinates)
            self.add_point(event.pos())

    def canvasMoveEvent(self, event):
    
        """ Add points to the brush path when the clicked mouse is moved. """
    
        if self.is_drawing:
            self.add_point(event.pos())
            self.update_buffer() # Extend the buffer

    def canvasReleaseEvent(self, event):
    
        """ When the mouse button is released, the features in the buffer are selected
            and the trace disappears."""
    
        if event.button() == Qt.LeftButton:
            self.is_drawing = False

            self.select_features_within_buffer()
            self.canvas.scene().removeItem(self.rubber_band)
            self.leftButtonReleased.emit()
            
    def add_point(self, pos):
    
        """ Add points to the brush path and buffer. """
    
        point = self.toLayerCoordinates(self.layer, pos) # Point in layer coordinates
        self.points.append(point)
        self.rubber_band.addPoint(self.toMapCoordinates(pos), True)

    def update_buffer(self):
    
        """Extend the buffer."""
    
        if len(self.points) < 2:
            return
        
        line_geometry = QgsGeometry.fromPolylineXY(self.points)
        buffer_geometry = line_geometry.buffer(self.buffer_size, 5)
        self.buffer = buffer_geometry # Brush buffer (in layer coordinates, necessary to select pixels when 
                                      # the layer CRS does not match the map CRS
        
        # The brush trace is in map coordinates, so that it can be displayed in QGIS
        
        buffer_points = buffer_geometry.asPolygon()[0]
        
        buffer_map = []
        for buffer_point in buffer_points:
            buffer_point_map = self.toMapCoordinates(self.layer, buffer_point)
            buffer_map.append(buffer_point_map)
        
        self.rubber_band.setToGeometry(QgsGeometry.fromPolygonXY([buffer_map]), None)

    def select_features_within_buffer(self):
    
        """Select features (pixel polygons) within the brush buffer."""
        
        if len(self.points) < 2:
            return
            
        if(self.buffer is None):
            return
        
        self.layer.removeSelection()
        
        for feature in self.layer.getFeatures():
            if self.buffer.intersects(feature.geometry()):
                self.layer.select(feature.id())

    def create_rubber_band(self):
    
        """Symbology for the brush trace."""
    
        rubber_band = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        rubber_color = QColor(Colors.Brush)
        rubber_color.setAlphaF(0.3)
        rubber_band.setColor(rubber_color)
        rubber_band.setWidth(2)
        return rubber_band

