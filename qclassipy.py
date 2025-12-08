import os

from qgis.PyQt.QtWidgets import QAction, QApplication 
from qgis.PyQt.QtGui import QIcon, QFontDatabase, QFont
from qgis.PyQt.QtCore import Qt

plugin_dir = os.path.dirname(os.path.abspath(__file__))

class QClassiPy:

    def __init__(self, iface):
    
        self.iface = iface
        
    def initGui(self):

        font_file = os.path.join(os.path.dirname(__file__), "fonts", "Ubuntu-R.ttf")
        font_id = QFontDatabase.addApplicationFont(font_file)
        loaded_fonts = QFontDatabase.applicationFontFamilies(font_id)

        if loaded_fonts:
            plugin_font = QFont(loaded_fonts[0], 11)
            QApplication.setFont(plugin_font)
    
        self.draw_mask_action = QAction(QIcon(os.path.join(plugin_dir,'icons','qcl_icon.svg')),
                                "Draw mask",
                                self.iface.mainWindow())

        self.create_tiles_action = QAction(QIcon(),
                                  "Create tiles",
                                  self.iface.mainWindow())
                               
        self.merge_masks_action = QAction(QIcon(),
                                  "Merge masks",
                                  self.iface.mainWindow())
                              
        self.draw_mask_action.triggered.connect(lambda: self.run(1))
        self.create_tiles_action.triggered.connect(lambda: self.run(0))
        self.merge_masks_action.triggered.connect(lambda: self.run(2))
        
        self.iface.addToolBarIcon(self.draw_mask_action)
        
        self.iface.addPluginToMenu("&QClassiPy", self.create_tiles_action)
        self.iface.addPluginToMenu("&QClassiPy", self.draw_mask_action)
        self.iface.addPluginToMenu("&QClassiPy", self.merge_masks_action)
        
    def unload(self):

        self.iface.removePluginMenu("&QClassiPy", self.create_tiles_action)
        self.iface.removePluginMenu("&QClassiPy", self.draw_mask_action)
        self.iface.removePluginMenu("&QClassiPy", self.merge_masks_action)

        self.iface.removeToolBarIcon(self.draw_mask_action)
        
    def run(self, action_clicked):
    
        import importlib
        from .gui import dock_widget
        importlib.reload(dock_widget)
        from .gui.dock_widget import QClassiPyDockWidget

        self.dock = QClassiPyDockWidget(tab_clicked = action_clicked)

        self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dock)
