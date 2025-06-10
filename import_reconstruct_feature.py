from PyQt5.QtWidgets import (
    QDialog, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QFrame, QMessageBox,
    QTableWidget, QTableWidgetItem, QGroupBox, QSizePolicy, QHeaderView,
    QScrollArea, QGroupBox, QApplication, QWidget
)
from PyQt5.QtCore import Qt, QThread, QEventLoop
from PyQt5.QtGui import QPixmap, QColor

from qgis.core import (
    QgsProject, QgsRectangle, QgsMessageLog, Qgis, QgsWkbTypes, QgsFeature, QgsFeatureRequest, edit, QgsVectorLayer, QgsProcessingFeatureSourceDefinition, QgsCategorizedSymbolRenderer, QgsRenderContext, QgsSingleSymbolRenderer,
    QgsRendererCategory,
    QgsSymbol,
    QgsVectorFileWriter, 
    QgsCoordinateTransformContext
)
from qgis.gui import QgsMapCanvas, QgsMapToolPan
from . import import_workers
import processing
import random
import base64
from osgeo import ogr

class ReconstructFeatures:
    """
    A class that handles the reconstruction and verification of features in QGIS.
    This class provides functionality to compare original and vetted data, 
    allowing users to review and merge feature attributes.
    """
    
    def __init__(self, selected_layer, selected_raster_layer, data, progress_bar, progress_lable):
        """
        Initialize the ReconstructFeatures class with necessary layers and UI components.
        
        Args:
            selected_layer: The original vector layer selected for processing
            selected_raster_layer: The raster layer to be used as background
            data: Dictionary containing broken features data to be reviewed
            progress_bar: UI progress bar component for showing operation progress
            progress_lable: UI label for progress status text
        """
        # Store the original layer for processing
        self.selected_layer_for_processing = selected_layer
        
        # Get the temporary layer that was previously saved
        self.saved_temp_layer = self.get_layer_by_name("Temporary_"+selected_layer.name())
        
        # Log extent information for debugging
        if self.saved_temp_layer:
            ext = self.saved_temp_layer.extent()
            QgsMessageLog.logMessage(f"Temp layer extent: {ext.toString()}", 'AMRUT', Qgis.Info)
        else:
            QgsMessageLog.logMessage("saved_temp_layer is None!", 'AMRUT', Qgis.Critical)
        
        # Store raster layer and data references
        self.selected_raster_layer = selected_raster_layer
        self.data = data 
        self.reprojected_raster_layer = None
        
        # Initialize feature index counter for navigation through broken features
        self.current_feature_index = 0
        
        # Store UI components for progress tracking
        self.progress_bar = progress_bar
        self.progress_lable = progress_lable
        
        # Ensure CRS compatibility between temp layer and original layer
        if self.saved_temp_layer and self.selected_layer_for_processing:
            if self.saved_temp_layer.crs() != self.selected_layer_for_processing.crs():
                # Match CRS without transforming coordinates (just metadata)
                self.saved_temp_layer.setCrs(self.selected_layer_for_processing.crs())
                QgsMessageLog.logMessage("CRS mismatch detected. Set saved_temp_layer CRS to match original layer.", 'AMRUT', Qgis.Warning)

        # Validate the temporary layer
        if not self.saved_temp_layer or not self.saved_temp_layer.isValid():
            QgsMessageLog.logMessage("saved_temp_layer is None or invalid!", 'AMRUT', Qgis.Critical)
        else:
            QgsMessageLog.logMessage(f"Loaded saved_temp_layer with {self.saved_temp_layer.featureCount()} features", 'AMRUT', Qgis.Info)

    def apply_colour(self, layer):
        """
        Apply random colors to each feature in the layer for better visualization.
        Each feature gets a unique color based on its feature ID.
        
        Args:
            layer: The vector layer to apply coloring to
        """
        # Create a categorized renderer based on feature IDs
        renderer = QgsCategorizedSymbolRenderer("$id", [])  # Use $id (QGIS internal unique feature ID)

        # Iterate through all features and assign random colors
        for feature in layer.getFeatures():
            unique_id = feature.id()  # Use feature ID to ensure uniqueness
            
            # Generate a random RGB color
            color = QColor(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
            
            # Create default symbol for the layer's geometry type
            symbol = QgsSymbol.defaultSymbol(layer.geometryType())
            symbol.setColor(color)
            
            # Increase line width for better visibility if it's a line layer
            if layer.geometryType() == QgsWkbTypes.LineGeometry:
                symbol.setWidth(symbol.width() * 5)  # Apply width increase again
            
            # Create and add category to renderer
            category = QgsRendererCategory(unique_id, symbol, f"Feature {unique_id}")
            renderer.addCategory(category)

        # Apply the renderer to the layer and refresh display
        layer.setRenderer(renderer)
        layer.triggerRepaint()

    def increase_line_width(self, layer):
        """
        Increase the line width for better visibility in line geometry layers.
        
        Args:
            layer: The vector layer to modify line width for
        """
        # Only apply to line geometry layers
        if layer.geometryType() == QgsWkbTypes.LineGeometry:
            # Create default symbol and increase width
            symbol = QgsSymbol.defaultSymbol(layer.geometryType())
            symbol.setWidth(symbol.width() * 5)  # Increase width by factor of 5
            
            # Apply new renderer with modified symbol
            layer.setRenderer(QgsSingleSymbolRenderer(symbol))
            layer.triggerRepaint()  # Refresh the layer display

    def merge_attribute_dialog(self):
        """
        Show the main dialog for verifying features in full-screen mode.
        This creates a comprehensive interface with dual map canvases and attribute tables.
        """
        # Create main dialog window
        dialog = QDialog(None)
        dialog.setWindowTitle("Merge Feature Attribute")
        dialog.setWindowState(Qt.WindowMaximized)  # Set to full-screen/maximized

        # Create main vertical layout for the dialog
        main_layout = QVBoxLayout(dialog)

        # Create horizontal layout for side-by-side map canvases (top section)
        top_canvas_layout = QHBoxLayout()
        
        # Apply visual styling to layers for better comparison
        self.apply_colour(self.saved_temp_layer)  # Color vetted data
        self.increase_line_width(self.selected_layer_for_processing)  # Enhance original data visibility
        
        # Ensure raster layer is in correct CRS for overlay
        self.transform_raster_CRS(self.selected_layer_for_processing, self.selected_raster_layer)

        # Create left canvas frame for original data
        left_canvas_frame = self.create_canvas_frame("Original Data", self.selected_layer_for_processing)
        # Create right canvas frame for vetted data
        right_canvas_frame = self.create_canvas_frame("Vetted Data", self.saved_temp_layer)

        # Add both canvas frames to horizontal layout
        top_canvas_layout.addWidget(left_canvas_frame)
        top_canvas_layout.addWidget(right_canvas_frame)
        
        # Add top section to main layout with stretch factor (1/3 of screen)
        main_layout.addLayout(top_canvas_layout, stretch=1)

        # Create bottom section for attribute tables of broken features
        bottom_attr_frame = self.create_attribute_tables_frame()
        # Add bottom section with higher stretch factor (2/3 of screen)
        main_layout.addWidget(bottom_attr_frame, stretch=2)

        # Initialize navigation and store dialog references
        self.current_feature_index = 0
        self.dialog = dialog
        self.left_canvas = left_canvas_frame.findChild(QgsMapCanvas)
        self.right_canvas = right_canvas_frame.findChild(QgsMapCanvas)

        # Set up canvas synchronization to keep views aligned
        self.is_synchronizing = False  # Flag to prevent recursive synchronization
        self.left_canvas.extentsChanged.connect(self.synchronize_right_canvas)
        self.right_canvas.extentsChanged.connect(self.synchronize_left_canvas)
        
        # Enable panning tools on both canvases
        self.setup_panning()

        # Update canvases to show current feature and display dialog
        self.update_canvases()
        dialog.exec_()

    def transform_raster_CRS(self, layer, raster_layer):
        """
        Transform raster layer to match the vector layer's CRS using a background worker.
        This ensures proper overlay alignment between raster and vector data.
        
        Args:
            layer: Reference vector layer for CRS matching
            raster_layer: Raster layer to be transformed
        """
        # Set progress bar to indeterminate mode during transformation
        self.progress_bar.setRange(0, 0)
        self.progress_bar.show()
        
        # Check if raster layer exists and if transformation is needed
        if raster_layer:
            reprojected_raster_layer_name = "Temporary_"+raster_layer.name()
            print(reprojected_raster_layer_name)
            self.reprojected_raster_layer = self.get_layer_by_name(reprojected_raster_layer_name)

        # Skip transformation if no raster or already exists
        if not raster_layer or self.reprojected_raster_layer:
            # Reset progress bar and exit
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(100)
            self.progress_lable.setText("")
            self.progress_bar.setVisible(False)
            return

        # Show progress bar and process events
        self.progress_bar.show()
        QApplication.processEvents()

        # Create worker thread for raster transformation
        self.worker = import_workers.RasterTransformWorker(layer, raster_layer)
        self.thread = QThread()

        # Move worker to separate thread for non-blocking operation
        self.worker.moveToThread(self.thread)

        # Connect thread signals
        self.thread.started.connect(self.worker.run)
        self.worker.progress_signal.connect(self.progress_bar.setValue)

        # Create event loop to block execution until transformation completes
        event_loop = QEventLoop()

        def on_transformation_finished(raster_layer):
            """
            Handle completion of raster transformation.
            
            Args:
                raster_layer: The transformed raster layer result
            """
            self.reprojected_raster_layer = raster_layer
            
            # Add transformed layer to project if successful
            if raster_layer:
                QgsProject.instance().addMapLayer(self.reprojected_raster_layer)
            else:
                QMessageBox.warning(None, "Error", "Raster transformation failed.")

            # Reset progress bar and hide it
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(100)
            self.progress_lable.setText("")
            self.progress_bar.setVisible(False)
            
            # Exit event loop to continue execution
            event_loop.quit()

        # Connect worker completion signals
        self.worker.finished_signal.connect(on_transformation_finished)
        self.worker.finished_signal.connect(self.thread.quit)
        self.worker.finished_signal.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

        # Start transformation thread
        self.thread.start()

        # Block execution until transformation completes
        event_loop.exec_()

    def create_attribute_tables_frame(self):
        """
        Create a frame containing attribute tables for all broken features 
        in the current feature entry. Tables are displayed horizontally
        with synchronized scrolling.
        
        Returns:
            QScrollArea: Scrollable container with attribute tables
        """
        # Create main container frame
        container = QFrame()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(10)

        # Check if there are features to display
        if self.current_feature_index < len(self.data):
            # Get current feature data
            feature_id = list(self.data.keys())[self.current_feature_index]
            broken_features = self.data[feature_id]

            if broken_features:
                # Store tables for scroll synchronization
                tables = []

                # Create table for each broken feature
                for idx, broken_feature in enumerate(broken_features, start=1):
                    # Create group box container for each feature table
                    group_box = QGroupBox(f"Broken Feature {idx}")
                    group_layout = QVBoxLayout(group_box)

                    # Create and configure attribute table
                    table = QTableWidget()
                    table.setWordWrap(True)
                    table.resizeColumnsToContents()
                    table.resizeRowsToContents()
                    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
                    table.horizontalHeader().setStretchLastSection(True)
                    table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

                    # Populate table based on feature type
                    if isinstance(broken_feature, QgsFeature):
                        # Handle QgsFeature objects
                        fields = broken_feature.fields()
                        num_fields = len(fields)
                        table.setColumnCount(2)
                        table.setRowCount(num_fields)
                        table.setHorizontalHeaderLabels(["Attribute", "Value"])

                        # Populate each field-value pair
                        for row in range(num_fields):
                            field_name = fields.at(row).name()
                            value = broken_feature.attribute(field_name)

                            table.setItem(row, 0, QTableWidgetItem(field_name))

                            # Special handling for photo fields
                            if field_name.lower() == "photo" and value:
                                # Create button for photo viewing
                                button = QPushButton("View Photo")
                                button.setFixedSize(120, 25)
                                button.clicked.connect(lambda _, v=value: self.show_photo_dialog(v))
                                
                                # Create container with padding for button
                                button_container = QWidget()
                                button_layout = QHBoxLayout(button_container)
                                button_layout.setContentsMargins(5, 0, 0, 0)
                                button_layout.addWidget(button)
                                button_layout.setAlignment(Qt.AlignLeft)

                                table.setCellWidget(row, 1, button_container)
                                table.setRowHeight(row, 35)  # Adjust row height for button
                            else:
                                # Regular text field
                                table.setItem(row, 1, QTableWidgetItem(str(value)))
                    else:
                        # Handle non-QgsFeature objects (simple values)
                        table.setColumnCount(1)
                        table.setRowCount(1)
                        table.setHorizontalHeaderLabels(["Value"])
                        table.setItem(0, 0, QTableWidgetItem(str(broken_feature)))

                    # Add table to group box
                    group_layout.addWidget(table)
                    
                    # Create accept button for this feature
                    accept_button = QPushButton("Accept")
                    accept_button.clicked.connect(lambda checked, bf=broken_feature: self.accept_and_next_feature(bf))
                    group_layout.addWidget(accept_button)

                    # Add group box to main layout
                    layout.addWidget(group_box)

                    # Store table reference for synchronization
                    tables.append(table)

                # Set up synchronized scrolling for all tables
                def sync_scrolls(value):
                    """Synchronize vertical scrolling across all tables."""
                    for table in tables:
                        table.verticalScrollBar().setValue(value)

                # Connect each table's scroll bar to synchronization function
                for table in tables:
                    table.verticalScrollBar().valueChanged.connect(lambda value, table=table: sync_scrolls(value))

            else:
                # No broken features available
                layout.addWidget(QLabel("No broken features available."))
        else:
            # All features have been reviewed
            layout.addWidget(QLabel("All features reviewed."))

        # Create scrollable area for the container
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(container)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        return scroll_area

    def show_photo_dialog(self, base64_string):
        """
        Decode and display a base64-encoded image in a popup dialog.
        The dialog size adjusts dynamically based on image dimensions.
        
        Args:
            base64_string: Base64-encoded image data
        """
        try:
            # Decode base64 image data
            image_data = base64.b64decode(base64_string)
            
            # Convert to QPixmap for display
            pixmap = QPixmap()
            if not pixmap.loadFromData(image_data):
                raise ValueError("Failed to load image data")

            # Get original image dimensions
            img_width = pixmap.width()
            img_height = pixmap.height()

            # Define size constraints
            max_width = 9000   # Maximum allowed width
            max_height = 700   # Maximum allowed height
            min_width = 600    # Minimum width for small images
            min_height = 500   # Minimum height for small images

            # Calculate scaled dimensions while preserving aspect ratio
            aspect_ratio = img_width / img_height

            if img_width > max_width or img_height > max_height:
                # Scale down large images
                if aspect_ratio > 1:
                    scaled_width = max_width
                    scaled_height = int(max_width / aspect_ratio)
                else:
                    scaled_height = max_height
                    scaled_width = int(max_height * aspect_ratio)
            else:
                # Ensure minimum size for small images
                scaled_width = max(min_width, img_width)
                scaled_height = max(min_height, img_height)

            # Scale pixmap to calculated dimensions
            pixmap = pixmap.scaled(scaled_width, scaled_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)

            # Create and configure dialog
            dialog = QDialog()
            dialog.setWindowTitle("Photo Preview")
            dialog.resize(scaled_width, scaled_height)

            # Create layout and display image
            layout = QVBoxLayout(dialog)
            label = QLabel()
            label.setPixmap(pixmap)
            label.setAlignment(Qt.AlignCenter)

            layout.addWidget(label)
            dialog.exec_()
            
        except Exception as e:
            # Show error message if image loading fails
            QMessageBox.critical(None, "Error", f"Failed to load image: {str(e)}")
    
    def accept_and_next_feature(self, accepted_feature):
        """
        Store the accepted feature and move to the next feature for review.
        Updates features in saved_temp_layer based on feature_id, excluding primary keys.
        
        Args:
            accepted_feature: The feature that was accepted by the user
        """
        # Reset layer filters to show all features
        self.selected_layer_for_processing.setSubsetString("")
        self.saved_temp_layer.setSubsetString("")
        
        # Check if review is complete
        if not self.data or self.current_feature_index >= len(self.data):
            QMessageBox.information(None, "Review Complete", "All features have been reviewed.")
            self.dialog.accept()
            return

        print(f"Accepted Feature (ID: {accepted_feature.id()}):")

        # Update features in the temporary layer
        if self.saved_temp_layer is not None:
            # Get primary key attribute indices to exclude from updates
            primary_key_indices = self.saved_temp_layer.primaryKeyAttributes()
            print(f"Primary key indices are : {primary_key_indices}")

            # Identify feature_id for matching records
            feature_id_field_name = 'feature_id'  # Field name for feature identification
            accepted_feature_id = accepted_feature[feature_id_field_name]

            # Prepare attributes for update (excluding primary keys)
            attributes = {}
            fields = accepted_feature.fields()
            for field in fields:
                field_index = fields.indexOf(field.name())
                # Only include non-primary key fields
                if field_index not in primary_key_indices:
                    attributes[field.name()] = accepted_feature[field.name()]

            # Update matching features in saved_temp_layer
            with edit(self.saved_temp_layer):
                request = QgsFeatureRequest()
                request.setFilterExpression(f'"{feature_id_field_name}" = \'{accepted_feature_id}\'')
                for feat in self.saved_temp_layer.getFeatures(request):
                    # Update all non-primary key attributes
                    for key, value in attributes.items():
                        feat[key] = value
                    self.saved_temp_layer.updateFeature(feat)

            print(f"Updated features in saved_temp_layer with {feature_id_field_name} = {accepted_feature_id}")
        else:
            print("saved_temp_layer is None. Layer might not be initialized yet.")

        # Move to next feature
        self.current_feature_index += 1
        
        if self.current_feature_index < len(self.data):
            # Create new attribute tables frame for next feature
            new_attr_frame = self.create_attribute_tables_frame()
            self.dialog.layout().replaceWidget(self.dialog.layout().itemAt(1).widget(), new_attr_frame)
            self.update_canvases()
        else:
            # All features reviewed - finalize process
            QMessageBox.information(None, "Review Complete", "All features have been reviewed.")

            # Merge features by attribute to consolidate data
            merged_layer = self.merge_features_by_attribute(self.saved_temp_layer, "feature_id")

            if self.saved_temp_layer is not None:
                # Get original file path for saving
                original_path = self.saved_temp_layer.dataProvider().dataSourceUri().split("|")[0]  
                print(f"Original file path of saved_temp_layer: {original_path}")

                # Generate new layer name
                layer_name = self.saved_temp_layer.name()
                if layer_name.startswith("Temporary_"):
                    layer_name = layer_name[len("Temporary_"):]
                new_layer_name = layer_name + "_vetted"
                
                # Update layer name in project tree
                project = QgsProject.instance()
                root = project.layerTreeRoot()
                layer_node = root.findLayer(self.saved_temp_layer.id())

                if layer_node is not None:
                    layer_node.setName(new_layer_name)
                    print(f"Layer renamed in project to: {new_layer_name}")
                else:
                    print("Layer node not found in layer tree.")

                # Save merged layer if valid
                if merged_layer is not None and merged_layer.isValid():
                    # Get file path and remove old layer
                    temp_layer_path = self.saved_temp_layer.source()  
                    QgsProject.instance().removeMapLayer(self.saved_temp_layer.id())

                    # Save merged layer to file (overwriting existing)
                    options = QgsVectorFileWriter.SaveVectorOptions()
                    options.driverName = "GPKG"
                    options.fileEncoding = "UTF-8"
                    options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
                    QgsVectorFileWriter.writeAsVectorFormatV2(merged_layer, temp_layer_path, QgsCoordinateTransformContext(), options)

                    # Reload updated layer
                    new_layer = QgsVectorLayer(temp_layer_path, new_layer_name, "ogr")

                    if new_layer.isValid():
                        QgsProject.instance().addMapLayer(new_layer)
                        self.saved_temp_layer = new_layer  # Update reference
                    else:
                        print("Error: Failed to reload the updated layer.")
                else:
                    # If merge failed, just rename existing layer
                    self.saved_temp_layer.setName(new_layer_name)
                    print("Merged layer is invalid. Only renaming existing layer.")      

                # Final layer name update and filter reset
                self.saved_temp_layer.setName(new_layer_name)
                self.saved_temp_layer.setSubsetString("")
            else:
                print("saved_temp_layer is None, cannot rename.")

            # Close dialog
            self.dialog.accept()
            
    def merge_features_by_attribute(self, input_layer, attribute):
        """
        Merge features in a layer based on a common attribute using QGIS's Dissolve algorithm.
        This consolidates multiple features with the same attribute value into single features.
        
        Args:
            input_layer: The input vector layer (QgsVectorLayer)
            attribute: The attribute name to dissolve/merge by (string)
            
        Returns:
            QgsVectorLayer: The output layer containing merged features, or None if failed
        """
        print(input_layer)
        
        # Validate input layer
        if not input_layer or not isinstance(input_layer, QgsVectorLayer):
            print("Invalid input layer")
            return None
        
        # Define parameters for dissolve algorithm
        params = {
            'INPUT': QgsProcessingFeatureSourceDefinition(input_layer.source(), selectedFeaturesOnly=False),
            'FIELD': [attribute],  # Field to dissolve/merge by
            'OUTPUT': 'memory:'    # Output to temporary memory layer
        }

        # Execute dissolve algorithm
        result = processing.run("native:dissolve", params)

        # Return the merged output layer
        output_layer = result['OUTPUT']    
        return output_layer
    
    def remove_layer_by_name(self, layer_name):
        """
        Remove a layer from the QGIS project by its name.
        
        Args:
            layer_name: Name of the layer to remove
            
        Returns:
            None
        """
        try:
            # Search for layer by name and remove it
            for layer in QgsProject.instance().mapLayers().values():
                if layer.name() == layer_name:
                    QgsProject.instance().removeMapLayer(layer.id())
                    break
            return None
        except Exception as e:
            QgsMessageLog.logMessage(f"Error in remove_layer_by_name: {str(e)}", 'AMRUT', Qgis.Critical)
            return None
        
    def create_canvas_frame(self, label_text, layer):
        """
        Create a frame containing a labeled map canvas for displaying spatial data.
        
        Args:
            label_text: Text label for the canvas (e.g., "Original Data")
            layer: Vector layer to display in the canvas
            
        Returns:
            QFrame: Frame containing label and map canvas
        """
        # Create container frame with vertical layout
        frame = QFrame()
        frame_layout = QVBoxLayout(frame)

        # Create and style label
        label = QLabel(label_text)
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("font-size: 12px; font-weight: bold;")
        frame_layout.addWidget(label)

        # Create map canvas and configure layers
        canvas = QgsMapCanvas()
        
        # Set opacity for better layer visualization
        self.set_colour_opacity(self.saved_temp_layer, 0.6)
        self.set_colour_opacity(self.selected_layer_for_processing, 0.6)
        
        # Set layers to display (vector layer on top of raster)
        canvas.setLayers([layer, self.reprojected_raster_layer])
        canvas.setCanvasColor(QColor("white"))  # White background
        canvas.refresh()  # Refresh display
        
        frame_layout.addWidget(canvas)
        return frame
    
    def set_colour_opacity(self, layer, opacity):
        """
        Set the opacity of all symbols in a layer for better visualization.
        
        Args:
            layer: Vector layer to modify
            opacity: Opacity value (0.0 to 1.0)
        """
        # Get all symbols from the layer's renderer
        context = QgsRenderContext()
        symbols = layer.renderer().symbols(context)
         
        # Set opacity for each symbol
        for symbol in symbols:
            symbol.setOpacity(opacity)
            
        # Refresh layer display
        layer.triggerRepaint()

    def synchronize_right_canvas(self):
        """
        Synchronize the right canvas extent with the left canvas.
        Prevents infinite loop with synchronization flag.
        """
        if not self.is_synchronizing:
            self.is_synchronizing = True
            self.right_canvas.setExtent(self.left_canvas.extent())
            self.right_canvas.refresh()
            self.is_synchronizing = False

    def synchronize_left_canvas(self):
        """
        Synchronize the left canvas extent with the right canvas.
        Prevents infinite loop with synchronization flag.
        """
        if not self.is_synchronizing:
            self.is_synchronizing = True
            self.left_canvas.setExtent(self.right_canvas.extent())
            self.left_canvas.refresh()
            self.is_synchronizing = False

    def setup_panning(self):
        """
        Enable panning tools on both map canvases for user navigation.
        """
        try:
            if self.left_canvas and self.right_canvas:
                # Create pan tools for each canvas
                self.left_pan_tool = QgsMapToolPan(self.left_canvas)
                self.right_pan_tool = QgsMapToolPan(self.right_canvas)

                # Set pan tools as active tools
                self.left_canvas.setMapTool(self.left_pan_tool)
                self.right_canvas.setMapTool(self.right_pan_tool)
        except Exception as e:
            QgsMessageLog.logMessage(f"Error in setup_panning: {str(e)}", 'AMRUT', Qgis.Critical)

    def update_canvases(self):
        """
            Update canvases to focus on the current feature.
            Zooms both canvases to the bounding box of the feature being verified.
        """
        # Ensure there are still features to process
        if self.current_feature_index < len(self.data):
            # Get all feature IDs from the data dictionary
            feature_ids = list(self.data.keys())
            
            # Get the current feature ID based on the index
            feature_id = feature_ids[self.current_feature_index]
            
            # Fetch the feature from the selected layer using the feature ID
            # Uses a filter expression to find the specific feature
            feature = next(self.selected_layer_for_processing.getFeatures(f"feature_id = {feature_id}"), None)
            
            if feature:
                # Calculate the geometric center of the feature
                centroid_geom = feature.geometry().centroid()
                
                # Convert the centroid geometry to a point coordinate
                centroid_point = centroid_geom.asPoint()
                
                # Calculate an appropriate buffer size based on the feature's geometry
                buffer = self.calculate_dynamic_buffer(feature.geometry())
                
                # Create a rectangular extent around the feature's centroid
                # The extent is expanded by the buffer in all directions
                extent = QgsRectangle(
                    centroid_point.x() - buffer,  # Left boundary
                    centroid_point.y() - buffer,  # Bottom boundary
                    centroid_point.x() + buffer,  # Right boundary
                    centroid_point.y() + buffer   # Top boundary
                )
                
                # Zoom the left canvas to show the feature from the processing layer
                self.zoom_to_feature_on_canvas(extent, self.left_canvas, self.selected_layer_for_processing, feature_id)
                
                # Zoom the right canvas to show the feature from the temporary saved layer
                self.zoom_to_feature_on_canvas(extent, self.right_canvas, self.saved_temp_layer, feature_id)
            else:
                # Log a warning message if the feature cannot be found in the layer
                QgsMessageLog.logMessage(
                    f"Feature with feature_id {feature_id} not found in the .amrut file.",
                    "AMRUT",
                    Qgis.Warning
                )            

    def zoom_to_feature_on_canvas(self, extent, canvas, layer, feature_id):
        """
        Zoom to the feature's bounding box on the canvas.
        
        Args:
            extent: QgsRectangle defining the area to zoom to
            canvas: The map canvas to update
            layer: The layer containing the feature
            feature_id: ID of the feature to highlight
        """
        if layer:
            # Apply a subset filter to display only the specific feature
            # This hides all other features in the layer
            layer.setSubsetString(f"feature_id = {feature_id}")
        
        # Set the canvas extent to the calculated bounding box
        canvas.setExtent(extent)
        
        # Refresh the canvas to apply all changes and redraw the map
        canvas.refresh()

    def calculate_dynamic_buffer(self, geometry):
        """
        Calculate a dynamic buffer size based on the geometry type and size.
        
        Args:
            geometry: QgsGeometry object to calculate buffer for
            
        Returns:
            float: Buffer size appropriate for the geometry type
        """
        # Determine the type of geometry (Point, Line, or Polygon)
        geometry_type = QgsWkbTypes.geometryType(geometry.wkbType())
        
        # Calculate buffer size based on geometry type
        if geometry_type == QgsWkbTypes.PointGeometry:
            # For point features, use a small fixed buffer
            buffer = 0.0001
            
        elif geometry_type == QgsWkbTypes.LineGeometry:
            # For line features, calculate buffer based on line length
            line_length = geometry.length()
            buffer = line_length * 0.25  # 25% of the line length
            
        elif geometry_type == QgsWkbTypes.PolygonGeometry:
            # For polygon features, calculate buffer based on bounding box diagonal
            bbox = geometry.boundingBox()
            bbox_width = bbox.width()   # Width of bounding box
            bbox_height = bbox.height() # Height of bounding box
            
            # Calculate diagonal length using Pythagorean theorem
            diagonal = (bbox_width**2 + bbox_height**2) ** 0.5
            buffer = diagonal * 0.5  # 50% of the diagonal length
            
        else:
            # Default buffer for unsupported or unknown geometry types
            buffer = 0.0001
        
        return buffer

    def get_layer_by_name(self, layer_name):
        """
        Retrieve a layer from the QGIS project by its name.
        
        Args:
            layer_name (str): Name of the layer to find
            
        Returns:
            QgsLayer or None: The matching layer object, or None if not found
        """
        try:
            # Iterate through all layers in the current QGIS project
            for layer in QgsProject.instance().mapLayers().values():
                # Check if the layer name matches the requested name
                if layer.name() == layer_name:
                    return layer
            
            # Return None if no matching layer is found
            return None
            
        except Exception as e:
            # Log any errors that occur during layer retrieval
            QgsMessageLog.logMessage(
                f"Error in get_layer_by_name: {str(e)}", 
                'AMRUT', 
                Qgis.Critical
            )
            return None