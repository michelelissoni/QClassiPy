# Get started

Let us start with a simple example of what can be achieved with QClassiPy. In this example, we will improve a Land Use Land Cover map from the Sentinel-2 10m Land Use/Land Cover Time Series (Karra et al. 2021).

## Download data

1. Download the data: [WestAlps_example.zip](https://github.com/michelelissoni/QClassiPy/blob/main/docs/WestAlps_example.zip)
2. Decompress the folder. Open the `west_alps.qgz` project in QGIS. It contains just a Google Satellite basemap.
   
   > You can also use another satellite basemap you are familiar with, as long as it covers the Western Alps.
  
3. Load the raster `WestAlps_S2LULC.tif`. It is a LULC raster with 9 classes. After inspecting the raster, hide or remove it.

<img src="https://github.com/michelelissoni/QClassiPy/blob/main/docs/images/lulc_westalps.png" height="150"> <img src="https://github.com/michelelissoni/QClassiPy/blob/main/docs/images/lulc_legend.png" height="150"> 

## Modify the map

4. Open QClassiPy from the icon in the plugin bar <img src="https://github.com/michelelissoni/QClassiPy/blob/main/icons/qcl_icon.svg" width="20">. Under `Load tile list`, click the 3-dot button and choose the `tiles_maurienne.csv` file. This file contains the coordinates of the raster tiles than can be edited by QClassiPy.
<img src="https://github.com/michelelissoni/QClassiPy/blob/main/docs/images/load_tiles.png" height="70">

5. Click on `Update mask path`. Find and choose the `WestAlps_S2LULC.tif` file. Now, the tile list has been updated to the correct file path on your system. You will not need to repeat this step with this list.

6. Click `Choose tile`. A table will open under the QClassiPy panel and you will see some green rectangles appear on the map. These are the tile locations. You can select them in the table or choose them from the map by selecting the tile with the QGIS Selection tool <img src="https://github.com/michelelissoni/QClassiPy/blob/main/docs/images/select_rectangle.png" height="40">.

7. Go the row 115 in the table and select it. Click `Ok`. In the QClassiPy panel, the `Classify` box will be enabled, and the project will zoom to the tile. You will see the LULC tile overlaid over the basemap. Using the `Opacity` bar, you can change its opacity.

<img src="https://github.com/michelelissoni/QClassiPy/blob/main/docs/images/stmichel_maurienne.png" height="300"> <img src="https://github.com/michelelissoni/QClassiPy/blob/main/docs/images/classify_tools.png" height="300"> 

8. You will see that a `polyimage` polygon layer has appeared in your Layers panel. This layer contains the pixels of the raster converted to polygons, making it easier to modify them interactively.

9. The LULC map is already quite good, but not perfect. For example, the Water (1) patches indicating the valley's river are discontinuous. Let us therefore trace the full path of the river across the tile. From the `Draw value` drop-down, select class "1|". You may want to edit it to remember that it stands for water <img src="https://github.com/michelelissoni/QClassiPy/blob/main/docs/images/draw_value.png" height="40">. Feel free to change the color from the `Color` button.

10. Check the `Brush` box. The spinbox next to it, indicating the brush width, will be enabled. Keep the brush width to 1. Now click and drag your mouse along the length of the river. When you release the mouse, the pixel you have run over will be changed to the Water class.

<img src="https://github.com/michelelissoni/QClassiPy/blob/main/docs/images/river_before.png" height="150">   <img src="https://github.com/michelelissoni/QClassiPy/blob/main/docs/images/river_after.png" height="150">

11. Some tree patches are not covered by Tree (2) pixels. Select class "2|" from the drop-down. Check the `Selection` box. Then choose the QGIS Select by Polygon tool <img src="https://github.com/michelelissoni/QClassiPy/blob/main/docs/images/select_polygon.png" height="40">. Draw a polygon over a misclassified tree patch. When you release (right-click), the area selected by the polygon will be converted to the Tree class.

<img src="https://github.com/michelelissoni/QClassiPy/blob/main/docs/images/trees_before.png" height="150">   <img src="https://github.com/michelelissoni/QClassiPy/blob/main/docs/images/trees_after.png" height="150">

12. Click on `SAVE`. Now, if you load the `WestAlps_S2LULC.tif` again (if it's already loaded, you will have to reload it) you will see that the changes you've made are reflected in the raster as well.

13. Close QClassiPy. You will be asked `Is this tile complete?`. Select "Complete" and click `Ok`.

## Draw the map

QClassiPy is not just a tool to modify a map but also to draw it yourself. 

14. Reopen QClassiPy and the tile list (steps 4-6). You will see that the tile you edited earlier is now red rather than green. This is meant to help you remember which tiles you've already edited: "Incomplete" tiles are in green, "Complete" tiles in red. Now select a nearby tile (for example, row 71 in the table).

15. This time, we want to draw the map ourselves. To erase what has already been drawn, the easiest way is to select as draw value "0|NULL". This value is the same one indicated in the `Null value` field just above: the drawing tools will therefore now behave as erasers. Choose the `Selection` tool and draw a polygon around the whole tile. The previous map will be erased.

16. Let us focus on drawing just the Tree class. This time, check the `Polygon` box. A new layer called `polymask` will appear in your Layers panel.

   > The Polygon tool is most suitable when you have isolated patches that you are classifying surrounded by null pixels. In a map where every pixel is classified, like a LULC map, it can sometimes create small gaps.

18. Edit `polymask` like you would any polygon layer. Select it in the Layers panel and then Toggle Editing <img src="https://github.com/michelelissoni/QClassiPy/blob/main/docs/images/toggle_editing.png" height="40">. Add a polygon <img src="https://github.com/michelelissoni/QClassiPy/blob/main/docs/images/add_polygon.png" height="40">, drawing it over the tree patch. When you close it, it will ask for a value in field "1" (the band name). Set it to 2 (the Tree class). Now Save Edits <img src="https://github.com/michelelissoni/QClassiPy/blob/main/docs/images/save_edits.png" height="40">. The polygon will turn the correct color and below, the area of the map covered by the polygon is also set to 2.

<img src="https://github.com/michelelissoni/QClassiPy/blob/main/docs/images/polygon_before.png" height="150">   <img src="https://github.com/michelelissoni/QClassiPy/blob/main/docs/images/polygon_after.png" height="150">

18. You can edit the polygon further, for instance with the Vertex Tool <img src="https://github.com/michelelissoni/QClassiPy/blob/main/docs/images/vertex_tool.png" height="40">. Every time you Save Edits <img src="https://github.com/michelelissoni/QClassiPy/blob/main/docs/images/save_edits.png" height="40">, the changes will be transferred to the map below.

19. For finer adjustments, you can switch to the Brush tool and the Erase tool, which works like the Brush tool, but sets the pixels to the NULL value. In this case, the `polymask` layer will disappear, but it will re-appear if you switch the Polygon tool on again.

20. Once you are finished, save. Before closing, let's clean up the symbology. You can switch between Draw values and edit their definitions to match the legend (step 3). You will see that there are 256 available values (the symbology has been inherited from the original LULC dataset), but the ones beyond 11 are empty. We can therefore remove them. Set the Draw Value to 11. Then, under the `Remove class` button, check `Larger`. Then click `Remove class`. All the classes beyond 11 will be removed (Warning: if you remove a class that is represented on the map, all the pixels with that value will be turned to NULL). If you later re-open the file, you will find that this symbology has been saved.

## Create the tile list

If we want to switch to another region of the same raster, we have to create a new tile list.

21. Open QClassiPy and switch to the `Create Tiles` tab. Under `Choose raster`, find the `WestAlps_S2LULC.tif` and click `Select`. 

<img src="https://github.com/michelelissoni/QClassiPy/blob/main/docs/images/create_tiles.png" height="300"> 
 
22. A `Tile bounds` layer will appear in the Layers panel, containing a red frame delimiting the raster bounds. This will result in the tiles covering the whole raster. If you want only a smaller region, you can modify the bounds. The `Bounds` allows you to select a region from pixel positions or geographic/projected coordinates. However, the easiest way is to select the `Tile bounds` layer. Toggle Editing <img src="https://github.com/michelelissoni/QClassiPy/blob/main/docs/images/toggle_editing.png" height="40"> and use the Vertex Tool <img src="https://github.com/michelelissoni/QClassiPy/blob/main/docs/images/vertex_tool.png" height="40"> to modify the polygon. Once it encompasses only the region you want, Save Edits <img src="https://github.com/michelelissoni/QClassiPy/blob/main/docs/images/save_edits.png" height="40">.

   > The tile list file is a CSV with 6 columns: 'filename' (the map raster path), 'y', 'x' (the row and column of the tile's top-left corner), 'height', 'width' (the tile's height and width in pixels), 'priority' (set to 1 if the tile is Incomplete, to 0 if Complete). If you want a more sparse distribution of the tiles, you can create a custom CSV that serves your needs.

24. Uncheck `Mask path`. Choose the path of your tile list in `Tile list path`. Under `Tile size` you can change the size of the tiles, as well as their overlap.

   > You can shrink the tiles as much as you want, but be careful about enlarging them: past a few hundred pixels, the size of the `polyimage` layer becomes too large for your system to handle. If you have found that at 224 x 224 QClassiPy was already very slow, you can shrink the tiles to speed it up.

28. Click SAVE. The tiles will be saved. If you switch back to `Draw mask` and open the list, you will see that they are located only in the region you chose.

<img src="https://github.com/michelelissoni/QClassiPy/blob/main/docs/images/bounds_before.png" height="150">   <img src="https://github.com/michelelissoni/QClassiPy/blob/main/docs/images/bounds_after.png" height="150">

27. QClassiPy supports masks with multiple bands. If you want to create a new, custom mask, check `Mask path` and choose its path. Then, in the `Mask bands` table, you can add the masks you want and edit their names. The mask will have the same pixel grid as the file you select in `Choose raster`.

   > QClassiPy does not presently allow you to create a mask with a custom resolution. However, you can create a raster with a custom resolution from `Processing Toolbox` → `Raster creation` → `Create constant raster layer` (choose an integer data type, preferably Byte, if you want to draw directly on this mask). If you want a multi-band mask, you can just select the constant raster in QClassiPy `Create tiles` → `Choose raster`. Then follow step 27 to create a new, multi-band mask.

## Merge masks

The `Merge masks` tab is meant to support collaborative mapping. It allows you to split the mapping work between yourself and a colleague.

<img src="https://github.com/michelelissoni/QClassiPy/blob/main/docs/images/merge_masks.png" height="300"> 

1. Create a tile list and a mask raster using the `Create tiles` tab.
2. Make a copy of the list and the raster and send them to a colleague. Choose which regions each of you will map.
3. Map your assigned tiles and mark them as "Complete". Your colleague will do the same. At the end, you will have two lists with different Complete tiles and two rasters where different parts have been mapped.
4. Retrieve the list file and the raster file from your colleague. Load your list file as List 1 and your colleague's file as List 2. You can use the `Update mask path` buttons to set the correct file path for your system.
5. Choose the path of the final tile list and the final mask. Click `MERGE`.
6. In the new raster, the areas that were marked as Complete in List 1 are now equal to the corresponding Map 1, and the same for List 2. In areas where both lists were marked as Complete, or Incomplete, the raster will have the same values as Map 1.
