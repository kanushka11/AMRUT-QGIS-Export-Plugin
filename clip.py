from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, QVariant,Qt
from qgis.PyQt.QtGui import QIcon, QFont
from qgis.PyQt.QtWidgets import QAction, QFileDialog, QMessageBox, QProgressDialog
from qgis.core import (
    QgsProcessingFeatureSourceDefinition,
    QgsVectorLayer,
    QgsRasterLayer,
    QgsWkbTypes,
    QgsProject,
    QgsRectangle,
    QgsField,
    QgsFeature,
    QgsGeometry,
    QgsProcessingFeedback,
    QgsSpatialIndex, 
    QgsPalLayerSettings, 
    QgsTextFormat, 
    QgsVectorLayerSimpleLabeling
)
import processing
import os



def clip_layers_to_grid(grid_layer, layers, output_base_dir, progress_signal):
    """Clip all layers by grid cells with a progress dialog."""
    feedback = QgsProcessingFeedback()

    # Create the output directory if it doesn't exist
    if not os.path.exists(output_base_dir):
        os.makedirs(output_base_dir)


    for i, feature in enumerate(grid_layer.getFeatures()):
        current_step = i
        progress_signal.emit(current_step)


        grid_cell_geom = feature.geometry()
        grid_cell_id = feature["id"]

        if not grid_cell_geom or not grid_cell_geom.isGeosValid():
            QMessageBox.warning(None, "Invalid Geometry", f"Skipping grid cell {grid_cell_id} due to invalid geometry.")
            continue

        grid_dir = os.path.join(output_base_dir, f"grid_{grid_cell_id}")
        if not os.path.exists(grid_dir):
            os.makedirs(grid_dir)

        temp_layer = QgsVectorLayer(
            "Polygon?crs={}".format(grid_layer.crs().authid()), 
            f"grid_cell_{grid_cell_id}", "memory"
        )
        temp_layer_data = temp_layer.dataProvider()
        temp_layer_data.addAttributes(grid_layer.fields())
        temp_layer.updateFields()

        temp_feature = QgsFeature()
        temp_feature.setGeometry(grid_cell_geom)
        temp_feature.setAttributes(feature.attributes())
        temp_layer_data.addFeatures([temp_feature])
        temp_layer.updateExtents()

        clipped_layers = {
            "Point": [],
            "Line": [],
            "Polygon": []
        }

        for layer in layers:
            if layer.type() == QgsVectorLayer.VectorLayer:  # Handle vector layers
                geometry_type = QgsWkbTypes.flatType(layer.wkbType())
                output_path = os.path.join(grid_dir, f"{layer.name()}_clipped.geojson")
                clip_params = {
                    'INPUT': layer,
                    'OVERLAY': temp_layer,
                    'OUTPUT': output_path
                }
                try:
                    processing.run("qgis:clip", clip_params, feedback=feedback)
                    if geometry_type == QgsWkbTypes.MultiPoint or geometry_type == QgsWkbTypes.Point:
                        clipped_layers["Point"].append(output_path)
                    elif geometry_type == QgsWkbTypes.MultiLineString or geometry_type == QgsWkbTypes.LineString:
                        clipped_layers["Line"].append(output_path)
                    elif geometry_type == QgsWkbTypes.MultiPolygon or geometry_type == QgsWkbTypes.Polygon:
                        clipped_layers["Polygon"].append(output_path)
                except Exception as e:
                    QMessageBox.warning(None, "Error", f"Error clipping vector layer '{layer.name()}' with grid cell {grid_cell_id}: {e}")
        
            elif layer.type() == QgsRasterLayer.RasterLayer:  # Handle raster layers
                output_path = os.path.join(grid_dir, f"{layer.name()}_clipped.tif")
                clip_params = {
                    'INPUT': layer.source(),
                    'MASK': temp_layer,
                    'OUTPUT': output_path,
                    'NODATA': -9999  # Define nodata value if needed
                }
                try:
                    processing.run("gdal:cliprasterbymasklayer", clip_params, feedback=feedback)
                except Exception as e:
                    QMessageBox.warning(None, "Error", f"Error clipping raster layer '{layer.name()}' with grid cell {grid_cell_id}: {e}")
        
        geometry_output_files = {
            "Point": os.path.join(grid_dir, "point.geojson"),
            "Line": os.path.join(grid_dir, "line.geojson"),
            "Polygon": os.path.join(grid_dir, "polygon.geojson")
        }
        for geometry_type, layer_paths in clipped_layers.items():
            if layer_paths :
                merge_clipped_layers(layer_paths, geometry_output_files[geometry_type], geometry_type, "EPSG:4326")

        for geometry_type, layer_paths in clipped_layers.items() :
            removeFiles(layer_paths)

        

        

def merge_clipped_layers (layers_path, merged_layer_path, geometry_type,crs) : 
    feedback = QgsProcessingFeedback()
    merge_params = {
            'LAYERS': layers_path,
            'CRS': crs,
            'OUTPUT': merged_layer_path
    }
    try:
            processing.run("qgis:mergevectorlayers", merge_params, feedback = feedback)
    except Exception as e:
            QMessageBox.warning(None, "Error", f"Error merging {geometry_type} layers: {e}")

def removeFiles(filePaths) :
    for file_path in filePaths:
        try:
            os.remove(file_path)
        except Exception as e:
            raise Exception(f"Error deleting {file_path}: {e}")


def check_geometries_and_extents(layers):
    """Check for invalid geometries and ensure layer extents overlap."""
    invalid_geometries = []
    all_extents = []


    for i, layer in enumerate(layers):
        if layer.type() == QgsVectorLayer.VectorLayer:
            for feature in layer.getFeatures():
                if not feature.geometry().isGeosValid():
                    invalid_geometries.append((layer.name(), feature.id()))
            all_extents.append(layer.extent())

    combined_extent = QgsRectangle()
    for extent in all_extents:
        combined_extent.combineExtentWith(extent)

    if combined_extent.isEmpty():
        raise Exception("No overlapping extents found among layers.")

    if invalid_geometries:
        msg = "Invalid geometries detected:\n" + "\n".join(
            [f"Layer: {layer}, Feature ID: {fid}" for layer, fid in invalid_geometries]
        )
        raise Exception(msg)

    return combined_extent

def drop_empty_grids(grid_layer, layers, feedback=None):
    """Remove grids that do not intersect any features."""
    provider = grid_layer.dataProvider()
    features_to_remove = []
    total_grids = grid_layer.featureCount()
    grid_index = QgsSpatialIndex(grid_layer)  # Use spatial index for faster checks

    for i, grid_feature in enumerate(grid_layer.getFeatures()):
        if feedback:
            feedback.setProgress(int((i / total_grids) * 100))
        if feedback and feedback.isCanceled():
            break

        grid_geom = grid_feature.geometry()
        intersects = False

        # Check intersection using spatial indexing
        for layer in layers:
            if layer.type() == QgsVectorLayer.VectorLayer:
                spatial_index = QgsSpatialIndex(layer)
                intersecting_ids = spatial_index.intersects(grid_geom.boundingBox())
                if intersecting_ids:
                    intersects = True
                    break

        if not intersects:
            features_to_remove.append(grid_feature.id())

    # Remove empty grids
    if features_to_remove:
        provider.deleteFeatures(features_to_remove)

    grid_layer.updateExtents()


