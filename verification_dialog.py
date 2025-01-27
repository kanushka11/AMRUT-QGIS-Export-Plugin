from PyQt5.QtWidgets import QDialog, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QFrame
from PyQt5.QtCore import Qt
from qgis.core import QgsProject, QgsRectangle, QgsGeometry, QgsWkbTypes
from qgis.gui import QgsMapCanvas, QgsMapToolPan
from PyQt5.QtGui import QColor


class VerificationDialog:
    def __init__(self, selected_layer_name, selected_raster_layer_name):
        self.selected_layer = self.get_layer_by_name(selected_layer_name)
        self.selected_raster_layer = self.get_layer_by_name(f"Temporary_{selected_raster_layer_name}")
        self.temporary_layer = self.get_layer_by_name(f"Temporary_{selected_layer_name}")
        
    def check_for_new_features(self):
        """Compare the feature_id attribute of both layers and prompt the user if new features are found."""
        if self.selected_layer and self.temporary_layer:
            selected_feature_ids = {f['feature_id'] for f in self.selected_layer.getFeatures()}
            self.new_feature_ids = set()

            for feature in self.temporary_layer.getFeatures():
                temp_feature_id = feature['feature_id']
                if temp_feature_id not in selected_feature_ids:
                    self.new_feature_ids.add(temp_feature_id)
            self.show_new_features_dialog()

    def show_new_features_dialog(self):
        """Show dialog box asking user to proceed to verify new features."""
        feature_count = len(self.new_feature_ids)
        message = f"{feature_count} new features found in the temporary layer."

        dialog = QDialog(None)
        dialog.setWindowTitle("New Features Found")
        dialog.setMinimumSize(300, 150)

        layout = QVBoxLayout(dialog)
        message_label = QLabel(message)
        message_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(message_label)

        if feature_count > 0:
            button_layout = QHBoxLayout()
            proceed_button = QPushButton("Proceed to Verify")
            button_layout.addWidget(proceed_button, alignment=Qt.AlignCenter)
            proceed_button.setFixedWidth(150)
            layout.addLayout(button_layout)

            proceed_button.clicked.connect(lambda: self.show_verification_dialog(dialog))
        dialog.exec_()
        
    def get_layer_by_name(self, layer_name):
        """Retrieve a layer from the QGIS project by its name."""
        for layer in QgsProject.instance().mapLayers().values():
            if layer.name() == layer_name:
                return layer
        return None

    def show_verification_dialog(self, parent_dialog):
        """Show the feature verification dialog."""
        parent_dialog.close()

        dialog = QDialog(None)
        dialog.setWindowTitle("Verify New Features")
        dialog.setMinimumSize(800, 600)

        main_layout = QVBoxLayout(dialog)
        canvas_layout = QHBoxLayout()

        # Left canvas for selected layer
        left_canvas_frame = self.create_canvas_frame("Selected Layer", self.selected_layer)
        canvas_layout.addWidget(left_canvas_frame)

        # Right canvas for temporary layer
        right_canvas_frame = self.create_canvas_frame("Temporary Layer", self.temporary_layer)
        canvas_layout.addWidget(right_canvas_frame)

        main_layout.addLayout(canvas_layout)

        # Add buttons for accepting or rejecting features
        button_layout = QHBoxLayout()
        accept_button = QPushButton("Accept New Feature")
        reject_button = QPushButton("Reject New Feature")
        button_layout.addWidget(accept_button)
        button_layout.addWidget(reject_button)
        main_layout.addLayout(button_layout)

        # Initialize feature navigation
        self.current_feature_index = 0
        self.dialog = dialog
        self.left_canvas = left_canvas_frame.findChild(QgsMapCanvas)
        self.right_canvas = right_canvas_frame.findChild(QgsMapCanvas)

        # Connect button actions
        accept_button.clicked.connect(self.accept_feature)
        reject_button.clicked.connect(self.reject_feature)

        self.update_canvases()
        dialog.exec_()

    def create_canvas_frame(self, label_text, layer):
        """Create a frame with a label and map canvas."""
        frame = QFrame()
        frame_layout = QVBoxLayout(frame)

        label = QLabel(label_text)
        label.setAlignment(Qt.AlignCenter)
        frame_layout.addWidget(label)

        canvas = QgsMapCanvas()
        canvas.setLayers([layer,self.selected_raster_layer])
        canvas.setCanvasColor(QColor("white"))
        canvas.setMapTool(QgsMapToolPan(canvas))
        frame_layout.addWidget(canvas)

        return frame

    def calculate_dynamic_buffer(self, geometry):
        """
        Calculate a dynamic buffer based on geometry type and size.
        """
        geometry_type = QgsWkbTypes.geometryType(geometry.wkbType())

        if geometry_type == QgsWkbTypes.PointGeometry:
            # For point geometries, use a small fixed buffer
            buffer = 0.0001  # Map units (adjust based on your map scale)

        elif geometry_type == QgsWkbTypes.LineGeometry:
            # For line geometries, use a buffer proportional to the length of the line
            line_length = geometry.length()
            buffer = line_length * 0.5  # 20% of length or a minimum of 100 units

        elif geometry_type == QgsWkbTypes.PolygonGeometry:
            # For polygon geometries, use a buffer based on the diagonal of the bounding box
            bbox = geometry.boundingBox()
            bbox_width = bbox.width()
            bbox_height = bbox.height()

            # Diagonal size of the bounding box
            diagonal = (bbox_width**2 + bbox_height**2) ** 0.5
            buffer = diagonal * 0.5  # 50% of diagonal

        else:
            # Default buffer for unsupported geometry types
            buffer = 0.0001  # Map units

        return buffer

    def update_canvases(self):
        """Update canvases to focus on the current feature."""
        if self.current_feature_index < len(self.new_feature_ids):
            # Convert the feature_id to integer
            feature_id = int(list(self.new_feature_ids)[self.current_feature_index])

            # Get the feature from the temporary layer
            temp_feature = next(self.temporary_layer.getFeatures(f"feature_id = {feature_id}"), None)

            if temp_feature:
                # Get the centroid of the feature's geometry
                centroid_geom = temp_feature.geometry().centroid()
                centroid_point = centroid_geom.asPoint()

                # Dynamically calculate the buffer for zooming
                buffer = self.calculate_dynamic_buffer(temp_feature.geometry())

                # Define an extent around the centroid for zooming
                extent = QgsRectangle(
                    centroid_point.x() - buffer,
                    centroid_point.y() - buffer,
                    centroid_point.x() + buffer,
                    centroid_point.y() + buffer
                )

                # Zoom to the centroid on both canvases
                self.zoom_to_feature_on_left_canvas(extent)
                self.zoom_to_feature_on_right_canvas(extent)
            else:
                print(f"Feature with feature_id {feature_id} not found in the temporary layer.")


    def zoom_to_feature_on_left_canvas(self, extent):
        """Zoom to the feature's centroid on the left canvas (selected layer)."""
        self.left_canvas.setExtent(extent)
        self.left_canvas.refresh()

    def zoom_to_feature_on_right_canvas(self, extent):
        """Zoom to the feature's centroid on the right canvas (temporary layer)."""
        self.right_canvas.setExtent(extent)
        self.right_canvas.refresh()

    def accept_feature(self):
        """Handle accepting the current feature."""
        feature_id = list(self.new_feature_ids)[self.current_feature_index]
        print(f"Feature {feature_id} accepted.")
        self.move_to_next_feature()

    def reject_feature(self):
        """Handle rejecting the current feature."""
        feature_id = list(self.new_feature_ids)[self.current_feature_index]
        print(f"Feature {feature_id} rejected.")
        self.move_to_next_feature()

    def move_to_next_feature(self):
        """Move to the next feature in the list."""
        self.current_feature_index += 1
        if self.current_feature_index < len(self.new_feature_ids):
            self.update_canvases()
        else:
            print("All features reviewed.")
            self.dialog.close()

    def get_layer_by_name(self, layer_name):
        """Retrieve a layer from the QGIS project by its name."""
        for layer in QgsProject.instance().mapLayers().values():
            if layer.name() == layer_name:
                return layer
        return None
