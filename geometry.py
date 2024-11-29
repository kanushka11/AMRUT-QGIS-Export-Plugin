
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
    QgsMapLayer,
    QgsGeometry,
    QgsProcessingFeedback,
    QgsSpatialIndex, 
    QgsPalLayerSettings, 
    QgsTextFormat, 
    QgsVectorLayerSimpleLabeling
)
from qgis.core import QgsMessageLog, Qgis

import processing
import os

def check_geometries_and_extents(layers):
    """Check for invalid geometries and ensure layer extents overlap."""
    invalid_geometries = []
    all_extents = []
    valid = True

    for i, layer in enumerate(layers):
        if layer.type() == QgsVectorLayer.VectorLayer:
            for feature in layer.getFeatures():
                if not feature.geometry().isGeosValid():
                    invalid_geometries.append((layer.name(), feature.id()))
                    valid = False
            all_extents.append(layer.extent())

    combined_extent = QgsRectangle()
    for extent in all_extents:
        combined_extent.combineExtentWith(extent)

    if combined_extent.isEmpty():
        valid = False
        raise Exception("No overlapping extents found among layers.")

    if invalid_geometries:
        valid = False
        msg = "Invalid geometries detected:\n" + "\n".join(
            [f"Layer: {layer}, Feature ID: {fid}" for layer, fid in invalid_geometries]
        )
        raise Exception(msg)

    return valid

def check_polygon_in_a_layer(layer) :
    valid = True
    invalid_geometries = []
    geometry_type = QgsWkbTypes.flatType(layer.wkbType())
    if geometry_type == QgsWkbTypes.MultiPolygon or geometry_type == QgsWkbTypes.Polygon :
            for feature in layer.getFeatures():
                if not feature.geometry().isGeosValid():
                    invalid_geometries.append((layer.name(), feature.id()))
                    valid = False
    else :
        raise Exception("The grid / segmentation Layer should be of type : Polygon")
    
    if invalid_geometries :
        valid = False
        msg = "Invalid geometries detected:\n" + "\n".join(
            [f"Layer: {layer}, Feature ID: {fid}" for layer, fid in invalid_geometries]
        )
        raise Exception(msg)
    
    return valid

def deep_copy_layer(original_layer):
    """
    Creates a deep copy of the selected layer.
    
    :param original_layer: QgsVectorLayer to be copied.
    :return: QgsVectorLayer - A new layer containing a copy of the original layer.
    """
    if not original_layer.isValid():
        raise ValueError("Invalid layer provided for deep copy.")

    # Get the geometry type and CRS of the original layer
    geometry_type = QgsWkbTypes.displayString(original_layer.wkbType())
    crs = original_layer.crs().authid()  # Get CRS in 'EPSG:XXXX' format

    # Create a new in-memory layer with the same geometry type and CRS
    new_layer = QgsVectorLayer(f"{geometry_type}?crs={crs}", f"Copy of {original_layer.name()}", "memory")
    provider = new_layer.dataProvider()

    # Copy the attribute fields from the original layer
    fields = original_layer.fields()
    provider.addAttributes(fields)
    new_layer.updateFields()

    # Copy all features from the original layer
    features = original_layer.getFeatures()
    copied_features = []
    for feature in features:
        new_feature = QgsFeature(feature)  # Deep copy of the feature
        copied_features.append(new_feature)
    provider.addFeatures(copied_features)
    new_layer.updateExtents()

    return new_layer

def validate_layer(layer):
    """
    Validate a QgsVectorLayer and return any issues found.

    :param layer: QgsVectorLayer to validate.
    :return: List of error messages or empty list if valid.
    """
    errors = []

    # Check if the layer is valid
    if not layer.isValid():
        errors.append("The layer is not valid. Check the file path or data source.")
        return errors
    else :
        QgsMessageLog.logMessage('Layers valid : '+ str(layer.name()), 'AMRUT_Export', Qgis.Info)

    # Check CRS validity
    if layer.crs().isValid():
        crs = layer.crs().authid()
    else:
        errors.append("The layer's CRS is invalid or not defined.")
        crs = "Undefined"

    # Check for features
    features = list(layer.getFeatures())
    if not features:
        errors.append("The layer contains no features.")

    # Check feature geometries
    for i, feature in enumerate(features):
        geom = feature.geometry()
        if geom is None or geom.isEmpty():
            errors.append(f"Feature ID {feature.id()} has no geometry.")
        elif not geom.isGeosValid():
            errors.append(f"Feature ID {feature.id()} has an invalid geometry.")

        # Check for 'id' attribute
        if feature.id() == -1:  # Check if the feature ID is invalid
            print("Feature ID is null or invalid.")

    # Check attribute fields
    if not layer.fields():
        errors.append("The layer contains no attribute fields.")
    else:
        for field in layer.fields():
            if not field.name():
                errors.append("A field has an empty name.")
            if field.type() == QVariant.Invalid:
                errors.append(f"Field '{field.name()}' has an invalid type.")


    return errors


def getExtent(layers):
    all_extents = []

    # Collect extents of vector layers
    for i, layer in enumerate(layers):
        if layer.type() == QgsMapLayer.VectorLayer:  # Correct layer type check
            all_extents.append(layer.extent())

    # Combine extents
    if all_extents:  # Ensure there are extents to combine
        combined_extent = all_extents[0]
        for extent in all_extents[1:]:
            combined_extent.combineExtentWith(extent)
        return combined_extent
    else:
        return QgsRectangle()  # Return an empty extent if no layers are valid


