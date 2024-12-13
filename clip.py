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
    QgsVectorFileWriter,
    QgsField,
    QgsFeature,
    QgsGeometry,
    QgsProcessingFeedback,
    QgsSpatialIndex, 
    QgsPalLayerSettings, 
    QgsTextFormat, 
    QgsVectorLayerSimpleLabeling,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsProject

)
import processing
import os
import time
from datetime import datetime
import csv
import subprocess
import shutil
import json
from . import rename_tiles as tiles



def clip_layers_to_grid(grid_layer, layers, output_base_dir, progress_signal):
    """Clip all layers by grid cells with a progress dialog."""
    feedback = QgsProcessingFeedback()

    # Create the output directory if it doesn't exist
    if not os.path.exists(output_base_dir):
        os.makedirs(output_base_dir)
    csv_file_path = os.path.join(output_base_dir, "grid_data.csv")

    with open(csv_file_path, mode='w', newline='', encoding='utf-8') as csv_file:
        csv_writer = csv.writer(csv_file)
        csv_writer.writerow(["grid_name", "creation_date", "assigned_to_surveyor", "submission_date"])

    for i, feature in enumerate(grid_layer.getFeatures()):
        current_step = i



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
        create_html_file(temp_layer,grid_dir, grid_layer.crs())

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
                tile_output_dir = os.path.join(grid_dir, "tiles")
                reprojected_raster = os.path.join(grid_dir, f"{layer.name()}_reproject.tif")

                clip_params = {
                    'INPUT': layer.source(),
                    'MASK': temp_layer,
                    'OUTPUT': output_path,
                    'NODATA': -9999  # Define nodata value if needed
                }
                try:
                    processing.run("gdal:cliprasterbymasklayer", clip_params, feedback=feedback)
                    if not os.path.exists(tile_output_dir):
                        os.makedirs(tile_output_dir)
                    params = {
                        'INPUT': output_path,
                        'TARGET_CRS': 'EPSG:3857',
                        'RESOLUTION': 0.0001,
                        'OUTPUT': reprojected_raster
                    }
                    processing.run("gdal:warpreproject", params, feedback = feedback)
                    params = {
                        'INPUT': reprojected_raster,  # Input raster file path
                        'OUTPUT': tile_output_dir,  # Output tile directory
                        'MIN_ZOOM_LEVEL': 16,
                        'MAX_ZOOM_LEVEL': 21, # Adjust zoom levels as needed
                        'TILE_FORMAT': 'png',  # Adjust format if needed
                        'RESAMPLING': 0,  # Default is nearest neighbor (adjust if needed)
                        'TMS_CONVENTION': True,  # Use TMS-compatible tiles (flipped Y-coordinate)
                        'PROFILE': 0,  # Mercator profile
                        'WEB_VIEWER': 'none',  # Generates OpenLayers web viewer files
                    }

                    processing.run("gdal:gdal2tiles", params, feedback=feedback)

                    tiles.rename_tiles(tile_output_dir)
                    remove_files([output_path, reprojected_raster])
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
            remove_files(layer_paths)

        with open(csv_file_path, mode='a', newline='', encoding='utf-8') as csv_file:
            csv_writer = csv.writer(csv_file)
            csv_writer.writerow([
                f"grid_{grid_cell_id}",
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "",  # Assigned to surveyor (empty)
                ""  # Submission date (empty)
            ])

        # Define a unique archive name separate from the directory
        archive_name = os.path.join(grid_dir, f"grid_{grid_cell_id}")
        create_archive(grid_dir,archive_name)
        progress_signal.emit(current_step)

def create_kml_file(layer, grid_dir, crs) :
    kml_file_path = os.path.join(grid_dir, f"location.kml")
    options = QgsVectorFileWriter.SaveVectorOptions()
    QgsVectorFileWriter.writeAsVectorFormat(
        layer,
        kml_file_path,
        "utf-8",
        crs,
        "KML"
    )


