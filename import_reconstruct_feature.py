from PyQt5.QtWidgets import QDialog, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QFrame, QMessageBox
from PyQt5.QtCore import Qt
from qgis.core import QgsProject, QgsRectangle, QgsMessageLog, Qgis, QgsWkbTypes, QgsProcessingFeedback,QgsProcessingContext,QgsProcessingFeatureSourceDefinition,QgsCoordinateTransform, QgsRasterLayer
from qgis.gui import QgsMapCanvas, QgsMapToolPan
from PyQt5.QtGui import QColor
from math import cos, radians
from itertools import islice
import processing
import zipfile
import os
import tempfile
import shutil
import json

class ReconstructFeatures:
    def __init__(self, selected_layer, saved_temp_layer, selected_raster_layer, data):
        self.selected_layer_for_processing = selected_layer
        self.saved_temp_layer = saved_temp_layer
        self.selected_raster_layer = selected_raster_layer
        self.data = data
        self.reprojected_raster_layer = None

    def merge_attribute_dialog(self):
        """Show the dialog for verifying features."""

        # Create a new dialog for verification
        dialog = QDialog(None)
        dialog.setWindowTitle("Merge Feature Attribute")  # Set the dialog title
        dialog.setMinimumSize(800, 600)  # Set minimum size for the dialog window

        # Disable the close button and system menu options
        dialog.setWindowFlags(dialog.windowFlags() & ~Qt.WindowCloseButtonHint)
        dialog.setWindowFlags(dialog.windowFlags() & ~Qt.WindowSystemMenuHint)

        main_layout = QVBoxLayout(dialog)
        canvas_layout = QHBoxLayout()  # Layout for map canvases
        # Add canvases for selected and temporary layers
        if self.selected_raster_layer and self.reprojected_raster_layer == None:
            self.transform_raster_CRS(self.selected_layer_for_processing, self.selected_raster_layer)

        left_canvas_frame = self.create_canvas_frame("Original Data", self.selected_layer_for_processing)
        canvas_layout.addWidget(left_canvas_frame)  # Add the left canvas to the layout
        right_canvas_frame = self.create_canvas_frame("Vetted Data", self.saved_temp_layer)
        canvas_layout.addWidget(right_canvas_frame)  # Add the right canvas to the layout
        main_layout.addLayout(canvas_layout)  # Add the canvas layout to the main layout

        # Add buttons for accepting or rejecting features
        button_layout = QHBoxLayout()
        button_layout.setSpacing(25) 
        reject_button = QPushButton("Reject Vetted Feature") 
        accept_button = QPushButton("Accept Vetted Feature")
        # Modify the width of the buttons
        accept_button.setFixedWidth(120)  # Set a fixed width for the accept button
        reject_button.setFixedWidth(120)  # Set a fixed width for the reject button

        # Modify the color of the buttons
        accept_button.setStyleSheet("background-color: green; color: white;")
        reject_button.setStyleSheet("background-color: red; color: white;")
        accept_button.setCursor(Qt.PointingHandCursor)
        reject_button.setCursor(Qt.PointingHandCursor)
        button_layout.addWidget(reject_button)  # Add the reject button to the layout
        button_layout.addWidget(accept_button)  # Add the accept button to the layout
        button_layout.setAlignment(Qt.AlignCenter)
        main_layout.addLayout(button_layout)  # Add the button layout to the main layout

        self.current_feature_index = 0  # Track the index of the current feature being verified
        self.dialog = dialog  # Store the dialog reference
        self.left_canvas = left_canvas_frame.findChild(QgsMapCanvas)  # Retrieve the left canvas
        self.right_canvas = right_canvas_frame.findChild(QgsMapCanvas)  # Retrieve the right canvas

        # Synchronize the views of both canvases
        self.is_synchronizing = False  # Flag to avoid recursive synchronization
        self.left_canvas.extentsChanged.connect(self.synchronize_right_canvas)
        self.right_canvas.extentsChanged.connect(self.synchronize_left_canvas)

        accept_button.clicked.connect(lambda: self.move_to_next_feature())
        reject_button.clicked.connect(lambda: self.reject_feature())

        # Update the canvases to focus on the first feature
        self.update_canvases()
        dialog.exec_()  # Display the dialog

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
        
    def create_canvas_frame(self, label_text, layer):
        """Create a frame with a label and a map canvas."""
        frame = QFrame()  # Create a container frame
        frame_layout = QVBoxLayout(frame)  # Set a vertical layout for the frame

        label = QLabel(label_text)  # Create a label with the provided text
        label.setAlignment(Qt.AlignCenter)  # Center-align the label text
        label.setStyleSheet("font-size: 12px; font-weight: bold;")  # Set font size and bold style
        frame_layout.addWidget(label)  # Add the label to the frame layout

        canvas = QgsMapCanvas()  # Create a map canvas
        self.set_colour_opacity(self.saved_temp_layer, 0.6)  # Adjust the opacity for better visualization
        self.set_colour_opacity(self.selected_layer_for_processing, 0.6)
        canvas.setLayers([layer, self.reprojected_raster_layer])
        canvas.setCanvasColor(QColor("white"))  # Set the canvas background color to white
        canvas.setMapTool(QgsMapToolPan(canvas))  # Enable panning on the canvas
        frame_layout.addWidget(canvas)  # Add the canvas to the frame layout

        return frame  # Return the completed frame
    
    def set_colour_opacity(self, layer, opacity):
        """Set the opacity of the layer for visualization."""
        symbol = layer.renderer().symbol()  # Get the symbol for the layer          
        if symbol:
            symbol.setOpacity(opacity)  # Set the opacity of the symbol
        layer.triggerRepaint()  # Trigger a repaint to apply the change

    def synchronize_right_canvas(self):
        """Synchronize the right canvas with the left canvas."""
        if not self.is_synchronizing:  # Prevent infinite loop 
            self.is_synchronizing = True  # Mark synchronization in progress
            self.right_canvas.setExtent(self.left_canvas.extent())  # Set the extent of the right canvas to match the left canvas
            self.right_canvas.refresh()  # Refresh the right canvas to update its display
            self.is_synchronizing = False  # Reset the synchronization flag

    def synchronize_left_canvas(self):
        """Synchronize the left canvas with the right canvas."""
        if not self.is_synchronizing:  # Prevent infinite loop
            self.is_synchronizing = True  # Mark synchronization in progress
            self.left_canvas.setExtent(self.right_canvas.extent())  # Set the extent of the left canvas to match the right canvas
            self.left_canvas.refresh()  # Refresh the left canvas to update its display
            self.is_synchronizing = False  # Reset the synchronization flag

    def update_canvases(self):
        """
        Update canvases to focus on the current feature.
        Zooms both canvases to the bounding box of the feature being verified.
        """
        if self.current_feature_index < len(self.data):  # Check if there are remaining features
            feature_id = int(next(islice(self.data.keys(), self.current_feature_index, None)))
            feature = next(self.selected_layer_for_processing.getFeatures(f"feature_id = {feature_id}"), None)  # Fetch the feature

            if feature:
                centroid_geom = feature.geometry().centroid()  # Calculate the centroid of the feature
                centroid_point = centroid_geom.asPoint()  # Get the centroid as a point
                buffer = self.calculate_dynamic_buffer(feature.geometry())  # Calculate a dynamic buffer size

                # Define the bounding box for the feature with the buffer
                extent = QgsRectangle(
                    centroid_point.x() - buffer,
                    centroid_point.y() - buffer,
                    centroid_point.x() + buffer,
                    centroid_point.y() + buffer
                )
                self.zoom_to_feature_on_canvas(extent, self.left_canvas)  # Zoom the left canvas to the feature
                self.zoom_to_feature_on_canvas(extent, self.right_canvas)  # Zoom the right canvas to the feature
            else:
                # Log a warning if the feature cannot be found
                QgsMessageLog.logMessage(
                    f"Feature with feature_id {feature_id} not found in the .amrut file.",
                    "AMRUT",
                    Qgis.Warning
                )            

    def zoom_to_feature_on_canvas(self, extent, canvas):
        """Zoom to the feature's bounding box on the canvas."""
        canvas.setExtent(extent)  # Set the extent of the canvas
        canvas.refresh()  # Refresh the canvas to apply the changes

    def calculate_dynamic_buffer(self, geometry):
        """Calculate a dynamic buffer size based on the geometry type and size."""
        geometry_type = QgsWkbTypes.geometryType(geometry.wkbType())  # Get the geometry type

        # Determine the buffer size based on the geometry type
        if geometry_type == QgsWkbTypes.PointGeometry:
            buffer = 0.0001  # Small buffer for point geometries
        elif geometry_type == QgsWkbTypes.LineGeometry:
            line_length = geometry.length()  # Calculate the length of the line
            buffer = line_length * 0.5  # Use half the line length as the buffer
        elif geometry_type == QgsWkbTypes.PolygonGeometry:
            bbox = geometry.boundingBox()  # Get the bounding box of the polygon
            bbox_width = bbox.width()  # Width of the bounding box
            bbox_height = bbox.height()  # Height of the bounding box
            diagonal = (bbox_width**2 + bbox_height**2) ** 0.5  # Calculate the diagonal length
            buffer = diagonal * 0.5  # Use half the diagonal length as the buffer
        else:
            buffer = 0.0001  # Default buffer size for unsupported geometry types

        return buffer  # Return the calculated buffer size
    
    def transform_raster_CRS(self, layer, raster_layer):
        """Create a map canvas to render the given layer."""
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
                processing_context = QgsProcessingContext()
                feedback = QgsProcessingFeedback()

                # Reproject the clipped raster to the grid CRS
                reproject_params = {
                    'INPUT': raster_layer.source(),
                    'SOURCE_CRS': raster_crs.authid(),  # Source CRS (from the clipped raster)
                    'TARGET_CRS': grid_crs.authid(),    # Target CRS (grid layer CRS)
                    'RESAMPLING': 0,                    # Nearest neighbor resampling
                    'NODATA': -9999,                    # Specify NoData value if needed
                    'OUTPUT': 'TEMPORARY_OUTPUT'        # Output as a temporary layer
                }

                # Run the reprojection algorithm
                transform_result = processing.run("gdal:warpreproject", reproject_params, context=processing_context, feedback=feedback)

                # Get the reprojected raster layer from the result
                self.reprojected_raster_layer = QgsRasterLayer(transform_result['OUTPUT'], f"Temporary_{raster_layer.name()}")

                # Validate the reprojected raster layer
                if not self.reprojected_raster_layer.isValid():
                    raise ValueError("Failed to reproject the raster layer.")

                # Add the reprojected raster layer to the project
                QgsProject.instance().addMapLayer(self.reprojected_raster_layer)

                return
