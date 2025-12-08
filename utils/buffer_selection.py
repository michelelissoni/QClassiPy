from PyQt5.QtGui import QColor 
from PyQt5.QtCore import Qt, pyqtSignal

from qgis.core import QgsGeometry, QgsVectorLayer, QgsWkbTypes
from qgis.gui import QgsMapTool, QgsRubberBand

import qgis.utils

class BufferSelectionTool(QgsMapTool):

    leftButtonReleased = pyqtSignal()

    def __init__(self, canvas, buffer_size=50):
        super().__init__(canvas)
        self.canvas = canvas
        self.buffer_size = buffer_size
        self.is_drawing = False
        self.points = []
        self.rubber_band = None

    def canvasPressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.is_drawing = True
            self.points = []
            self.rubber_band = self.create_rubber_band()
            self.add_point(event.pos())

    def canvasMoveEvent(self, event):
        if self.is_drawing:
            self.add_point(event.pos())
            self.update_buffer()

    def canvasReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.is_drawing = False

            self.select_features_within_buffer()
            self.canvas.scene().removeItem(self.rubber_band)
            self.leftButtonReleased.emit()
            
    def add_point(self, pos):
        point = self.toMapCoordinates(pos)
        self.points.append(point)
        self.rubber_band.addPoint(point, True)

    def update_buffer(self):
        if len(self.points) < 2:
            return
        
        line_geometry = QgsGeometry.fromPolylineXY(self.points)
        buffer_geometry = line_geometry.buffer(self.buffer_size, 5)
        self.rubber_band.setToGeometry(buffer_geometry, None)

    def select_features_within_buffer(self):
        
        if len(self.points) < 2:
            return
        
        active_layer = qgis.utils.iface.activeLayer()
        if not active_layer or not isinstance(active_layer, QgsVectorLayer):
            return
        
        line_geometry = QgsGeometry.fromPolylineXY(self.points)
        buffer_geometry = line_geometry.buffer(self.buffer_size, 5)
        
        active_layer.removeSelection()
        
        for feature in active_layer.getFeatures():
            if buffer_geometry.intersects(feature.geometry()):
                active_layer.select(feature.id())

    def create_rubber_band(self):
        rubber_band = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        rubber_color = QColor('orange')
        rubber_color.setAlphaF(0.3)
        rubber_band.setColor(rubber_color)
        rubber_band.setWidth(2)
        return rubber_band

