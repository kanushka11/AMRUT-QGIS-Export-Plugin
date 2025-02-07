from PyQt5.QtWidgets import QDialog, QHBoxLayout, QVBoxLayout, QLabel
from PyQt5.QtCore import Qt, QTimer
from qgis.core import QgsProject, QgsVectorLayer, QgsCoordinateTransform, QgsRasterLayer, QgsProcessingFeedback, QgsProcessingContext, QgsMessageLog, Qgis, QgsPointXY
from qgis.gui import QgsMapCanvas
from PyQt5.QtGui import QColor, QMouseEvent
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
        self.temporary_files = []  # List to track temporary files
        self.reprojected_raster_layer = None

        self.setWindowTitle("AMRUT 2.0")
        self.setWindowState(Qt.WindowMaximized)

        # Attributes for map canvases
        self.left_map_canvas = None
        self.right_map_canvas = None
        self.synchronizing = False  # Prevent infinite synchronization loops

        # Main layout
        layout = QHBoxLayout(self)

        layer = self.get_layer_by_name(self.selected_layer_name)
        raster_layer = self.get_layer_by_name(self.selected_raster_layer_name) if self.selected_raster_layer_name else None

        if layer:
            left_panel, self.left_map_canvas = self.create_layer_visualization_panel(layer, f"{self.selected_layer_name} (Original Data)", raster_layer)
        else:
            left_panel, self.left_map_canvas = self.create_error_panel(f"Layer '{self.selected_layer_name}' not found in the project."), None
        layout.addLayout(left_panel)

        # Add a vertical divider
        self.add_vertical_divider(layout)

        # Add right panel
        right_panel, self.right_map_canvas = self.create_geojson_visualization_panel(raster_layer)
        layout.addLayout(right_panel)

        # Synchronize extents between left and right map canvases
        self.setup_canvas_synchronization()

        QTimer.singleShot(1000, self.show_new_feature_dialog)  # Delay in ms before triggering check

    def show_new_feature_dialog(self):
        try:
            newFeatureFound = verification_dialog.VerificationDialog(self.selected_layer_name, self.selected_raster_layer_name, self.amrut_file_path, self.grid_extent)
            newFeatureFound.check_for_new_features()
        except Exception as e:
            QgsMessageLog.logMessage(f"Error in show_new_feature_dialog: {str(e)}", 'AMRUT', Qgis.Critical)

    def setup_canvas_synchronization(self):
        """Synchronize extents between the left and right map canvases."""
        try:
            if self.left_map_canvas and self.right_map_canvas:
                self.left_map_canvas.extentsChanged.connect(self.sync_extents_to_right)
                self.right_map_canvas.extentsChanged.connect(self.sync_extents_to_left)
        except Exception as e:
            QgsMessageLog.logMessage(f"Error in setup_canvas_synchronization: {str(e)}", 'AMRUT', Qgis.Critical)

    def sync_extents_to_right(self):
        """Sync the extent of the left canvas to the right canvas."""
        try:
            if not self.synchronizing:  # Prevent infinite loops
                self.synchronizing = True
                if self.left_map_canvas and self.right_map_canvas:
                    self.right_map_canvas.setExtent(self.left_map_canvas.extent())
                    self.right_map_canvas.refresh()
                    self.refresh_canvas_layers(self.right_map_canvas)  # Refresh layers for the new extent
                self.synchronizing = False
        except Exception as e:
            QgsMessageLog.logMessage(f"Error in sync_extents_to_right: {str(e)}", 'AMRUT', Qgis.Critical)

    def sync_extents_to_left(self):
        """Sync the extent of the right canvas to the left canvas."""
        try:
            if not self.synchronizing:  # Prevent infinite loops
                self.synchronizing = True
                if self.left_map_canvas and self.right_map_canvas:
                    self.left_map_canvas.setExtent(self.right_map_canvas.extent())
                    self.left_map_canvas.refresh()
                    self.refresh_canvas_layers(self.left_map_canvas)  # Refresh layers for the new extent
                self.synchronizing = False
        except Exception as e:
            QgsMessageLog.logMessage(f"Error in sync_extents_to_left: {str(e)}", 'AMRUT', Qgis.Critical)

    def refresh_canvas_layers(self, canvas):
        """Refresh all layers in the given canvas to load data for the current extent."""
        try:
            if canvas:
                for layer in canvas.layers():
                    layer.triggerRepaint()  # Reload and repaint the layer for the current extent
        except Exception as e:
            QgsMessageLog.logMessage(f"Error in refresh_canvas_layers: {str(e)}", 'AMRUT', Qgis.Critical)

    def create_geojson_visualization_panel(self, raster_layer):
        """Create a panel to visualize the GeoJSON extracted from the AMRUT file."""
        try:
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
                panel_layout, map_canvas = self.create_layer_visualization_panel(
                    geojson_layer,
                    f"{self.selected_layer_name} (Field Data)",
                    raster_layer
                )
                return panel_layout, map_canvas
            else:
                panel_layout = self.create_error_panel(f"Layer '{self.selected_layer_name}' not found in .AMRUT file")
                return panel_layout, None
        except Exception as e:
            QgsMessageLog.logMessage(f"Error in create_geojson_visualization_panel: {str(e)}", 'AMRUT', Qgis.Critical)
            return None, None

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

                    # Add the temporary file path to the list for cleanup
                    self.temporary_files.append(temp_geojson_file_path)
                    
                    # Load the GeoJSON into a vector layer using the temporary file path
                    geojson_layer = QgsVectorLayer(temp_geojson_file_path, layer_name, "ogr")

                    if geojson_layer.isValid():
                        return geojson_layer
                    else:
                        raise ValueError(f"GeoJSON layer '{layer_name}' is not valid.")
                else:
                    raise FileNotFoundError(f"GeoJSON file '{geojson_filename}' not found in the AMRUT file.")
        except Exception as e:
            QgsMessageLog.logMessage(f"Error loading GeoJSON: {str(e)}", 'AMRUT', Qgis.Critical)
            return None

    def get_layer_by_name(self, layer_name):
        """Retrieve a layer from the QGIS project by its name."""
        try:
            for layer in QgsProject.instance().mapLayers().values():
                if layer.name() == layer_name:
                    return layer
            return None
        except Exception as e:
            QgsMessageLog.logMessage(f"Error in get_layer_by_name: {str(e)}", 'AMRUT', Qgis.Critical)
            return None
    
    def remove_layer_by_name(self, layer_name):
        """Remove a layer from the QGIS project by its name."""
        try:
            for layer in QgsProject.instance().mapLayers().values():
                if layer.name() == layer_name:
                    QgsProject.instance().removeMapLayer(layer.id())
                    break
            return None
        except Exception as e:
            QgsMessageLog.logMessage(f"Error in remove_layer_by_name: {str(e)}", 'AMRUT', Qgis.Critical)
            return None

    def create_layer_visualization_panel(self, layer, title, raster_layer):
        """Create a panel to visualize a specific project layer."""
        try:
            panel_layout = QVBoxLayout()
            
            # Create the label with larger and bold text
            label = QLabel(title)
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet("font-size: 12px; font-weight: bold;")  # Set font size and bold style
            
            panel_layout.addWidget(label)

            if raster_layer and self.reprojected_raster_layer == None:
                self.transform_raster_CRS(layer, raster_layer)

            # Create the map canvas and add it to the panel
            map_canvas = self.create_map_canvas(layer)
            panel_layout.addWidget(map_canvas)

            return panel_layout, map_canvas
        except Exception as e:
            QgsMessageLog.logMessage(f"Error in create_layer_visualization_panel: {str(e)}", 'AMRUT', Qgis.Critical)
            return None, None
        
    def transform_raster_CRS(self, layer, raster_layer):
        existing_layer = None

        if raster_layer and self.reprojected_raster_layer == None:
            # Remove if a clipped and reprojected raster already exists
            self.remove_layer_by_name(f"Temporary_{raster_layer.name()}")
        elif raster_layer:
            # Check if a clipped and reprojected raster already exists
            for lyr in QgsProject.instance().mapLayers().values():
                if lyr.name() == f"Temporary_{raster_layer.name()}" and isinstance(lyr, QgsRasterLayer):
                    existing_layer = lyr
                    break

        if raster_layer:
            # Raster clipping and reprojection logic
            if existing_layer:
                self.reprojected_raster_layer = existing_layer
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
                    'OUTPUT': 'TEMPORARY_OUTPUT'        # Output as a temporary layer
                }

                # Run the reprojection algorithm
                reprojected_result = processing.run("gdal:warpreproject", reproject_params, context=processing_context, feedback=feedback)

                # Add the temporary raster file to the cleanup list
                temp_raster_path = reprojected_result['OUTPUT']
                self.temporary_files.append(temp_raster_path)

                # Get the reprojected raster layer from the result
                self.reprojected_raster_layer = QgsRasterLayer(reprojected_result['OUTPUT'], f"Temporary_{raster_layer.name()}")

                # Validate the reprojected raster layer
                if not self.reprojected_raster_layer.isValid():
                    raise ValueError("Failed to reproject the raster layer.")

                # Add the reprojected raster layer to the project
                QgsProject.instance().addMapLayer(self.reprojected_raster_layer)

    def create_map_canvas(self, layer):
        """Create a map canvas to render the given layer."""
        try:
            # Set up the map canvas with layers
            canvas = QgsMapCanvas()
            canvas.setLayers([layer, self.reprojected_raster_layer])

            # Set extent and background color for canvas
            canvas.setExtent(self.grid_extent)
            canvas.setCanvasColor(QColor("white"))

            # Enable mouse tracking for panning
            canvas.setMouseTracking(True)
            self.setup_mouse_tracking(canvas)

            canvas.refresh()  # Refresh the canvas to ensure proper visualization

            return canvas
        except Exception as e:
            QgsMessageLog.logMessage(f"Error in create_map_canvas: {str(e)}", 'AMRUT', Qgis.Critical)
            return None
        
    def setup_mouse_tracking(self, canvas):
        """Set up mouse tracking for panning."""
        self.canvas = canvas
        self.last_mouse_position = None

        # Connect mouse events
        self.canvas.mousePressEvent = self.mouse_press_event
        self.canvas.mouseMoveEvent = self.mouse_move_event
        self.canvas.mouseReleaseEvent = self.mouse_release_event

    def mouse_press_event(self, event: QMouseEvent):
        """Handle mouse press event for panning."""
        if event.button() == Qt.LeftButton:
            self.last_mouse_position = event.pos()

    def mouse_move_event(self, event: QMouseEvent):
        """Handle mouse move event for panning."""
        if self.last_mouse_position is not None:
            # Calculate delta in screen coordinates
            current_mouse_position = event.pos()

            # Convert mouse positions to map coordinates
            start_map_point = self.canvas.getCoordinateTransform().toMapCoordinates(self.last_mouse_position)
            end_map_point = self.canvas.getCoordinateTransform().toMapCoordinates(current_mouse_position)

            # Calculate map delta
            map_delta_x = start_map_point.x() - end_map_point.x()
            map_delta_y = start_map_point.y() - end_map_point.y()

            # Update the canvas center
            current_center = self.canvas.center()
            new_center = QgsPointXY(current_center.x() + map_delta_x, current_center.y() + map_delta_y)

            self.canvas.setCenter(new_center)

            # Update last mouse position
            self.last_mouse_position = current_mouse_position

    def mouse_release_event(self, event: QMouseEvent):
        """Handle mouse release event."""
        if event.button() == Qt.LeftButton:
            self.last_mouse_position = None

    def create_error_panel(self, message):
        """Create a panel to display an error message."""
        try:
            panel_layout = QVBoxLayout()
            error_label = QLabel(message)
            error_label.setAlignment(Qt.AlignCenter)
            panel_layout.addWidget(error_label)
            return panel_layout
        except Exception as e:
            QgsMessageLog.logMessage(f"Error in create_error_panel: {str(e)}", 'AMRUT', Qgis.Critical)
            return None

    def add_vertical_divider(self, layout):
        """Add a vertical divider to the layout."""
        try:
            line = QLabel()
            line.setFixedWidth(1)
            line.setStyleSheet("background-color: black;")
            layout.addWidget(line)
        except Exception as e:
            QgsMessageLog.logMessage(f"Error in add_vertical_divider: {str(e)}", 'AMRUT', Qgis.Critical)

    def closeEvent(self, event):
        """Override closeEvent to remove temporary layers and refresh the map canvas."""
        try:
            # Remove temporary layers
            self.remove_layer_by_name(f"Temporary_{self.selected_layer_name}")
            self.remove_layer_by_name(f"Temporary_{self.selected_raster_layer_name}")

            # Refresh all layers to clear cached features
            QgsProject.instance().reloadAllLayers()

            # Delete all temporary files
            for temp_file in self.temporary_files:
                if os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                    except Exception as e:
                        QgsMessageLog.logMessage(f"Error deleting temp file {temp_file}: {str(e)}", 'AMRUT', Qgis.Warning)
            
            self.refresh_map_canvas()
            QgsProject.instance().write()
        except Exception as e:
            QgsMessageLog.logMessage(f"Error in closeEvent cleanup: {str(e)}", 'AMRUT', Qgis.Critical)
        finally:
            super().closeEvent(event)

    def refresh_map_canvas(self):
        """Refresh the map canvas to ensure changes are visible."""
        try:
            for map_canvas in self.findChildren(QgsMapCanvas):
                map_canvas.refresh()  # Refresh the canvas to clear outdated visuals
        except Exception as e:
            QgsMessageLog.logMessage(f"Error while refreshing the map canvas: {str(e)}", 'AMRUT', Qgis.Critical)
