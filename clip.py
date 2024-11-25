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



def clip_layers_to_grid(grid_layer, layers, output_base_dir, progress_dialog):
    """Clip all layers by grid cells with a progress dialog."""
    feedback = QgsProcessingFeedback()

    # Create the output directory if it doesn't exist
    if not os.path.exists(output_base_dir):
        os.makedirs(output_base_dir)

    total_features = grid_layer.featureCount()
    current_progress = 2  # Progress already at 2 steps

    for i, feature in enumerate(grid_layer.getFeatures()):
        current_step = current_progress + i
        progress_dialog.setValue(current_step)
        progress_dialog.setLabelText(f"Clipping layers for grid cell {i + 1}/{total_features}...")
        if progress_dialog.wasCanceled():
            QMessageBox.warning(None, "Process Canceled", "The clipping process was canceled.")
            break

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

        for layer in layers:
            if layer.type() == QgsVectorLayer.VectorLayer:
                output_path = os.path.join(grid_dir, f"{layer.name()}_clipped.geojson")
                clip_params = {
                    'INPUT': layer,
                    'OVERLAY': temp_layer,
                    'OUTPUT': output_path
                }
                try:
                    processing.run("qgis:clip", clip_params, feedback=feedback)
                except Exception as e:
                    QMessageBox.warning(None, "Error", f"Error clipping layer '{layer.name()}' with grid cell {grid_cell_id}: {e}")

    progress_dialog.setValue(current_progress + total_features)


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


