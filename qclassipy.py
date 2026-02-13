"""
Filename: qclassipy.py
Author: Michele Lissoni
Date: 2026-02-10
"""

"""
Initialization of the plugin buttons and GUI. Check for dependency problems.
"""


import os
import sys
import platform
import subprocess
import warnings

from qgis.core import Qgis
from qgis.PyQt.QtWidgets import QAction, QApplication, QMessageBox 
from qgis.PyQt.QtGui import QIcon, QFontDatabase, QFont
from qgis.PyQt.QtCore import Qt

from .gui.constants import Directories

layer_dir = Directories.Layer
icon_dir = Directories.Icon
font_dir = Directories.Font

def get_python_executable():
    """Get the actual Python executable path across platforms."""
    system = platform.system()
    
    if system == 'Windows':
        # On Windows, use exec_prefix
        executable = os.path.join(sys.exec_prefix, 'python.exe')
    elif system == 'Darwin':  # macOS
        # On macOS, Python is typically in bin/python3
        executable = os.path.join(sys.exec_prefix, 'bin', 'python3')
    else:
        # Fallback
        executable = sys.executable
        
    path_exists = os.path.isfile(executable)
        
    executable = sys.executable if not path_exists else executable
    
    return executable, path_exists     

def checkPackages():
    """Check whether all the necessary packages can be imported."""

    missing_packages = []
    package_errors = []
    
    try:
        import packaging
    except Exception as e:
        package_errors.append(type(e).__name__ +':  '+str(e))
        missing_packages.append('packaging')
        
    try:
        import numpy as np
    except Exception as e:
        package_errors.append(type(e).__name__ +':  '+str(e))
        missing_packages.append('numpy')
        
    try:
        import pandas as pd
    except Exception as e:
        package_errors.append(type(e).__name__ +':  '+str(e))
        missing_packages.append('pandas')
        
    try:
        import shapely
        shapely_geos_major, shapely_geos_minor, _ = shapely.geos_version
        
        # Error message for incompatibility between the QGIS and Shapely versions of GEOS. May not be necessary.
        '''
        if shapely_geos_major != Qgis.geosVersionMajor() or shapely_geos_minor != Qgis.geosVersionMinor():
            missing_packages.append('shapely')
            package_errors.append(f"Shapely GEOS is {shapely.geos_version_string}, but QGIS GEOS version is {Qgis.geosVersion()}. Consider uninstalling shapely and reinstalling with `pip install shapely --no-binary shapely`.")
        '''
        
    except Exception as e:
        package_errors.append(type(e).__name__ +':  '+str(e))
        missing_packages.append('shapely')
        
    try:
        from osgeo import gdal
        from osgeo import ogr
        from osgeo import osr
    except Exception as e:
        package_errors.append(type(e).__name__ +':  '+str(e))
        missing_packages.append('osgeo')
        
    # Currently, osgeo.gdal_array is incompatible with NumPy 2. To catch the error,
    # it is necessary to import it in a subprocess.
        
    python_executable, path_exists = get_python_executable()
    
    result = subprocess.run(
        [python_executable, '-c', 'from osgeo import gdal_array'],
        capture_output=True
    )
    
    if result.returncode != 0 :
        package_errors.append(str(result.stderr))
        try:
            import numpy
            if 'numpy' in str(result.stderr) and numpy.__version__>='2' :
                missing_packages.append("osgeo.gdal_array (needs numpy &lt; 2)")
        except:
            missing_packages.append('osgeo.gdal_array')
            
    return missing_packages, package_errors

class QClassiPy:

    def __init__(self, iface):
    
        self.iface = iface
        
        self.missing_packages, self.package_errors = checkPackages()
        
    def initGui(self):
        """Initialize the commands in the plugin menu and load the icon in the plugin bar."""

        # Load font for optimal visualization

        font_file = os.path.join(font_dir, "Ubuntu-R.ttf")
        font_id = QFontDatabase.addApplicationFont(font_file)
        loaded_fonts = QFontDatabase.applicationFontFamilies(font_id)

        if loaded_fonts:
            self.best_font = QFont(loaded_fonts[0], 11)
        else:
            self.best_font = None
    
        # QActions to open the QClassiPy tabs
    
        self.draw_mask_action = QAction(QIcon(os.path.join(icon_dir, 'qcl_icon.svg')),
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

        # Add the actions to the plugin menu entries and the plugin bar
        
        self.iface.addToolBarIcon(self.draw_mask_action) # The tool bar icon opens the Draw Mask tab
        
        self.iface.addPluginToMenu("&QClassiPy", self.create_tiles_action)
        self.iface.addPluginToMenu("&QClassiPy", self.draw_mask_action)
        self.iface.addPluginToMenu("&QClassiPy", self.merge_masks_action)
        
    def unload(self):

        self.iface.removePluginMenu("&QClassiPy", self.create_tiles_action)
        self.iface.removePluginMenu("&QClassiPy", self.draw_mask_action)
        self.iface.removePluginMenu("&QClassiPy", self.merge_masks_action)

        self.iface.removeToolBarIcon(self.draw_mask_action)
        
    def run(self, action_clicked):
    
        """Open the GUI in the dock widget."""
    
        python_version = sys.version
        
        if sys.version < '3' :
            msg = QMessageBox()
            msg.setWindowTitle("Python version")
            msg.setText("Python 3 (preferably &ge;3.10)<br> is needed.")
            msg.addButton(QMessageBox.Ok)
            msg.exec_()
            
            return
            
        # Error message for dependency issues    
            
        if len(self.missing_packages) > 0:
        
            for i, package in enumerate(self.missing_packages):
                warnings.warn(package+"  :  " + self.package_errors[i])
        
            package_string = "<br>".join(self.missing_packages)

            msg = QMessageBox()
            msg.setWindowTitle("Missing packages")
            msg.setText("Install or fix these Python packages<br>and restart QGIS.<br><br>"+package_string+"<br><br><a href='https://github.com/michelelissoni/QClassiPy/blob/main/docs/dependencies.md'>Help</a>")
            msg.addButton(QMessageBox.Ok)
            msg.exec_()
            
            return
            
        # Create file that will contain default browse directory
        
        browsedir_path = os.path.join(layer_dir, 'browsedir.txt')
        if not os.path.exists(browsedir_path):
            with open(browsedir_path, 'w') as outfile:
                outfile.write('')
                        
        # Open the dock widget
                        
        from .gui.dock_widget import QClassiPyDockWidget

        self.dock = QClassiPyDockWidget(tab_clicked = action_clicked, font = self.best_font)
        
        self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dock)
        
