
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
from qgis.PyQt.QtGui import QIcon, QFont
from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, QVariant,Qt
from qgis.PyQt.QtWidgets import QAction, QFileDialog, QMessageBox, QProgressDialog

def create_500m_grid(bbox, grid_size=500, crs='EPSG:32644'):
    """Create a 500m x 500m grid covering the bounding box."""
    xmin, ymin, xmax, ymax = bbox
    grid_layer = QgsVectorLayer("Polygon?crs={}".format(crs), "500m Grid", "memory")
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