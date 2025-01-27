from PyQt5.QtWidgets import QDialog, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QFrame
from PyQt5.QtCore import Qt
from qgis.core import QgsProject, QgsRectangle, QgsMessageLog, Qgis, QgsWkbTypes
from qgis.gui import QgsMapCanvas, QgsMapToolPan
from PyQt5.QtGui import QColor


class VerificationDialog:
    def __init__(self, selected_layer_name, selected_raster_layer_name):

        # Fetch the layer based on its name
        self.selected_layer = self.get_layer_by_name(selected_layer_name)
        self.selected_raster_layer = self.get_layer_by_name(f"Temporary_{selected_raster_layer_name}")
        self.temporary_layer = self.get_layer_by_name(f"Temporary_{selected_layer_name}")

    def check_for_new_features(self):
        """
        Compare feature IDs of the selected layer and the temporary layer to identify new features.
        If new features are found, prompt the user with a dialog.
        """
        if self.selected_layer and self.temporary_layer:
            # Collect feature IDs from the selected layer into a set
            selected_feature_ids = {f['feature_id'] for f in self.selected_layer.getFeatures()}
            self.new_feature_ids = set()  # Initialize a set to store IDs of new features

            for feature in self.temporary_layer.getFeatures():
                temp_feature_id = feature['feature_id']  # Extract feature ID from the temporary layer
                if temp_feature_id not in selected_feature_ids:  # Check if it's a new feature
                    self.new_feature_ids.add(temp_feature_id)

            self.show_new_features_dialog()

    def show_new_features_dialog(self):
        """
        Display a dialog showing the number of new features found.
        If features are found, allow the user to proceed to verification.
        """
        feature_count = len(self.new_feature_ids)  # Count the number of new features
        message = f"{feature_count} new features found in the temporary layer."  # Prepare the message

        # Create a dialog box to display the message
        dialog = QDialog(None)
        dialog.setWindowTitle("New Features Found")  # Set the title of the dialog
        dialog.setMinimumSize(300, 150)  # Set minimum size for the dialog window

        layout = QVBoxLayout(dialog)  # Use a vertical layout for the dialog

        message_label = QLabel(message)
        message_label.setAlignment(Qt.AlignCenter)  # Center-align the message text
        layout.addWidget(message_label)  # Add the label to the layout

        if feature_count > 0:
            # If there are new features, add a "Proceed" button
            button_layout = QHBoxLayout()
            proceed_button = QPushButton("Proceed to Verify")  # Create the button
            button_layout.addWidget(proceed_button, alignment=Qt.AlignCenter)  # Add button to the layout
            proceed_button.setFixedWidth(150)  # Set a fixed width for the button
            layout.addLayout(button_layout)  # Add the button layout to the main layout
            proceed_button.clicked.connect(lambda: self.show_verification_dialog(dialog)) # Connect the button click event to open the verification dialog

        dialog.exec_()  # Display the dialog

    def get_layer_by_name(self, layer_name):
        """Retrieve a layer by its name from the QGIS project. If layer not found return None"""
        for layer in QgsProject.instance().mapLayers().values():
            if layer.name() == layer_name:
                return layer 
        return None

    def show_verification_dialog(self, parent_dialog):
        """Show the dialog for verifying new features."""
        parent_dialog.close()  # Close the parent dialog

        # Create a new dialog for verification
        dialog = QDialog(None)
        dialog.setWindowTitle("Verify New Features")  # Set the dialog title
        dialog.setMinimumSize(800, 600)  # Set minimum size for the dialog window

        # Disable the close button and system menu options
        dialog.setWindowFlags(dialog.windowFlags() & ~Qt.WindowCloseButtonHint)
        dialog.setWindowFlags(dialog.windowFlags() & ~Qt.WindowSystemMenuHint)

        main_layout = QVBoxLayout(dialog)
        canvas_layout = QHBoxLayout()  # Layout for map canvases

        # Add canvases for selected and temporary layers
        left_canvas_frame = self.create_canvas_frame("Selected Layer", self.selected_layer)
        canvas_layout.addWidget(left_canvas_frame)  # Add the left canvas to the layout
        right_canvas_frame = self.create_canvas_frame("Temporary Layer", self.temporary_layer)
        canvas_layout.addWidget(right_canvas_frame)  # Add the right canvas to the layout
        main_layout.addLayout(canvas_layout)  # Add the canvas layout to the main layout

        # Add buttons for accepting or rejecting features
        button_layout = QHBoxLayout()
        accept_button = QPushButton("Accept New Feature")
        reject_button = QPushButton("Reject New Feature") 
        button_layout.addWidget(accept_button)  # Add the accept button to the layout
        button_layout.addWidget(reject_button)  # Add the reject button to the layout
        main_layout.addLayout(button_layout)  # Add the button layout to the main layout

        self.current_feature_index = 0  # Track the index of the current feature being verified
        self.dialog = dialog  # Store the dialog reference
        self.left_canvas = left_canvas_frame.findChild(QgsMapCanvas)  # Retrieve the left canvas
        self.right_canvas = right_canvas_frame.findChild(QgsMapCanvas)  # Retrieve the right canvas

        # Synchronize the views of both canvases
        self.is_synchronizing = False  # Flag to avoid recursive synchronization
        self.left_canvas.extentsChanged.connect(self.synchronize_right_canvas)
        self.right_canvas.extentsChanged.connect(self.synchronize_left_canvas)

        accept_button.clicked.connect(self.move_to_next_feature)
        reject_button.clicked.connect(self.reject_feature)

        # Update the canvases to focus on the first feature
        self.update_canvases()
        dialog.exec_()  # Display the dialog

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

    def create_canvas_frame(self, label_text, layer):
        """Create a frame with a label and a map canvas."""
        frame = QFrame()  # Create a container frame
        frame_layout = QVBoxLayout(frame)  # Set a vertical layout for the frame

        label = QLabel(label_text)  # Create a label with the provided text
        label.setAlignment(Qt.AlignCenter)  # Center-align the label text
        frame_layout.addWidget(label)  # Add the label to the frame layout

        canvas = QgsMapCanvas()  # Create a map canvas
        if layer == self.temporary_layer:
            self.set_colour_opacity(self.temporary_layer, 0.6)  # Adjust the opacity for better visualization

        canvas.setLayers([layer, self.selected_raster_layer])
        canvas.setCanvasColor(QColor("white"))  # Set the canvas background color to white
        canvas.setMapTool(QgsMapToolPan(canvas))  # Enable panning on the canvas
        frame_layout.addWidget(canvas)  # Add the canvas to the frame layout

        return frame  # Return the completed frame

    def update_canvases(self):
        """
        Update canvases to focus on the current feature.
        Zooms both canvases to the bounding box of the feature being verified.
        """
        if self.current_feature_index < len(self.new_feature_ids):  # Check if there are remaining features
            feature_id = int(list(self.new_feature_ids)[self.current_feature_index])  # Get the current feature ID
            feature = next(self.temporary_layer.getFeatures(f"feature_id = {feature_id}"), None)  # Fetch the feature

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

    def reject_feature(self):
        """
        Handle rejecting the current feature.
        Deletes the feature from the temporary layer(layer from .amrut file) and moves to the next feature.
        """
        feature_id = int(list(self.new_feature_ids)[self.current_feature_index])  # Get the current feature ID
        feature = next(self.temporary_layer.getFeatures(f"feature_id = {feature_id}"), None)  # Fetch the feature
        self.temporary_layer.startEditing()  # Start editing the temporary layer
        self.temporary_layer.deleteFeature(feature.id())  # Delete the feature from the layer
        self.temporary_layer.commitChanges()  # Save the changes
        self.move_to_next_feature()  # Move to the next feature in the list

    def move_to_next_feature(self):
        """
        Move to the next feature in the list.
        If no more features remain, close the dialog.
        """
        self.current_feature_index += 1  # Increment the feature index
        if self.current_feature_index < len(self.new_feature_ids):  # Check if there are more features
            self.update_canvases()  # Update canvases to display the next feature
        else:
            self.set_colour_opacity(self.temporary_layer, 1)  # Reset the opacity of the temporary layer
            self.dialog.close()  # Close the verification dialog

    def set_colour_opacity(self, layer, opacity):
        """Set the opacity of the layer for visualization."""
        symbol = layer.renderer().symbol()  # Get the symbol for the layer
        if symbol:
            symbol.setOpacity(opacity)  # Set the opacity of the symbol
        layer.triggerRepaint()  # Trigger a repaint to apply the changes

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
            print(buffer)
        else:
            buffer = 0.0001  # Default buffer size for unsupported geometry types

        return buffer  # Return the calculated buffer size
