
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
    QgsVectorFileWriter,
    QgsProcessingFeedback,
    QgsSpatialIndex, 
    QgsPalLayerSettings, 
    QgsTextFormat, 
    QgsVectorLayerSimpleLabeling,
    QgsVectorDataProvider,
    QgsRectangle,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsVectorLayerUtils
)
from qgis.PyQt.QtGui import QIcon, QFont
from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, QVariant,Qt
from qgis.PyQt.QtWidgets import QAction, QFileDialog, QMessageBox, QProgressDialog
from .import export_geometry as geometry
import os
import uuid

def create_grid_layer(bbox, grid_size, crs):
    """Create a 500m x 500m grid covering the bounding box."""
    xmin, ymin, xmax, ymax = bbox
    grid_layer = QgsVectorLayer("Polygon?crs={}".format(crs), "Grid", "memory")
    provider = grid_layer.dataProvider()

    # Define the fields for the layer
    provider.addAttributes([QgsField("id", QVariant.Int)])
    grid_layer.updateFields()

    grid_cells = []
    cell_id = 0
    x = xmin
    while x < xmax:
        y = ymin
        while y < ymax:
            # Create the grid cell as a rectangle
            rect = QgsRectangle(x, y, x + grid_size, y + grid_size)
            feature = QgsFeature()
            feature.setGeometry(QgsGeometry.fromRect(rect))
            feature.setAttributes([cell_id])
            grid_cells.append(feature)
            y += grid_size
            cell_id += 1
        x += grid_size

    # Add the features (grid cells) to the layer
    provider.addFeatures(grid_cells)
    grid_layer.updateExtents()
    add_grid_labels(grid_layer)

    return grid_layer

def add_grid_labels(grid_layer):
    """Add labels to the grid layer, showing grid cell IDs."""
    if not isinstance(grid_layer, QgsVectorLayer):
        raise TypeError("grid_layer must be a QgsVectorLayer.")

    # Step 1: Initialize label settings
    label_settings = QgsPalLayerSettings()
    label_settings.fieldName = "id"  # Field to use for labeling (e.g., grid cell ID)
    label_settings.placement = QgsPalLayerSettings.OverPoint  # Label placement over the grid cells

    # Step 2: Configure text format (font, size, etc.)
    text_format = QgsTextFormat()
    text_format.setFont(QFont("Arial", 10))  # Use desired font and size
    text_format.setSize(10)  # Font size for labels
    label_settings.setFormat(text_format)

    # Step 3: Assign the labeling settings to the layer
    labeling = QgsVectorLayerSimpleLabeling(label_settings)  # Create a labeling object
    grid_layer.setLabeling(labeling)  # Assign labeling configuration to the layer
    grid_layer.setLabelsEnabled(True)  # Enable labels for the grid layer

    # Step 4: Refresh the layer to apply the changes
    grid_layer.triggerRepaint()

def create_grid_within_single_polygon(selectedLayers,polygon_layer, grid_size, crs):
    """
    Create a grid covering only a single polygon geometry.

    :param polygon_layer: QgsVectorLayer containing one polygon geometry.
    :param grid_size: Size of the grid cells (e.g., 500 for 500m x 500m).
    :param crs: CRS for the output grid layer (default EPSG:32644).
    :return: QgsVectorLayer with the generated grid.
    """
    try:
        error = geometry.validate_layer(polygon_layer)
        if error :
            msg = "Error :\n" + "\n".join( [f"{error_msg}" for error_msg in error])
            raise Exception(msg)
        
        if not polygon_layer.isValid():
            raise ValueError("Invalid polygon layer provided")

        # Extract the polygon geometry
        features = list(polygon_layer.getFeatures())
        if len(features) != 1:
            raise ValueError("Layer must contain exactly one polygon feature")
        polygon_geom = features[0].geometry()

        if polygon_geom is None or polygon_geom.isEmpty():
            raise ValueError("Polygon geometry is empty or invalid")

        # Generate the grid cells and clip them to the polygon geometry
        combined_extent_of_selected_layers = geometry.getExtent(selectedLayers)
        extent_of_polygon_layer = geometry.getExtent([polygon_layer])
        if not extent_of_polygon_layer.contains(combined_extent_of_selected_layers) :
            raise Exception("Error : Selected Layer(s) extent is greater than that of AOI/ ROI Layer")

        grid_layer = create_grid_layer(extent_of_polygon_layer.toRectF().getCoords(),grid_size, crs)

        polygon_crs = polygon_layer.crs()
        grid_crs = grid_layer.crs()
        if polygon_crs != grid_crs:
            transform = QgsCoordinateTransform(polygon_crs, grid_crs, QgsProject.instance())
            polygon_geom.transform(transform)
        
        unique_id = str(uuid.uuid4())
        clipped_grid_layer = QgsVectorLayer("Polygon?crs={}".format(crs), unique_id, "memory")

        provider = clipped_grid_layer.dataProvider()
        provider.addAttributes(grid_layer.fields())
        clipped_grid_layer.updateFields()

        for grid_feature in grid_layer.getFeatures():
            grid_geom = grid_feature.geometry()
            if grid_geom.intersects(polygon_geom):
                clipped_geom = grid_geom.intersection(polygon_geom)
                if not clipped_geom.isEmpty():
                    clipped_feature = QgsFeature()
                    clipped_feature.setGeometry(clipped_geom)
                    clipped_feature.setAttributes(grid_feature.attributes())
                    provider.addFeature(clipped_feature)

        clipped_grid_layer.updateExtents()
        error = geometry.validate_layer(clipped_grid_layer)
       
        if not error :
            file_path = getFilePath(unique_id)
            save_file_to_disk(layer = clipped_grid_layer, file_path=file_path)
            saved_grid_layer =  QgsVectorLayer(file_path + ".gpkg", unique_id, "ogr")
            QgsProject.instance().addMapLayer(saved_grid_layer)
            return unique_id
        else :
            msg = "Error :\n" + "\n".join( [f"{error_msg}" for error_msg in error])
            raise Exception(msg)

    except Exception as e:
        raise Exception(f"Error during grid creation: {str(e)}")

def getFilePath(file_name) :
    project = QgsProject.instance()

# Get the project file path (if it's saved)
    project_file_path = project.fileName()

    # Get the directory where the project file is located
    project_directory = os.path.dirname(project_file_path) if project_file_path else os.path.expanduser("~")
    
    # Ensure the directory exists
    if not os.path.exists(project_directory):
        os.makedirs(project_directory)

    
    return os.path.join(project_directory, file_name)

def save_file_to_disk (file_path, layer) :
    options = QgsVectorFileWriter.SaveVectorOptions()

# Set the CRS transformation context (optional)
    error = QgsVectorFileWriter.writeAsVectorFormatV2(
        layer=layer,
        fileName = file_path,
        transformContext= QgsProject.instance().transformContext(),
        options =options,  
    )