def create_html_file(layer, grid_dir, crs):
    """
    Creates an HTML file with a script that redirects to Google Maps for the polygon feature.
    """
    html_file_path = os.path.join(grid_dir, f"location.html")
    json_file_path = os.path.join(grid_dir, "metadata.json")
    target_crs = QgsCoordinateReferenceSystem("EPSG:4326")
    transform = QgsCoordinateTransform(crs, target_crs, QgsProject.instance())
    # Get the geometry of the first feature (assuming only one feature per layer)
    layer.startEditing()
    feature = next(layer.getFeatures(), None)
    layer.commitChanges()

    if not feature:
        raise ValueError("No feature found in the layer.")

    geometry = feature.geometry()

    if geometry.isEmpty():
        raise ValueError("Geometry is empty.")

    # Extract the centroid of the polygon as latitude and longitude
    geometry.transform(transform)

    # Extract the centroid of the polygon as latitude and longitude
    centroid = geometry.centroid().asPoint()
    latitude, longitude = centroid.y(), centroid.x()

    # Write the HTML file
    html_content = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Polygon Location</title>
            <script>
                // Google Maps URL with latitude and longitude
                const googleMapsUrl = "https://www.google.com/maps?q={latitude},{longitude}";
    
                // Redirect to the Google Maps URL when the page loads
                window.onload = () => {{
                    window.location.href = googleMapsUrl;
                }};
            </script>
        </head>
        <body>
            <p>If you are not redirected automatically, click <a href="https://www.google.com/maps?q={latitude},{longitude}">here</a>.</p>
        </body>
        </html>
        """
    #metadata Json
    bounding_box = geometry.boundingBox()
    bounding_box_dict = {
        "north": bounding_box.yMaximum(),
        "south": bounding_box.yMinimum(),
        "east": bounding_box.xMaximum(),
        "west": bounding_box.xMinimum()
    }

    # Write the bounding box to a JSON file
    with open(json_file_path, 'w', encoding='utf-8') as json_file:
        json.dump(bounding_box_dict, json_file, indent=4)

    # Save the HTML file
    with open(html_file_path, 'w', encoding='utf-8') as html_file:
        html_file.write(html_content)


        

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

def close_files (file_paths) :
    for file_path in file_paths :
        file = open(file_path, "r+")
        file.close()

def remove_files(file_paths) :
    for file_path in file_paths:
        retries = 5  # Number of retries to delete the file
        while retries > 0:
            try:
                os.remove(file_path)
                break
            except PermissionError:
                retries -= 1
                time.sleep(0.5)  # Wait for 500ms before retrying
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

def create_archive (grid_dir, archive_name) :
    try :
        files_to_compress = []
        tiles_dir = None
        for root, dirs, files in os.walk(grid_dir):
            for file in files:
                if file != "location.html":
                    files_to_compress.append(os.path.join(root, file))
            if "tiles" in dirs:
                tiles_dir = os.path.join(root, "tiles")
            # Create a temporary directory for archiving
        temp_archive_dir = os.path.join(grid_dir, f"temp_archive")
        if not os.path.exists(temp_archive_dir):
            os.makedirs(temp_archive_dir)

        for file_path in files_to_compress:
            relative_path = os.path.relpath(file_path, grid_dir)
            dest_path = os.path.join(temp_archive_dir, relative_path)
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            shutil.copy(file_path, dest_path)

        # Compress files to .zip
        shutil.make_archive(archive_name, 'zip', temp_archive_dir)

        # Rename .zip to .amrut
        amrut_file = f"{archive_name}.amrut"
        os.rename(f"{archive_name}.zip", amrut_file)

        # Cleanup temporary archive directory
        shutil.rmtree(temp_archive_dir)

        # Remove original files (except location.html)
        remove_files(files_to_compress)

        # Remove tiles directory
        if tiles_dir and os.path.exists(tiles_dir):
            shutil.rmtree(tiles_dir)

    except Exception as e:
        QMessageBox.warning(None, "Error", f"Error creating .amrut archive for grid : {e}")

