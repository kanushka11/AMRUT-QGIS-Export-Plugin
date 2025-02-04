from qgis.core import (
    QgsVectorFileWriter,
    QgsVectorLayer,
    QgsProject,
    QgsFeature,
    QgsGeometry,
    QgsFields,
    QgsField,
    QgsWkbTypes,
    QgsCoordinateReferenceSystem
)
from PyQt5.QtCore import QVariant
import os

def process_temp_layer(layer_name) :
    original_layer = QgsProject.instance().mapLayersByName(layer_name)[0]
    temporary_layer = QgsProject.instance().mapLayersByName(f"Temporary_{layer_name}")[0]
    if not original_layer:
        raise Exception(f"No layer named {layer_name} found in the project to compare with.")


