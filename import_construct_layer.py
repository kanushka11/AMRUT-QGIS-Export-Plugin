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
import zipfile
import json
import tempfile
import processing

merged_layer = None

def construct_layer(directory, amrut_files, layer_name):
    global merged_layer
    init_merged_layer(layer_name)
    layers_to_merge = []

    for amrut_file in amrut_files:
        amrut_path = os.path.join(directory, amrut_file)
        print(f"Constructing Layer for {layer_name} , thus Reading File : {amrut_path}")
        # Open the .amrut file as a ZIP archive
        with zipfile.ZipFile(amrut_path, 'r') as zip_ref:
            # Check if layer exists in the archive
            layer_file_name = f"{layer_name}.geojson"
            if  layer_file_name not in zip_ref.namelist():
                return False, f"Layer not found in {amrut_file}"

            geojson_data = zip_ref.read(layer_file_name).decode('utf-8')
            temp_dir = tempfile.gettempdir()
            temp_geojson_file_path = os.path.join(temp_dir, f"Temporary_{layer_file_name}")
            print(f"Reading layer from mobile : {temp_geojson_file_path}")
            # GeoJSON data to the temporary file
            with open(temp_geojson_file_path, 'w', encoding='utf-8') as temp_geojson_file:
                temp_geojson_file.write(geojson_data)

            geojson_layer = QgsVectorLayer(temp_geojson_file_path, layer_name, "ogr")
            layers_to_merge.append(geojson_layer)


    merge_layers(layers_to_merge)
    saved_layer_path = save_temporary_layer(layer_name)
    print(f"Merged layer feature count: {merged_layer.featureCount()}")


    return True, saved_layer_path  # Successfully validated, return layer map

def init_merged_layer(layer_name) :
    global merged_layer
    print(f"Init merger layer for {layer_name}")
    active_layer = QgsProject.instance().mapLayersByName(layer_name)[0]
    if not active_layer:
        raise Exception(f"No layer named {layer_name} found in the project")
    geometry_type = active_layer.wkbType()
    geometry_str = QgsWkbTypes.displayString(geometry_type).split(" ")[0]
    crs = QgsCoordinateReferenceSystem("EPSG:4326")
    layer_uri = f"{geometry_str}?crs={crs.authid()}"
    merged_layer = QgsVectorLayer(layer_uri, f"Temporary_{layer_name}", "memory")

def merge_layers(layers_to_merge):
    global merged_layer
    parameters = {
        'LAYERS': layers_to_merge,
        'CRS': QgsCoordinateReferenceSystem("EPSG:4326"),
        'OUTPUT': 'memory:'  # Keep it in memory
    }
    merged_layer = processing.run("native:mergevectorlayers", parameters)['OUTPUT']
    if not merged_layer or not merged_layer.isValid():
        raise Exception("Merging layers failed.")


def save_temporary_layer(layer_name):
    global merged_layer
    project_path = QgsProject.instance().homePath()  # Gets the root project directory
    temporary_layer_path = os.path.join(project_path, f"{layer_name}_vetted.gpkg")
    save_file_to_disk(temporary_layer_path, merged_layer)

    return temporary_layer_path

def save_file_to_disk (file_path, layer) :
    options = QgsVectorFileWriter.SaveVectorOptions()

# Set the CRS transformation context (optional)
    error = QgsVectorFileWriter.writeAsVectorFormatV2(
        layer=layer,
        fileName = file_path,
        transformContext= QgsProject.instance().transformContext(),
        options =options,
    )


