from PyQt5.QtWidgets import QDialog, QHBoxLayout, QVBoxLayout, QLabel
from PyQt5.QtCore import Qt, QTimer
from qgis.core import QgsProject, QgsVectorLayer, QgsCoordinateTransform, QgsRasterLayer, QgsProcessingFeedback, QgsProcessingContext, QgsMessageLog, Qgis, QgsPointXY
from qgis.gui import QgsMapCanvas, QgsMapToolPan
from PyQt5.QtGui import QColor
from . import verification_dialog
from qgis.core import QgsCoordinateReferenceSystem

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
        self.left_canvas = None
        self.right_canvas = None
        self.synchronizing = False  # Prevent infinite synchronization loops

        # Main layout
        layout = QHBoxLayout(self)

        layer = self.get_layer_by_name(self.selected_layer_name)
        raster_layer = self.get_layer_by_name(self.selected_raster_layer_name) if self.selected_raster_layer_name else None

        # DEBUG: Log layer information
        if layer:
            QgsMessageLog.logMessage(f"[DEBUG] Original layer found: {layer.name()}, Valid: {layer.isValid()}, Features: {layer.featureCount()}", 'AMRUT', Qgis.Info)
        else:
            QgsMessageLog.logMessage(f"[DEBUG] Original layer '{self.selected_layer_name}' not found", 'AMRUT', Qgis.Warning)

        if raster_layer:
            QgsMessageLog.logMessage(f"[DEBUG] Raster layer found: {raster_layer.name()}, Valid: {raster_layer.isValid()}", 'AMRUT', Qgis.Info)

        if layer:
            left_panel, self.left_canvas = self.create_layer_visualization_panel(layer, f"{self.selected_layer_name} (Original Data)", raster_layer)
        else:
            left_panel, self.left_canvas = self.create_error_panel(f"Layer '{self.selected_layer_name}' not found in the project."), None
        layout.addLayout(left_panel)

        # Add a vertical divider
        self.add_vertical_divider(layout)

        # Add right panel
        right_panel, self.right_canvas = self.create_geojson_visualization_panel(raster_layer)
        layout.addLayout(right_panel)

        # Synchronize the views of both canvases
        self.is_synchronizing = False  # Flag to avoid recursive synchronization
        if self.left_canvas and self.right_canvas:
            self.left_canvas.extentsChanged.connect(self.synchronize_right_canvas)
            self.right_canvas.extentsChanged.connect(self.synchronize_left_canvas)

        self.setup_panning()

        # Delay the feature dialog to ensure UI is fully loaded
        QTimer.singleShot(2000, lambda: self.show_new_feature_dialog(layer))

    def show_new_feature_dialog(self, layer):
        try:
            if layer:
                newFeatureFound = verification_dialog.VerificationDialog(self.selected_layer_name, self.selected_raster_layer_name, self.amrut_file_path, self.grid_extent)
                newFeatureFound.check_for_new_features()
                layer.setSubsetString("")
                symbol = layer.renderer().symbol()  # Get the symbol for the layer          
                if symbol:
                    symbol.setOpacity(1)  # Set the opacity of the symbol
                renderer = layer.renderer()
                if renderer:
                    symbol = renderer.symbol()
                    if symbol:
                        QgsMessageLog.logMessage(f"[DEBUG] Symbol opacity: {symbol.opacity()}", "AMRUT", Qgis.Info)
                        QgsMessageLog.logMessage(f"[DEBUG] Symbol color: {symbol.color().name()}", "AMRUT", Qgis.Info)
                    else:
                        QgsMessageLog.logMessage("[DEBUG] No symbol found", "AMRUT", Qgis.Warning)
                else:
                    QgsMessageLog.logMessage("[DEBUG] No renderer found", "AMRUT", Qgis.Warning)

                layer.triggerRepaint()  # Trigger a repaint to apply the changes
        except Exception as e:
            QgsMessageLog.logMessage(f"Error in show_new_feature_dialog: {str(e)}", 'AMRUT', Qgis.Critical)

    def synchronize_right_canvas(self):
        """Synchronize the right canvas with the left canvas."""
        if not self.is_synchronizing and self.right_canvas:  # Check if right_canvas exists
            self.is_synchronizing = True  # Mark synchronization in progress
            self.right_canvas.setExtent(self.left_canvas.extent())  # Set the extent of the right canvas to match the left canvas
            self.right_canvas.refresh()  # Refresh the right canvas to update its display
            self.is_synchronizing = False  # Reset the synchronization flag

    def synchronize_left_canvas(self):
        """Synchronize the left canvas with the right canvas."""
        if not self.is_synchronizing and self.left_canvas:  # Check if left_canvas exists
            self.is_synchronizing = True  # Mark synchronization in progress
            self.left_canvas.setExtent(self.right_canvas.extent())  # Set the extent of the left canvas to match the right canvas
            self.left_canvas.refresh()  # Refresh the left canvas to update its display
            self.is_synchronizing = False  # Reset the synchronization flag

    def setup_panning(self):
        """Enable panning on both canvases."""
        try:
            if self.left_canvas:
                self.left_pan_tool = QgsMapToolPan(self.left_canvas)
                self.left_canvas.setMapTool(self.left_pan_tool)
            
            if self.right_canvas:
                self.right_pan_tool = QgsMapToolPan(self.right_canvas)
                self.right_canvas.setMapTool(self.right_pan_tool)
        except Exception as e:
            QgsMessageLog.logMessage(f"Error in setup_panning: {str(e)}", 'AMRUT', Qgis.Critical)

    def create_geojson_visualization_panel(self, raster_layer):
        """Create a panel to visualize the GeoJSON extracted from the AMRUT file."""
        try:
            panel_layout = QVBoxLayout()

            # Load GeoJSON from AMRUT file
            geojson_layer = self.load_geojson_from_amrut(self.amrut_file_path, self.selected_layer_name)

            if geojson_layer and geojson_layer.isValid():
                temporary_layer_name = f"Temporary_{self.selected_layer_name}"
                existing_layer = self.get_layer_by_name(temporary_layer_name)

                if existing_layer:
                    QgsProject.instance().removeMapLayer(existing_layer.id())

                geojson_layer.setName(temporary_layer_name)
                
                # Add to project BEFORE creating visualization
                QgsProject.instance().addMapLayer(geojson_layer)

                QgsMessageLog.logMessage(f"[DEBUG] GeoJSON layer added: {geojson_layer.name()}, Valid: {geojson_layer.isValid()}, Features: {geojson_layer.featureCount()}", 'AMRUT', Qgis.Info)

                panel_layout, map_canvas = self.create_layer_visualization_panel(
                    geojson_layer,
                    f"{self.selected_layer_name} (Field Data)",
                    raster_layer
                )

                return panel_layout, map_canvas
            else:
                QgsMessageLog.logMessage(f"[DEBUG] Failed to load GeoJSON for layer: {self.selected_layer_name}", 'AMRUT', Qgis.Warning)
                panel_layout = self.create_error_panel(f"Layer '{self.selected_layer_name}' is invalid in .AMRUT file")
                return panel_layout, None

        except Exception as e:
            QgsMessageLog.logMessage(f"Error in create_geojson_visualization_panel: {str(e)}", 'AMRUT', Qgis.Critical)
            panel_layout = self.create_error_panel(f"Error loading GeoJSON: {str(e)}")
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

                    # Add the temporary file path to the list for cleanup
                    self.temporary_files.append(temp_geojson_file_path)
                    
                    # Load the GeoJSON into a vector layer using the temporary file path
                    geojson_layer = QgsVectorLayer(temp_geojson_file_path, layer_name, "ogr")
                    if not geojson_layer.isValid():
                        QgsMessageLog.logMessage(f"[DEBUG] GeoJSON layer invalid, error: {geojson_layer.error().message()}", 'AMRUT', Qgis.Critical)
                        return None

                    original_layer = self.get_layer_by_name(self.selected_layer_name)
                    
                    # Set CRS if undefined
                    if not geojson_layer.crs().isValid() and original_layer:
                        geojson_layer.setCrs(original_layer.crs())
                        geojson_layer.updateExtents()

                    # Reproject if CRS doesn't match original
                    if original_layer and geojson_layer.crs() != original_layer.crs():
                        processing_context = QgsProcessingContext()
                        feedback = QgsProcessingFeedback()
                        reproject_params = {
                            'INPUT': geojson_layer,
                            'TARGET_CRS': original_layer.crs().authid(),
                            'OUTPUT': 'memory:'
                        }
                        result = processing.run("native:reprojectlayer", reproject_params, context=processing_context, feedback=feedback)
                        geojson_layer = result['OUTPUT']
                        geojson_layer.setName(f"Temporary_{layer_name}")
                        geojson_layer.updateExtents()

                    QgsMessageLog.logMessage(
                        f"GeoJSON valid: {geojson_layer.isValid()}, CRS: {geojson_layer.crs().authid()}, Extent: {geojson_layer.extent().toString()}, Features: {geojson_layer.featureCount()}",
                        'AMRUT', Qgis.Info
                    )

                    return geojson_layer
                else:
                    QgsMessageLog.logMessage(f"[DEBUG] GeoJSON file {geojson_filename} not found in AMRUT archive", 'AMRUT', Qgis.Warning)
                    return None
            
        except Exception as e:
            QgsMessageLog.logMessage(f"Error loading GeoJSON: {str(e)}", 'AMRUT', Qgis.Critical)
            return None

    def get_layer_by_name(self, layer_name):
        """Retrieve a layer from the QGIS project by its name."""
        try:
            if not layer_name:
                return None
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
            if not layer_name:
                return
            for layer in QgsProject.instance().mapLayers().values():
                if layer.name() == layer_name:
                    QgsProject.instance().removeMapLayer(layer.id())
                    break
        except Exception as e:
            QgsMessageLog.logMessage(f"Error in remove_layer_by_name: {str(e)}", 'AMRUT', Qgis.Critical)

    def create_layer_visualization_panel(self, layer, title, raster_layer):
        """Create a panel to visualize a specific project layer."""
        try:
            panel_layout = QVBoxLayout()
            
            # Create the label with larger and bold text
            label = QLabel(title)
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet("font-size: 12px; font-weight: bold;")  # Set font size and bold style
            
            panel_layout.addWidget(label)

            # Transform raster CRS if needed and raster layer exists
            if raster_layer and self.reprojected_raster_layer is None:
                self.transform_raster_CRS(layer, raster_layer)

            # Create the map canvas and add it to the panel
            map_canvas = self.create_map_canvas(layer)
            if map_canvas:
                panel_layout.addWidget(map_canvas)
            else:
                error_label = QLabel("Failed to create map canvas")
                panel_layout.addWidget(error_label)

            return panel_layout, map_canvas
        except Exception as e:
            QgsMessageLog.logMessage(f"Error in create_layer_visualization_panel: {str(e)}", 'AMRUT', Qgis.Critical)
            return self.create_error_panel(f"Error creating visualization: {str(e)}"), None
        
    def transform_raster_CRS(self, layer, raster_layer):
        """Transform raster layer CRS to match vector layer CRS."""
        try:
            if not layer or not raster_layer:
                return

            existing_layer = None
            grid_crs = layer.crs()
            raster_crs = raster_layer.crs()
            
            QgsMessageLog.logMessage(f"Raster Layer Name: {raster_layer.name()}", 'AMRUT', Qgis.Info)
            QgsMessageLog.logMessage(f"Raster Layer Valid: {raster_layer.isValid()}", 'AMRUT', Qgis.Info)
            QgsMessageLog.logMessage(f"Raster Source Path: {raster_layer.source()}", 'AMRUT', Qgis.Info)
            QgsMessageLog.logMessage(f"Raster CRS: {raster_crs.authid()}", 'AMRUT', Qgis.Info)
            QgsMessageLog.logMessage(f"Grid CRS: {grid_crs.authid()}", 'AMRUT', Qgis.Info)
            
            # Check if we need to reproject
            if raster_crs.authid() == grid_crs.authid():
                self.reprojected_raster_layer = raster_layer
                return

            # Remove existing temporary raster if exists
            if self.reprojected_raster_layer is None:
                self.remove_layer_by_name(f"Temporary_{raster_layer.name()}")
            else:
                for lyr in QgsProject.instance().mapLayers().values():
                    if lyr.name() == f"Temporary_{raster_layer.name()}" and isinstance(lyr, QgsRasterLayer):
                        existing_layer = lyr
                        break

            if existing_layer:
                self.reprojected_raster_layer = existing_layer
            else:
                if not os.path.isfile(raster_layer.source()):
                    QgsMessageLog.logMessage(f"Raster layer '{raster_layer.name()}' is not file-based or lacks a valid source path.", 'AMRUT', Qgis.Warning)
                    self.reprojected_raster_layer = raster_layer  # Use original if can't reproject
                    return

                # Setup processing context
                processing_context = QgsProcessingContext()
                feedback = QgsProcessingFeedback()

                # Reproject full raster
                reproject_params = {
                    'INPUT': raster_layer.source(),
                    'SOURCE_CRS': raster_crs.authid(),
                    'TARGET_CRS': grid_crs.authid(),
                    'RESAMPLING': 0,
                    'NODATA': -9999,
                    'OUTPUT': 'TEMPORARY_OUTPUT'
                }

                try:
                    reprojected_result = processing.run("gdal:warpreproject", reproject_params, context=processing_context, feedback=feedback)
                    temp_raster_path = reprojected_result['OUTPUT']
                    self.temporary_files.append(temp_raster_path)

                    self.reprojected_raster_layer = QgsRasterLayer(temp_raster_path, f"Temporary_{raster_layer.name()}")

                    if not self.reprojected_raster_layer.isValid():
                        QgsMessageLog.logMessage("Failed to reproject the raster layer.", 'AMRUT', Qgis.Warning)
                        self.reprojected_raster_layer = raster_layer  # Fallback to original
                        return

                    QgsMessageLog.logMessage(
                        f"[Reprojected Raster] CRS: {self.reprojected_raster_layer.crs().authid()}, Extent: {self.reprojected_raster_layer.extent().toString()}",
                        'AMRUT', Qgis.Info
                    )

                    QgsProject.instance().addMapLayer(self.reprojected_raster_layer)
                
                except Exception as e:
                    QgsMessageLog.logMessage(f"Error reprojecting raster: {str(e)}", 'AMRUT', Qgis.Warning)
                    self.reprojected_raster_layer = raster_layer  # Fallback to original

        except Exception as e:
            QgsMessageLog.logMessage(f"Error in transform_raster_CRS: {str(e)}", 'AMRUT', Qgis.Critical)
            self.reprojected_raster_layer = raster_layer if raster_layer else None

    def create_map_canvas(self, layer):
        """Create a map canvas to render the given layer."""
        try:
            if not layer or not layer.isValid():
                QgsMessageLog.logMessage(f"[Canvas] Invalid layer provided", 'AMRUT', Qgis.Warning)
                return None

            canvas = QgsMapCanvas()
            canvas.setCanvasColor(QColor("white"))

            # CRITICAL FIX: Proper layer ordering with vector on top
            layers_to_add = []
            
            # Add vector layer first (will be rendered on top)
            if layer and layer.isValid():
                layers_to_add.append(layer)
                QgsMessageLog.logMessage(f"[Canvas] Added vector layer: {layer.name()}", 'AMRUT', Qgis.Info)
            
            # Add raster layer second (will be rendered at bottom)
            if self.reprojected_raster_layer and self.reprojected_raster_layer.isValid():
                layers_to_add.append(self.reprojected_raster_layer)
                QgsMessageLog.logMessage(f"[Canvas] Added raster layer: {self.reprojected_raster_layer.name()}", 'AMRUT', Qgis.Info)

            if not layers_to_add:
                QgsMessageLog.logMessage("[Canvas] No valid layers to add", 'AMRUT', Qgis.Warning)
                return None

            # Set layers with proper ordering
            canvas.setLayers(layers_to_add)                  

            # Set extent - prioritize layer extent, fallback to grid extent
            if layer and layer.isValid() and not layer.extent().isEmpty():
                canvas.setExtent(layer.extent())
                QgsMessageLog.logMessage(f"[Canvas] Set extent from layer: {layer.extent().toString()}", 'AMRUT', Qgis.Info)
            elif self.grid_extent and not self.grid_extent.isEmpty():
                canvas.setExtent(self.grid_extent)
                QgsMessageLog.logMessage(f"[Canvas] Set extent from grid: {self.grid_extent.toString()}", 'AMRUT', Qgis.Info)
            else:
                QgsMessageLog.logMessage("[Canvas] No valid extent available", 'AMRUT', Qgis.Warning)

            # Set a minimum size for the canvas
            canvas.setMinimumSize(400, 300)
            
            # Force refresh to apply changes
            canvas.refresh()
            canvas.update()
            
            QgsMessageLog.logMessage(
                f"[Canvas Setup] Layer: {layer.name()}, Valid: {layer.isValid()}, "
                f"Features: {layer.featureCount()}, Extent: {layer.extent().toString()}",
                'AMRUT', Qgis.Info
            )
            return canvas
        except Exception as e:
            QgsMessageLog.logMessage(f"Error in create_map_canvas: {str(e)}", 'AMRUT', Qgis.Critical)
            return None

    def create_error_panel(self, message):
        """Create a panel to display an error message."""
        try:
            panel_layout = QVBoxLayout()
            error_label = QLabel(message)
            error_label.setAlignment(Qt.AlignCenter)
            error_label.setStyleSheet("color: red; font-weight: bold;")
            panel_layout.addWidget(error_label)
            return panel_layout
        except Exception as e:
            QgsMessageLog.logMessage(f"Error in create_error_panel: {str(e)}", 'AMRUT', Qgis.Critical)
            return QVBoxLayout()

    def add_vertical_divider(self, layout):
        """Add a vertical divider to the layout."""
        try:
            line = QLabel()
            line.setFixedWidth(2)
            line.setStyleSheet("background-color: gray;")
            layout.addWidget(line)
        except Exception as e:
            QgsMessageLog.logMessage(f"Error in add_vertical_divider: {str(e)}", 'AMRUT', Qgis.Critical)

    def closeEvent(self, event):
        """Override closeEvent to remove temporary layers and refresh the map canvas."""
        try:
            # Remove temporary layers
            self.remove_layer_by_name(f"Temporary_{self.selected_layer_name}")
            if self.selected_raster_layer_name:
                self.remove_layer_by_name(f"Temporary_{self.selected_raster_layer_name}")

            # Delete all temporary files
            for temp_file in self.temporary_files:
                if os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                    except Exception as e:
                        QgsMessageLog.logMessage(f"Error deleting temp file {temp_file}: {str(e)}", 'AMRUT', Qgis.Warning)
            
            # Refresh map canvas in main QGIS interface
            if hasattr(self, 'iface') and self.iface:
                self.iface.mapCanvas().refresh()

        except Exception as e:
            QgsMessageLog.logMessage(f"Error in closeEvent cleanup: {str(e)}", 'AMRUT', Qgis.Critical)
        finally:
            super().closeEvent(event)