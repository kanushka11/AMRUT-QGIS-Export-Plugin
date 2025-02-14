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
