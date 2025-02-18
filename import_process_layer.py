from qgis.core import (
    QgsProject, QgsProcessingFeedback, QgsProcessingContext, QgsRasterLayer, QgsMessageLog, Qgis
)
import processing


def process_temp_layer(layer_name):
    original_layer = QgsProject.instance().mapLayersByName(layer_name)[0]
    temporary_layer = QgsProject.instance().mapLayersByName(f"Temporary_{layer_name}")[0]
    original_layer.setSubsetString("")
    temporary_layer.setSubsetString("")

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
    
    # Iterate over feature groups
    for feature_id, features in feature_map.items():
        print(f"Feature ID: {feature_id}, Number of Features: {len(features)}")
        
        if len(features) > 1:
            # Extract field names excluding 'feature_id' (primary key)
            field_names = [field.name() for field in temporary_layer.fields() if field.name() not in ["fid", "feature_id"]]
            
            # Convert all feature attributes (excluding feature_id) to a set of tuples
            unique_values = {tuple(feature[attr] for attr in field_names) for feature in features}
            
            # If there's more than one unique value set, add to split_feature_map
            if len(unique_values) > 1:
                split_feature_map[feature_id] = features

    return split_feature_map




