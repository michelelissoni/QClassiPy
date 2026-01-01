# External dependencies

The QClassiPy plugin has dependencies on the Python `Numpy`, `Pandas` and `Shapely` packages. While these are bundled with some versions of QGIS, this is not always the case. The plugin also uses the GDAL library bundled with QGIS, which may be incompatible with `NumPy 2.0`.

If there is a dependency error, a `Missing packages` message will pop up. It will list the missing or incompatible packages. Here follow our proposed solution to the most common dependency issues.

<img src="https://github.com/michelelissoni/QClassiPy/blob/main/docs/images/missing_packages.png">
