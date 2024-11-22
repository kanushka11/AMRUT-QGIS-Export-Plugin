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

# Initialize Qt resources from file resources.py
from .resources import *
# Import the code for the dialog
from .export_dialog import ClipMergeExportDialog

# Initialize Qt resources from file resources.py
from .resources import *
# Import the code for the dialog
from .export_dialog import ClipMergeExportDialog
import os.path
class ClipMergeExport:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'ClipMergeExport_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&ClipMergeExport')

        # Check if plugin was started the first time in current QGIS session
        # Must be set in initGui() to survive plugin reloads
        self.first_start = None

    def tr(self, message):
        """Get the translation for a string using Qt translation API."""
        return QCoreApplication.translate('ClipMergeExport', message)

    def add_action(self, icon_path, text, callback, enabled_flag=True, add_to_menu=True, add_to_toolbar=True, status_tip=None, whats_this=None, parent=None):
        """Add a toolbar icon to the toolbar."""
        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.iface.addToolBarIcon(action)

        if add_to_menu:
            self.iface.addPluginToMenu(self.menu, action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""
        icon_path = ':/plugins/export/icon.png'
        self.add_action(icon_path, text=self.tr(u'Clip and Export'), callback=self.run, parent=self.iface.mainWindow())

        # will be set False in run()
        self.first_start = True

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(self.tr(u'&ClipMergeExport'), action)
            self.iface.removeToolBarIcon(action)

    def run(self):
        """Run the plugin to process all layers."""
        layers = [layer for layer in QgsProject.instance().mapLayers().values() if layer.isValid()]

        # Initialize progress dialog
        progress_dialog = QProgressDialog("Processing...", "Cancel", 0, 100)
        progress_dialog.setMinimumSize(300, 100)
        progress_dialog.setWindowModality(Qt.WindowModal)
        progress_dialog.show()

        # Feedback object for long operations
        feedback = QgsProcessingFeedback()

        # Step 1: Validate geometries and check extents
        progress_dialog.setLabelText("Validating layers...")
        try:
            combined_extent = check_geometries_and_extents(layers)
        except Exception as e:
            QMessageBox.critical(None, "Error", str(e))
            progress_dialog.close()
            return

        if progress_dialog.wasCanceled():
            QMessageBox.warning(None, "Process Canceled", "The process was canceled.")
            progress_dialog.close()
            return

        # Step 2: Create a grid
        progress_dialog.setLabelText("Creating grid...")
        grid_layer = create_500m_grid(combined_extent.toRectF().getCoords())
        add_grid_labels(grid_layer)
        QgsProject.instance().addMapLayer(grid_layer)

        # Step 3: Drop empty grids

       

        # Step 5: Clip layers
        progress_dialog.setLabelText("Clipping layers...")
        output_base_dir = '/home/shubhangam/Documents/grids'
        try:
            clip_layers_to_grid(grid_layer, layers, output_base_dir, progress_dialog)
        except Exception as e:
            QMessageBox.critical(None, "Clipping Error", str(e))
            progress_dialog.close()
            return

        progress_dialog.close()
        QMessageBox.information(None, "Success", "Export complete!")



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

