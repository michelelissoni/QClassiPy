# External dependencies

The QClassiPy plugin has dependencies on the Python NumPy, Pandas and Shapely packages. While these are bundled with some versions of QGIS, this is not always the case. The plugin also uses the GDAL library bundled with QGIS, which may be incompatible with NumPy 2.0.

If there is a dependency error, a `Missing packages` message will pop up. It will list the missing or incompatible packages.

<img src="https://github.com/michelelissoni/QClassiPy/blob/main/docs/images/missing_packages.png">

The most common dependency issues are:
* Pandas and/or Shapely missing
* an incompatibility between GDAL and NumPy (message: `osgeo.gdal_array (needs numpy < 2)`)

We recommend the following solutions, depending on your operating system, but they may have to be tailored to your Python and QGIS setup. After implementing them, restart QGIS and the plugin should open without issue.

### Windows
1. Search among your applications for the `OSGeo4W Shell` and open it.
2. Type in that shell: `pip install --upgrade "numpy<2" pandas shapely`

Even if there are no NumPy incompatibilities, we suggest specifying `"numpy<2"` in the `pip` call to ensure that NumPy is not upgraded and the other packages do not have compatibility issues.

### Linux
The solution for Linux may depend on whether your main Python installation is in the Python path of QGIS (you can check the Python path by running `sys.path` in the QGIS Python Console). If it is, then you can simply run `pip install --upgrade "numpy<2" pandas shapely` in your terminal. Even if there are no NumPy incompatibilities, we suggest specifying `"numpy<2"` in the `pip` call to ensure that NumPy is not upgraded and the other packages do not have compatibility issues.

If your main Python installation is not in the QGIS Python path or you do not wish to downgrade your main Python packages, then you can install the packages for the QGIS Python installation. If the QGIS Python executable is `/usr/bin/python3` (this is the most common case, but you can check via `sys.executable`), we suggest installing the `python3-numpy` (currently, this NumPy version is <2.0), `python3-pandas` and/or `python3-shapely` packages with your package installer (`apt` for Debian/Ubuntu, `dnf` for Fedora).

### MacOS
Not yet tested, but the Linux solution might apply in this case as well.

## Other problems
If you receive the `Missing packages` message, but the problematic packages are not those described above, check the Python Warning (in the QGIS Python console) that has been issued concurrently. You will find more information on the error.
