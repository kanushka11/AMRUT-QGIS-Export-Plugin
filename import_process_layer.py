from qgis.core import (
    QgsProject, QgsProcessingFeedback, QgsProcessingContext, QgsRasterLayer, QgsMessageLog, Qgis
)
import processing


def process_temp_layer(layer_name):
    original_layer = QgsProject.instance().mapLayersByName(layer_name)[0]
    temporary_layer = QgsProject.instance().mapLayersByName(f"Temporary_{layer_name}")[0]

    if not original_layer:
        raise Exception(f"No layer named {layer_name} found in the project to compare with.")

    feature_map = {}  # Dictionary to store feature_id → list of features

    # Iterate over features in the temporary layer
    for feature in temporary_layer.getFeatures():
        feature_id = feature["feature_id"]  # Get the feature_id attribute

        if feature_id not in feature_map:
            feature_map[feature_id] = []  # Initialize list if not present

        feature_map[feature_id].append(feature)  # Append the feature to the list

    split_feature_map = {}
    # Print the feature_map to check grouped features
    for feature_id, features in feature_map.items():
        print(f"Feature ID: {feature_id}, Number of Features: {len(features)}")
        if len(features) > 1:
            split_feature_map[feature_id] = features

    return split_feature_map


def transform_raster_CRS(layer, raster_layer):
    """Create a map canvas to render the given layer."""
    
    remove_layer_by_name(f"Temporary_{raster_layer.name()}")

    # Get the CRS of the grid layer (vector) and raster layer
    grid_crs = layer.crs()
    raster_crs = raster_layer.crs()
    processing_context = QgsProcessingContext()
    feedback = QgsProcessingFeedback()

    # Reproject the clipped raster to the grid CRS
    reproject_params = {
        'INPUT': raster_layer.source(),
        'SOURCE_CRS': raster_crs.authid(),  # Source CRS (from the clipped raster)
        'TARGET_CRS': grid_crs.authid(),    # Target CRS (grid layer CRS)
        'RESAMPLING': 0,                    # Nearest neighbor resampling
        'NODATA': -9999,                    # Specify NoData value if needed
        'OUTPUT': 'TEMPORARY_OUTPUT'        # Output as a temporary layer
    }

    # Run the reprojection algorithm
    transform_result = processing.run("gdal:warpreproject", reproject_params, context=processing_context, feedback=feedback)

    # Get the reprojected raster layer from the result
    reprojected_raster_layer = QgsRasterLayer(transform_result['OUTPUT'], f"Temporary_{raster_layer.name()}")

    # Validate the reprojected raster layer
    if not reprojected_raster_layer.isValid():
        raise Exception("Failed to reproject the raster layer.")

    return reprojected_raster_layer


def remove_layer_by_name(layer_name):
    """Remove a layer from the QGIS project by its name."""
    try:
        for layer in QgsProject.instance().mapLayers().values():
            if layer.name() == layer_name:
                QgsProject.instance().removeMapLayer(layer.id())
                break
        return None
    except Exception as e:
        QgsMessageLog.logMessage(f"Error in remove_layer_by_name: {str(e)}", 'AMRUT', Qgis.Critical)
        return None
