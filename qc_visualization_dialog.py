from PyQt5.QtWidgets import QDialog, QHBoxLayout, QVBoxLayout, QLabel, QApplication, QMessageBox
from PyQt5.QtCore import Qt, QTimer
from qgis.core import QgsProject, QgsVectorLayer, QgsCoordinateTransform, QgsRasterLayer, QgsProcessingFeedback, QgsProcessingContext
from qgis.gui import QgsMapCanvas
from PyQt5.QtGui import QColor
from . import new_feature_choice
from . import verification_dialog 

import zipfile
import tempfile
import os
import processing

class QualityCheckVisualizationDialog(QDialog):
    def __init__(self, parent, selected_layer_name, amrut_file_path, selected_raster_layer_name, grid_extent):
        super().__init__(parent)
        self.selected_layer_name = selected_layer_name
        self.amrut_file_path = amrut_file_path
        self.selected_raster_layer_name = selected_raster_layer_name
        self.grid_extent = grid_extent

        self.setWindowTitle("AMRUT 2.0")
        self.setWindowState(Qt.WindowMaximized)

        # Attributes for map canvases
        self.left_map_canvas = None
        self.right_map_canvas = None
        self.synchronizing = False  # Prevent infinite synchronization loops

        # Main layout
        layout = QHBoxLayout(self)

        # Left panel: Visualization of selected project layer
        layer = self.get_layer_by_name(self.selected_layer_name)
        raster_layer = self.get_layer_by_name(self.selected_raster_layer_name)

        if layer:
            left_panel, self.left_map_canvas = self.create_layer_visualization_panel(layer, f"{self.selected_layer_name} from Project", raster_layer, 0)
        else:
            left_panel = self.create_error_panel(f"Layer '{self.selected_layer_name}' not found.")
        layout.addLayout(left_panel)

        # Add a vertical divider
        self.add_vertical_divider(layout)

        # Right panel: Visualization of GeoJSON from AMRUT file
        if raster_layer:
            right_panel, self.right_map_canvas = self.create_geojson_visualization_panel(raster_layer, 1)
        else:
            right_panel = self.create_error_panel(f"Layer '{self.selected_raster_layer_name}' not found.")
        layout.addLayout(right_panel)

        # Synchronize extents between left and right map canvases
        self.setup_canvas_synchronization()
        
        QTimer.singleShot(1000, self.show_new_feature_dialog)  # Delay in ms before triggering check

    def show_new_feature_dialog(self):
        grid = self.get_layer_by_name("Grid")
        newFeatureFound = verification_dialog.IntroDialog(
            self,
            selected_layer_name=self.selected_layer_name,
            selected_raster_layer_name=self.selected_raster_layer_name,
            grid_extent=grid.extent()
        )

        newFeatureFound.exec_()

    def setup_canvas_synchronization(self):
        """Synchronize extents between the left and right map canvases."""
        if self.left_map_canvas and self.right_map_canvas:
            self.left_map_canvas.extentsChanged.connect(self.sync_extents_to_right)
            self.right_map_canvas.extentsChanged.connect(self.sync_extents_to_left)

    def sync_extents_to_right(self):
        """Sync the extent of the left canvas to the right canvas."""
        if not self.synchronizing:  # Prevent infinite loops
            self.synchronizing = True
            self.right_map_canvas.setExtent(self.left_map_canvas.extent())
            self.right_map_canvas.refresh()
            self.synchronizing = False

    def sync_extents_to_left(self):
        """Sync the extent of the right canvas to the left canvas."""
        if not self.synchronizing:  # Prevent infinite loops
            self.synchronizing = True
            self.left_map_canvas.setExtent(self.right_map_canvas.extent())
            self.left_map_canvas.refresh()
            self.synchronizing = False

    def create_geojson_visualization_panel(self, raster_layer, called_for):
        """Create a panel to visualize the GeoJSON extracted from the AMRUT file."""
        panel_layout = QVBoxLayout()

        # Load GeoJSON from AMRUT file
        geojson_layer = self.load_geojson_from_amrut(self.amrut_file_path, self.selected_layer_name)

        if geojson_layer:
            temporary_layer_name = f"Temporary_{self.selected_layer_name}"
            existing_layer = self.get_layer_by_name(temporary_layer_name)

            if existing_layer:
                QgsProject.instance().removeMapLayer(existing_layer.id())

            geojson_layer.setName(temporary_layer_name)
            QgsProject.instance().addMapLayer(geojson_layer)

            # Create and return the visualization panel
            panel_layout, map_canvas = self.create_layer_visualization_panel(geojson_layer, f"{self.selected_layer_name} from AMRUT File", raster_layer, called_for)
            return panel_layout, map_canvas
        else:
            panel_layout.addWidget(QLabel("GeoJSON layer not found in AMRUT file."))
            return panel_layout, None

    def load_geojson_from_amrut(self, amrut_file_path, layer_name):
        """Extract and load the GeoJSON file from the AMRUT archive."""
        try:
            # Open the AMRUT file (which is a zip)
            with zipfile.ZipFile(amrut_file_path, 'r') as zip_ref:
                geojson_filename = f"{layer_name}.geojson"

                if geojson_filename in zip_ref.namelist():
                    # Extract the GeoJSON content
                    geojson_content = zip_ref.read(geojson_filename).decode('utf-8')

                    # Check if a temporary file with the prefix exists
                    temp_dir = tempfile.gettempdir()
                    temp_geojson_file_path = os.path.join(temp_dir, f"Temporary_{geojson_filename}")

                    # Save the GeoJSON content to the temporary file
                    with open(temp_geojson_file_path, 'w', encoding='utf-8') as temp_geojson_file:
                        temp_geojson_file.write(geojson_content)

                    # Load the GeoJSON into a vector layer using the temporary file path
                    geojson_layer = QgsVectorLayer(temp_geojson_file_path, layer_name, "ogr")

                    if geojson_layer.isValid():
                        return geojson_layer
                    else:
                        raise ValueError(f"GeoJSON layer '{layer_name}' is not valid.")
                else:
                    raise FileNotFoundError(f"GeoJSON file '{geojson_filename}' not found in the AMRUT file.")
        except Exception as e:
            print(f"Error loading GeoJSON: {str(e)}")
            return None

    def get_layer_by_name(self, layer_name):
        """Retrieve a layer from the QGIS project by its name."""
        for layer in QgsProject.instance().mapLayers().values():
            if layer.name() == layer_name:
                return layer
        return None
    
    def remove_layer_by_name(self, layer_name):
        """Remove a layer from the QGIS project by its name."""
        for layer in QgsProject.instance().mapLayers().values():
            if layer.name() == layer_name:
                QgsProject.instance().removeMapLayer(layer.id())
                break
        return None

    def create_layer_visualization_panel(self, layer, title, raster_layer, called_for):
        """Create a panel to visualize a specific project layer."""
        panel_layout = QVBoxLayout()
        
        # Create the label with larger and bold text
        label = QLabel(title)
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("font-size: 12px; font-weight: bold;")  # Set font size and bold style
        
        panel_layout.addWidget(label)
        
        # Create the map canvas and add it to the panel
        map_canvas = self.create_map_canvas(layer, raster_layer, called_for)
        panel_layout.addWidget(map_canvas)

        return panel_layout, map_canvas

    def create_map_canvas(self, layer, raster_layer, called_for):
        """Create a map canvas to render the given layer."""
        try:
            existing_layer = None

            if(called_for == 0):
                # Remove if a clipped and reprojected raster already exists
                self.remove_layer_by_name(f"Temporary_{raster_layer.name()}")
            else:
                # Check if a clipped and reprojected raster already exists
                for lyr in QgsProject.instance().mapLayers().values():
                    if lyr.name() == f"Temporary_{raster_layer.name()}" and isinstance(lyr, QgsRasterLayer):
                        existing_layer = lyr
                        break

            # If the layer exists, reuse it; otherwise, create it
            if existing_layer:
                reprojected_raster_layer = existing_layer
            else:
                # Get the CRS of the grid layer (vector) and raster layer
                grid_crs = layer.crs()
                raster_crs = raster_layer.crs()

                # Transform grid extent to the raster's CRS
                if grid_crs != raster_crs:
                    transform = QgsCoordinateTransform(grid_crs, raster_crs, QgsProject.instance().transformContext())
                    transformed_extent = transform.transformBoundingBox(self.grid_extent)
                else:
                    transformed_extent = self.grid_extent
                    
                # Set up the processing context
                processing_context = QgsProcessingContext()
                feedback = QgsProcessingFeedback()

                # Parameters for clipping the raster
                params = {
                    'INPUT': raster_layer.source(),
                    'PROJWIN': f"{transformed_extent.xMinimum()},{transformed_extent.xMaximum()},"
                            f"{transformed_extent.yMaximum()},{transformed_extent.yMinimum()}",
                    'NODATA': -9999,
                    'OPTIONS': '',
                    'DATA_TYPE': 0,  # Keep original data type
                    'OUTPUT': 'TEMPORARY_OUTPUT'  # Use TEMPORARY_OUTPUT for processing algorithms
                }

                # Run the processing algorithm
                clipped_result = processing.run("gdal:cliprasterbyextent", params, context=processing_context, feedback=feedback)

                # Get the clipped raster layer from the result
                clipped_raster_layer = QgsRasterLayer(clipped_result['OUTPUT'], f"{raster_layer.name()} (Clipped)")

                # Validate the clipped raster layer
                if not clipped_raster_layer.isValid():
                    raise ValueError("Failed to clip the raster layer in memory.")

                # Reproject the clipped raster to the grid CRS
                reproject_params = {
                    'INPUT': clipped_raster_layer.source(),
                    'SOURCE_CRS': raster_crs.authid(),  # Source CRS (from the clipped raster)
                    'TARGET_CRS': grid_crs.authid(),    # Target CRS (grid layer CRS)
                    'RESAMPLING': 0,                    # Nearest neighbor resampling
                    'NODATA': -9999,                    # Specify NoData value if needed
                    'TARGET_RESOLUTION': None,          # Use default resolution
                    'OPTIONS': '',
                    'DATA_TYPE': 0,                     # Keep original data type
                    'TARGET_EXTENT': None,              # Use default extent
                    'TARGET_EXTENT_CRS': None,          # Use default CRS for extent
                    'MULTITHREADING': False,
                    'OUTPUT': 'TEMPORARY_OUTPUT'        # Output as a temporary layer
                }

                # Run the reprojection algorithm
                reprojected_result = processing.run("gdal:warpreproject", reproject_params, context=processing_context, feedback=feedback)

                # Get the reprojected raster layer from the result
                reprojected_raster_layer = QgsRasterLayer(reprojected_result['OUTPUT'], f"Temporary_{raster_layer.name()}")

                # Validate the reprojected raster layer
                if not reprojected_raster_layer.isValid():
                    raise ValueError("Failed to reproject the raster layer.")

                # Add the reprojected raster layer to the project
                QgsProject.instance().addMapLayer(reprojected_raster_layer)

            # Set up the map canvas with layers
            canvas = QgsMapCanvas()
            canvas.setLayers([layer, reprojected_raster_layer])

            # Set extent and background color for canvas
            canvas.setExtent(self.grid_extent)
            canvas.setCanvasColor(QColor("white"))

            # Enable map interactions (zoom and pan)
            canvas.setMouseTracking(True)  # Enable mouse tracking for panning and zooming
            # canvas.setMapUnits(layer.crs().mapUnits())  # Set map units

            canvas.refresh()  # Refresh the canvas to ensure proper visualization

            return canvas

        except Exception as e:
            print(f"Error: {str(e)}")
            return None

    def add_vertical_divider(self, layout):
        """Add a vertical divider to the layout."""
        line = QLabel()
        line.setFixedWidth(1)
        line.setStyleSheet("background-color: black;")
        layout.addWidget(line)

    def closeEvent(self, event):
        """Override closeEvent to remove temporary layers."""
        try:
            # Remove the temporary layers
            temporary_selected_layer_name = f"Temporary_{self.selected_layer_name}"
            temporary_raster_layer_name = f"Temporary_{self.selected_raster_layer_name}"

            self.remove_layer_by_name(temporary_selected_layer_name)
            self.remove_layer_by_name(temporary_raster_layer_name)
            
        except Exception as e:
            print(f"Error during cleanup: {str(e)}")
        
        # Call the base class implementation to ensure proper closing
        super().closeEvent(event)
