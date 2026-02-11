"""
Filename: table_dock.py
Author: Michele Lissoni
Date: 2026-02-10
"""

"""

The QClassiPyDockWidget class handles the dock widget containing the tabs and
the passages between the tabs.

"""

from qgis.PyQt.QtWidgets import QApplication, QWidget
from qgis.PyQt.QtCore import QRect, QEvent
from qgis.PyQt.QtGui import QFont

from qgis.gui import QgsDockWidget

import os

from .draw_mask import QClassiPyDrawMask
from .create_tiles import QClassiPyCreateTiles
from .merge_masks import QClassiPyMergeMasks
from ..ui.all_uis import Ui_QClassiPyDockWidget

class QClassiPyDockWidget(QgsDockWidget):
    
    def __init__(self, tab_clicked = 1, font = QFont()):
    
        """
        Initialization
        
        Keywords:
        - tab_clicked (int): 0 for Create tiles, 1 for Draw mask, 2 for Merge masks
        - font (QFont): the font of the plugin
        """
        
        super(QClassiPyDockWidget, self).__init__()
        
        self.ui = Ui_QClassiPyDockWidget()
        self.ui.setupUi(self)
                
        # Set the font to all child widgets
                
        self.best_font = font
        for child_widget in self.findChildren(QWidget):
            child_widget.setFont(font)
        
        self.draw_mask = None
        self.create_tiles = None
        self.merge_masks = None

        self.open_tab_index = -1
        self.ui.plugin_tabs.setCurrentIndex(tab_clicked)
        self.onTabClicked(tab_clicked)
        
        self.ui.plugin_tabs.tabBar().installEventFilter(self)

        self.ui.closing_label.setHidden(True)
        self.ui.switching_label.setHidden(True)
        
    def onTabClicked(self, index):
        """
        Open the tab that has been clicked
        """

        # Do nothing if the open tab has been clicked
        if index==self.open_tab_index :
            return
            
        # Remove widget from previous tab

        if self.open_tab_index==0 :
            self.layout().removeWidget(self.create_tiles)
            tiles_closed = self.create_tiles.close()
            
            if tiles_closed :
                self.create_tiles = None
            else:
                self.ui.plugin_tabs.setCurrentIndex(0)
                self.ui.plugin_tabs.setCurrentWidget(self.ui.create_tiles_tab)
                self.ui.layout().addWidget(self.create_tiles)
                return False
            
        elif self.open_tab_index==1 :
            self.layout().removeWidget(self.draw_mask)
            draw_closed = self.draw_mask.close()
            
            if draw_closed :
                self.draw_mask = None
            else:
                self.ui.plugin_tabs.setCurrentIndex(1)
                self.ui.plugin_tabs.setCurrentWidget(self.ui.draw_mask_tab)
                self.layout().addWidget(self.draw_mask)
                return False
        
        elif self.open_tab_index==2 :
            self.layout().removeWidget(self.merge_masks)
            tiles_closed = self.merge_masks.close()
            
            if tiles_closed :
                self.merge_masks = None
            else:
                self.ui.plugin_tabs.setCurrentIndex(2)
                self.ui.plugin_tabs.setCurrentWidget(self.merge_masks_tab)
                self.layout().addWidget(self.merge_masks)
                return False

        # Create widget for new tab
        
        # "Create tiles"
        if index==0 :
           self.ui.plugin_tabs.setCurrentIndex(0)
           self.ui.plugin_tabs.setCurrentWidget(self.ui.create_tiles_tab) 
           
           self.create_tiles = QClassiPyCreateTiles(parent = self, font = self.best_font)
           self.layout().addWidget(self.create_tiles)
           self.create_tiles.setGeometry(QRect(10, 55, 434, 467))
        
        # "Draw mask"
        elif index==1 :
        
           self.ui.plugin_tabs.setCurrentIndex(1)
           self.ui.plugin_tabs.setCurrentWidget(self.ui.draw_mask_tab) 
        
           self.draw_mask = QClassiPyDrawMask(parent = self, font = self.best_font)
           self.layout().addWidget(self.draw_mask)
           self.draw_mask.setGeometry(QRect(10, 55, 434, 467))
        
        # "Merge masks"
        elif index==2 :
           self.ui.plugin_tabs.setCurrentIndex(2)
           self.ui.plugin_tabs.setCurrentWidget(self.ui.merge_mask_tab) 
           
           self.merge_masks = QClassiPyMergeMasks(parent = self, font = self.best_font)
           self.layout().addWidget(self.merge_masks)
           self.merge_masks.setGeometry(QRect(10, 55, 434, 467))
        
        self.open_tab_index = index
                
        return True
        
    def eventFilter(self, obj, event):
        """
        Overload the event filter to show a "Switching" message in case switching tabs takes some time.
        """
    
        if obj == self.ui.plugin_tabs.tabBar() :
        
            if event.type() == QEvent.MouseButtonPress:
                index = obj.tabAt(event.pos())
                
                self.ui.switching_label.setHidden(False)
                self.ui.switching_label.repaint()
                QApplication.processEvents()
                
                switch_tab = self.onTabClicked(index)
                
                self.ui.switching_label.setHidden(True)
                
                return not switch_tab
                
        return super().eventFilter(obj, event)
       
    def closeEvent(self, event):
        """
        Close the open tab and close the widget
        """
        
        self.ui.closing_label.setHidden(False)
        self.ui.closing_label.repaint()
        QApplication.processEvents()
        
        if self.draw_mask is not None :
        
            widget_closed = self.draw_mask.close()
            
        elif self.create_tiles is not None :
        
            widget_closed = self.create_tiles.close()

        elif self.merge_masks is not None :
        
            widget_closed = True
            
        else:
            
            widget_closed = True
            
        if widget_closed :
            event.accept()
        else:
            self.ui.closing_label.setHidden(True)
            event.ignore()
            
