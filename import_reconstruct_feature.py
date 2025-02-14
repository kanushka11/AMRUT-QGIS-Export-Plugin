from PyQt5.QtWidgets import (
    QDialog, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QFrame, QMessageBox,
    QTableWidget, QTableWidgetItem, QGroupBox, QSizePolicy, QHeaderView
)
from PyQt5.QtWidgets import QScrollArea, QGroupBox, QTableWidget, QTableWidgetItem, QApplication, QProgressBar
from PyQt5.QtCore import Qt, QThread, QEventLoop
from qgis.core import (
    QgsProject, QgsRectangle, QgsMessageLog, Qgis, QgsWkbTypes,
    QgsProcessingFeedback, QgsProcessingContext, QgsRasterLayer, QgsFeature, QgsFeatureRequest, edit
)
from qgis.gui import QgsMapCanvas, QgsMapToolPan
from PyQt5.QtGui import QColor
from . import import_workers

class ReconstructFeatures:
    def __init__(self, selected_layer, saved_temp_layer, selected_raster_layer, data, progress_bar):
        self.selected_layer_for_processing = selected_layer
        self.saved_temp_layer = saved_temp_layer
        self.selected_raster_layer = selected_raster_layer
        self.data = data 
        self.reprojected_raster_layer = None
        self.current_feature_index = 0  # Initialize current_feature_index
        self.progress_bar = progress_bar

    def merge_attribute_dialog(self):
        """Show the dialog for verifying features in full-screen mode."""
        dialog = QDialog(None)
        dialog.setWindowTitle("Merge Feature Attribute")
        # Set the dialog to full-screen (or maximized)
        dialog.setWindowState(Qt.WindowMaximized)
        dialog.setWindowFlags(dialog.windowFlags() & ~Qt.WindowCloseButtonHint)
        dialog.setWindowFlags(dialog.windowFlags() & ~Qt.WindowSystemMenuHint)

        main_layout = QVBoxLayout(dialog)  # Main vertical layout

        # Create a horizontal layout for left and right canvases (Top Section)
        top_canvas_layout = QHBoxLayout()

        # Ensure raster transformation if needed
        if self.selected_raster_layer and self.reprojected_raster_layer is None:
            self.transform_raster_CRS(self.selected_layer_for_processing, self.selected_raster_layer)

        # Create left (Original Data) and right (Vetted Data) canvases
        left_canvas_frame = self.create_canvas_frame("Original Data", self.selected_layer_for_processing)
        right_canvas_frame = self.create_canvas_frame("Vetted Data", self.saved_temp_layer)

        top_canvas_layout.addWidget(left_canvas_frame)
        top_canvas_layout.addWidget(right_canvas_frame)
        # Add the top section with a stretch factor (e.g., 1/3 of the screen)
        main_layout.addLayout(top_canvas_layout, stretch=1)

        # Create the bottom section: a frame that shows attribute tables for the broken features.
        bottom_attr_frame = self.create_attribute_tables_frame()
        # Add the bottom section with a higher stretch factor (e.g., 2/3 of the screen)
        main_layout.addWidget(bottom_attr_frame, stretch=2)

        self.current_feature_index = 0
        self.dialog = dialog
        self.left_canvas = left_canvas_frame.findChild(QgsMapCanvas)
        self.right_canvas = right_canvas_frame.findChild(QgsMapCanvas)
        # No canvas is created in the bottom section, so we do not assign self.bottom_canvas

        # Synchronize the top two canvases
        self.is_synchronizing = False
        self.left_canvas.extentsChanged.connect(self.synchronize_right_canvas)
        self.right_canvas.extentsChanged.connect(self.synchronize_left_canvas)

        self.update_canvases()
        dialog.exec_()

    def transform_raster_CRS(self, layer, raster_layer):
        """ Initiate raster transformation with a blocking progress bar """
        if not raster_layer or self.reprojected_raster_layer:
            return  # Skip if no raster or already transformed

        # Show progress bar (indeterminate state)
        self.progress_bar.setRange(0, 0)  # Indeterminate mode
        self.progress_bar.show()
        QApplication.processEvents()

        self.worker = import_workers.RasterTransformWorker(layer, raster_layer)
        self.thread = QThread()

        # Move worker to thread
        self.worker.moveToThread(self.thread)

        # Connect signals
        self.thread.started.connect(self.worker.run)
        self.worker.progress_signal.connect(self.progress_bar.setValue)

        event_loop = QEventLoop()  # Create an event loop to block execution

        def on_transformation_finished(raster_layer):
            """ Handle raster transformation completion """
            self.reprojected_raster_layer = raster_layer
            if raster_layer:
                QgsProject.instance().addMapLayer(self.reprojected_raster_layer)
            else:
                QMessageBox.warning(None, "Error", "Raster transformation failed.")

            self.progress_bar.setRange(0, 100)  # Reset progress range
            self.progress_bar.setValue(100)

            event_loop.quit()  # Exit event loop, allowing execution to continue

        # Connect the finished signal to event loop quit
        self.worker.finished_signal.connect(on_transformation_finished)
        self.worker.finished_signal.connect(self.thread.quit)
        self.worker.finished_signal.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

        # Start thread
        self.thread.start()

        # Block execution until transformation is complete
        event_loop.exec_()


    def create_attribute_tables_frame(self):
        """
        Create a QFrame that displays attribute tables (horizontally)
        for all the broken features in the current feature entry.
        """
        container = QFrame()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(10)

        # Ensure we are within the feature index range
        if self.current_feature_index < len(self.data):
            feature_id = list(self.data.keys())[self.current_feature_index]
            broken_features = self.data[feature_id]

            if broken_features:
                for idx, broken_feature in enumerate(broken_features, start=1):
                    group_box = QGroupBox(f"Broken Feature {idx}")
                    group_layout = QVBoxLayout(group_box)

                    table = QTableWidget()
                    table.setWordWrap(True)
                    table.resizeColumnsToContents()
                    table.resizeRowsToContents()
                    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
                    table.horizontalHeader().setStretchLastSection(True)
                    table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

                    if isinstance(broken_feature, QgsFeature):
                        fields = broken_feature.fields()
                        num_fields = len(fields)
                        table.setColumnCount(2)
                        table.setRowCount(num_fields)
                        table.setHorizontalHeaderLabels(["Attribute", "Value"])

                        for row in range(num_fields):
                            field_name = fields.at(row).name()
                            value = broken_feature.attribute(field_name)
                            table.setItem(row, 0, QTableWidgetItem(field_name))
                            table.setItem(row, 1, QTableWidgetItem(str(value)))
                    else:
                        table.setColumnCount(1)
                        table.setRowCount(1)
                        table.setHorizontalHeaderLabels(["Value"])
                        table.setItem(0, 0, QTableWidgetItem(str(broken_feature)))

                    group_layout.addWidget(table)

                    # Create "Accept" button
                    accept_button = QPushButton("Accept")
                    accept_button.clicked.connect(lambda checked, bf=broken_feature: self.accept_and_next_feature(bf))
                    group_layout.addWidget(accept_button)

                    layout.addWidget(group_box)
            else:
                layout.addWidget(QLabel("No broken features available."))
        else:
            layout.addWidget(QLabel("All features reviewed."))

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(container)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        return scroll_area
    

    def accept_and_next_feature(self, accepted_feature):
        """
        Store the accepted feature separately and move to the next feature.
        Updates features in saved_temp_layer based on feature_id, excluding primary keys.
        """
        self.selected_layer_for_processing.setSubsetString("")  # Reset the filter to show all features
        self.saved_temp_layer.setSubsetString("")
        if not self.data or self.current_feature_index >= len(self.data):
            QMessageBox.information(None, "Review Complete", "All features have been reviewed.")
            self.dialog.accept()
            return

        print(f"Accepted Feature (ID: {accepted_feature.id()}):")

        if self.saved_temp_layer is not None:
            # Get primary key attribute indices
            primary_key_indices = self.saved_temp_layer.primaryKeyAttributes()
            print(f"Primary key indices are : {primary_key_indices}")

            # Identify the feature_id field name and value from the accepted feature
            # Assuming 'feature_id' is a field in your layer. Adjust if different.
            feature_id_field_name = 'feature_id'  # Replace with the actual field name
            accepted_feature_id = accepted_feature[feature_id_field_name]

            # Prepare attribute map for updating existing features
            attributes = {}
            fields = accepted_feature.fields() # gets the fields of accepted_feature
            for field in fields: # looping in all the fields
                field_index = fields.indexOf(field.name()) # get field index to check if it is a primary key
                if field_index not in primary_key_indices: # if field is not a primary key
                    attributes[field.name()] = accepted_feature[field.name()] # append attribute value to update in layer

            # Update features in saved_temp_layer
            with edit(self.saved_temp_layer):
                request = QgsFeatureRequest()
                request.setFilterExpression(f'"{feature_id_field_name}" = \'{accepted_feature_id}\'')
                for feat in self.saved_temp_layer.getFeatures(request):
                    # Update attributes
                    for key, value in attributes.items():
                        feat[key] = value
                    self.saved_temp_layer.updateFeature(feat)

            print(f"Updated features in saved_temp_layer with {feature_id_field_name} = {accepted_feature_id}")
        else:
            print("saved_temp_layer is None. Layer might not be initialized yet.")

        # Move to the next feature
        self.current_feature_index += 1
        if self.current_feature_index < len(self.data):
            new_attr_frame = self.create_attribute_tables_frame()
            self.dialog.layout().replaceWidget(self.dialog.layout().itemAt(1).widget(), new_attr_frame)
            self.update_canvases()
        else:
            self.set_colour_opacity(self.saved_temp_layer, 1)  # Adjust the opacity for better visualization
            self.set_colour_opacity(self.selected_layer_for_processing, 1)
            QMessageBox.information(None, "Review Complete", "All features have been reviewed.")
            self.dialog.accept()
            

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
            feature_ids = list(self.data.keys())
            feature_id = feature_ids[self.current_feature_index]
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
                self.zoom_to_feature_on_canvas(extent, self.left_canvas, self.selected_layer_for_processing, feature_id)  # Zoom the left canvas to the feature
                self.zoom_to_feature_on_canvas(extent, self.right_canvas, self.saved_temp_layer, feature_id)  # Zoom the right canvas to the feature
            else:
                # Log a warning if the feature cannot be found
                QgsMessageLog.logMessage(
                    f"Feature with feature_id {feature_id} not found in the .amrut file.",
                    "AMRUT",
                    Qgis.Warning
                )            

    def zoom_to_feature_on_canvas(self, extent, canvas, layer, feature_id):
        """Zoom to the feature's bounding box on the canvas."""
        if layer:
            # Apply a filter to show only the specific feature
            layer.setSubsetString(f"feature_id = {feature_id}")
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
            buffer = line_length * 0.25  # Use half the line length as the buffer
        elif geometry_type == QgsWkbTypes.PolygonGeometry:
            bbox = geometry.boundingBox()  # Get the bounding box of the polygon
            bbox_width = bbox.width()  # Width of the bounding box
            bbox_height = bbox.height()  # Height of the bounding box
            diagonal = (bbox_width**2 + bbox_height**2) ** 0.5  # Calculate the diagonal length
            buffer = diagonal * 0.5  # Use half the diagonal length as the buffer
        else:
            buffer = 0.0001  # Default buffer size for unsupported geometry types

        return buffer  # Return the calculated buffer size
