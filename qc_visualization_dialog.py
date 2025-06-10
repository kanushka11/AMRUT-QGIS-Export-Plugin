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
    """
    Dialog class for visualizing and comparing original GIS data with field data from AMRUT files.
    
    This dialog creates a side-by-side comparison view with:
    - Left panel: Original layer data from QGIS project
    - Right panel: Field data extracted from AMRUT file
    
    Features include synchronized map navigation, raster layer support, and automatic cleanup.
    """
    
    def __init__(self, parent, selected_layer_name, amrut_file_path, selected_raster_layer_name, grid_extent):
        """
        Initialize the Quality Check Visualization Dialog.
        
        Args:
            parent: Parent widget
            selected_layer_name (str): Name of the vector layer to compare
            amrut_file_path (str): Path to the AMRUT file containing field data
            selected_raster_layer_name (str): Name of the background raster layer
            grid_extent: Spatial extent for the visualization
        """
        super().__init__(parent)
        
        # Store initialization parameters
        self.selected_layer_name = selected_layer_name
        self.amrut_file_path = amrut_file_path
        self.selected_raster_layer_name = selected_raster_layer_name
        self.grid_extent = grid_extent
        
        # Initialize tracking variables
        self.temporary_files = []  # List to track temporary files for cleanup
        self.reprojected_raster_layer = None  # Cache for reprojected raster layer
        
        # Configure dialog window
        self.setWindowTitle("AMRUT 2.0")
        self.setWindowState(Qt.WindowMaximized)

        # Initialize map canvas attributes
        self.left_canvas = None   # Canvas for original data
        self.right_canvas = None  # Canvas for field data
        self.synchronizing = False  # Prevent infinite synchronization loops

        # Create main horizontal layout for side-by-side panels
        layout = QHBoxLayout(self)

        # Retrieve layers from QGIS project
        layer = self.get_layer_by_name(self.selected_layer_name)
        raster_layer = self.get_layer_by_name(self.selected_raster_layer_name) if self.selected_raster_layer_name else None

        # DEBUG: Log layer information for troubleshooting
        if layer:
            QgsMessageLog.logMessage(f"[DEBUG] Original layer found: {layer.name()}, Valid: {layer.isValid()}, Features: {layer.featureCount()}", 'AMRUT', Qgis.Info)
        else:
            QgsMessageLog.logMessage(f"[DEBUG] Original layer '{self.selected_layer_name}' not found", 'AMRUT', Qgis.Warning)

        if raster_layer:
            QgsMessageLog.logMessage(f"[DEBUG] Raster layer found: {raster_layer.name()}, Valid: {raster_layer.isValid()}", 'AMRUT', Qgis.Info)

        # Create left panel (original data)
        if layer:
            left_panel, self.left_canvas = self.create_layer_visualization_panel(layer, f"{self.selected_layer_name} (Original Data)", raster_layer)
        else:
            left_panel, self.left_canvas = self.create_error_panel(f"Layer '{self.selected_layer_name}' not found in the project."), None
        layout.addLayout(left_panel)

        # Add visual separator between panels
        self.add_vertical_divider(layout)

        # Create right panel (field data from AMRUT file)
        right_panel, self.right_canvas = self.create_geojson_visualization_panel(raster_layer)
        layout.addLayout(right_panel)

        # Set up synchronized navigation between both map canvases
        self.is_synchronizing = False  # Flag to avoid recursive synchronization
        if self.left_canvas and self.right_canvas:
            # Connect extent change signals for synchronization
            self.left_canvas.extentsChanged.connect(self.synchronize_right_canvas)
            self.right_canvas.extentsChanged.connect(self.synchronize_left_canvas)

        # Enable panning tools for both canvases
        self.setup_panning()

        # Delay the feature verification dialog to ensure UI is fully loaded
        QTimer.singleShot(2000, lambda: self.show_new_feature_dialog(layer))

    def show_new_feature_dialog(self, layer):
        """
        Display the verification dialog for checking new features and update layer rendering.
        
        Args:
            layer: The vector layer to check for new features
        """
        try:
            if layer:
                # Create and run verification dialog
                newFeatureFound = verification_dialog.VerificationDialog(
                    self.selected_layer_name, 
                    self.selected_raster_layer_name, 
                    self.amrut_file_path, 
                    self.grid_extent
                )
                newFeatureFound.check_for_new_features()
                
                # Reset layer filter to show all features
                layer.setSubsetString("")
                
                # Update layer rendering properties
                symbol = layer.renderer().symbol()  # Get the symbol for the layer          
                if symbol:
                    symbol.setOpacity(1)  # Set full opacity for visibility
                    
                # Debug logging for symbol properties
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

                # Force layer refresh to apply changes
                layer.triggerRepaint()
                
        except Exception as e:
            QgsMessageLog.logMessage(f"Error in show_new_feature_dialog: {str(e)}", 'AMRUT', Qgis.Critical)

    def synchronize_right_canvas(self):
        """
        Synchronize the right canvas extent with the left canvas.
        Prevents infinite recursion using synchronization flag.
        """
        if not self.is_synchronizing and self.right_canvas:  # Check if right_canvas exists
            self.is_synchronizing = True  # Mark synchronization in progress
            self.right_canvas.setExtent(self.left_canvas.extent())  # Match extents
            self.right_canvas.refresh()  # Refresh display
            self.is_synchronizing = False  # Reset synchronization flag

    def synchronize_left_canvas(self):
        """
        Synchronize the left canvas extent with the right canvas.
        Prevents infinite recursion using synchronization flag.
        """
        if not self.is_synchronizing and self.left_canvas:  # Check if left_canvas exists
            self.is_synchronizing = True  # Mark synchronization in progress
            self.left_canvas.setExtent(self.right_canvas.extent())  # Match extents
            self.left_canvas.refresh()  # Refresh display
            self.is_synchronizing = False  # Reset synchronization flag

    def setup_panning(self):
        """
        Enable panning tools on both map canvases for user navigation.
        """
        try:
            # Set up panning tool for left canvas
            if self.left_canvas:
                self.left_pan_tool = QgsMapToolPan(self.left_canvas)
                self.left_canvas.setMapTool(self.left_pan_tool)
            
            # Set up panning tool for right canvas
            if self.right_canvas:
                self.right_pan_tool = QgsMapToolPan(self.right_canvas)
                self.right_canvas.setMapTool(self.right_pan_tool)
                
        except Exception as e:
            QgsMessageLog.logMessage(f"Error in setup_panning: {str(e)}", 'AMRUT', Qgis.Critical)

    def create_geojson_visualization_panel(self, raster_layer):
        """
        Create a visualization panel for GeoJSON data extracted from the AMRUT file.
        
        Args:
            raster_layer: Background raster layer for context
            
        Returns:
            tuple: (panel_layout, map_canvas) or (error_panel, None) if failed
        """
        try:
            panel_layout = QVBoxLayout()

            # Extract and load GeoJSON from AMRUT file
            geojson_layer = self.load_geojson_from_amrut(self.amrut_file_path, self.selected_layer_name)

            if geojson_layer and geojson_layer.isValid():
                # Create unique temporary layer name
                temporary_layer_name = f"Temporary_{self.selected_layer_name}"
                
                # Remove any existing temporary layer with same name
                existing_layer = self.get_layer_by_name(temporary_layer_name)
                if existing_layer:
                    QgsProject.instance().removeMapLayer(existing_layer.id())

                # Set layer name and add to project
                geojson_layer.setName(temporary_layer_name)
                QgsProject.instance().addMapLayer(geojson_layer)

                QgsMessageLog.logMessage(f"[DEBUG] GeoJSON layer added: {geojson_layer.name()}, Valid: {geojson_layer.isValid()}, Features: {geojson_layer.featureCount()}", 'AMRUT', Qgis.Info)

                # Create visualization panel for the GeoJSON layer
                panel_layout, map_canvas = self.create_layer_visualization_panel(
                    geojson_layer,
                    f"{self.selected_layer_name} (Field Data)",
                    raster_layer
                )

                return panel_layout, map_canvas
            else:
                # Handle invalid GeoJSON layer
                QgsMessageLog.logMessage(f"[DEBUG] Failed to load GeoJSON for layer: {self.selected_layer_name}", 'AMRUT', Qgis.Warning)
                panel_layout = self.create_error_panel(f"Layer '{self.selected_layer_name}' is invalid in .AMRUT file")
                return panel_layout, None

        except Exception as e:
            QgsMessageLog.logMessage(f"Error in create_geojson_visualization_panel: {str(e)}", 'AMRUT', Qgis.Critical)
            panel_layout = self.create_error_panel(f"Error loading GeoJSON: {str(e)}")
            return panel_layout, None

    def load_geojson_from_amrut(self, amrut_file_path, layer_name):
        """
        Extract and load GeoJSON data from an AMRUT archive file.
        
        Args:
            amrut_file_path (str): Path to the AMRUT zip file
            layer_name (str): Name of the layer to extract
            
        Returns:
            QgsVectorLayer: Loaded GeoJSON layer or None if failed
        """
        try:
            # Open AMRUT file as zip archive
            with zipfile.ZipFile(amrut_file_path, 'r') as zip_ref:
                geojson_filename = f"{layer_name}.geojson"

                # Check if GeoJSON file exists in archive
                if geojson_filename in zip_ref.namelist():
                    # Extract GeoJSON content as text
                    geojson_content = zip_ref.read(geojson_filename).decode('utf-8')

                    # Create temporary file for GeoJSON data
                    temp_dir = tempfile.gettempdir()
                    temp_geojson_file_path = os.path.join(temp_dir, f"Temporary_{geojson_filename}")

                    # Write GeoJSON content to temporary file
                    with open(temp_geojson_file_path, 'w', encoding='utf-8') as temp_geojson_file:
                        temp_geojson_file.write(geojson_content)

                    # Track temporary file for cleanup
                    self.temporary_files.append(temp_geojson_file_path)
                    
                    # Load GeoJSON as vector layer
                    geojson_layer = QgsVectorLayer(temp_geojson_file_path, layer_name, "ogr")
                    if not geojson_layer.isValid():
                        QgsMessageLog.logMessage(f"[DEBUG] GeoJSON layer invalid, error: {geojson_layer.error().message()}", 'AMRUT', Qgis.Critical)
                        return None

                    # Get original layer for CRS reference
                    original_layer = self.get_layer_by_name(self.selected_layer_name)
                    
                    # Set CRS if undefined, using original layer's CRS
                    if not geojson_layer.crs().isValid() and original_layer:
                        geojson_layer.setCrs(original_layer.crs())
                        geojson_layer.updateExtents()

                    # Reproject GeoJSON layer if CRS doesn't match original
                    if original_layer and geojson_layer.crs() != original_layer.crs():
                        # Set up processing context for reprojection
                        processing_context = QgsProcessingContext()
                        feedback = QgsProcessingFeedback()
                        
                        # Configure reprojection parameters
                        reproject_params = {
                            'INPUT': geojson_layer,
                            'TARGET_CRS': original_layer.crs().authid(),
                            'OUTPUT': 'memory:'
                        }
                        
                        # Execute reprojection
                        result = processing.run("native:reprojectlayer", reproject_params, context=processing_context, feedback=feedback)
                        geojson_layer = result['OUTPUT']
                        geojson_layer.setName(f"Temporary_{layer_name}")
                        geojson_layer.updateExtents()

                    # Log layer information for debugging
                    QgsMessageLog.logMessage(
                        f"GeoJSON valid: {geojson_layer.isValid()}, CRS: {geojson_layer.crs().authid()}, "
                        f"Extent: {geojson_layer.extent().toString()}, Features: {geojson_layer.featureCount()}",
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
        """
        Retrieve a layer from the current QGIS project by its name.
        
        Args:
            layer_name (str): Name of the layer to find
            
        Returns:
            QgsMapLayer: Found layer or None if not found
        """
        try:
            if not layer_name:
                return None
                
            # Search through all layers in the project
            for layer in QgsProject.instance().mapLayers().values():
                if layer.name() == layer_name:
                    return layer
            return None
            
        except Exception as e:
            QgsMessageLog.logMessage(f"Error in get_layer_by_name: {str(e)}", 'AMRUT', Qgis.Critical)
            return None
    
    def remove_layer_by_name(self, layer_name):
        """
        Remove a layer from the QGIS project by its name.
        
        Args:
            layer_name (str): Name of the layer to remove
        """
        try:
            if not layer_name:
                return
                
            # Find and remove layer from project
            for layer in QgsProject.instance().mapLayers().values():
                if layer.name() == layer_name:
                    QgsProject.instance().removeMapLayer(layer.id())
                    break
                    
        except Exception as e:
            QgsMessageLog.logMessage(f"Error in remove_layer_by_name: {str(e)}", 'AMRUT', Qgis.Critical)

    def create_layer_visualization_panel(self, layer, title, raster_layer):
        """
        Create a complete visualization panel with title and map canvas for a layer.
        
        Args:
            layer: Vector layer to visualize
            title (str): Title text for the panel
            raster_layer: Background raster layer (optional)
            
        Returns:
            tuple: (panel_layout, map_canvas) or (error_panel, None) if failed
        """
        try:
            panel_layout = QVBoxLayout()
            
            # Create and style the title label
            label = QLabel(title)
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet("font-size: 12px; font-weight: bold;")
            panel_layout.addWidget(label)

            # Transform raster CRS to match vector layer if needed
            if raster_layer and self.reprojected_raster_layer is None:
                self.transform_raster_CRS(layer, raster_layer)

            # Create map canvas and add to panel
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
        """
        Transform raster layer CRS to match vector layer CRS for proper overlay.
        
        Args:
            layer: Vector layer with target CRS
            raster_layer: Raster layer to transform
        """
        try:
            if not layer or not raster_layer:
                return

            existing_layer = None
            grid_crs = layer.crs()
            raster_crs = raster_layer.crs()
            
            # Log CRS information for debugging
            QgsMessageLog.logMessage(f"Raster Layer Name: {raster_layer.name()}", 'AMRUT', Qgis.Info)
            QgsMessageLog.logMessage(f"Raster Layer Valid: {raster_layer.isValid()}", 'AMRUT', Qgis.Info)
            QgsMessageLog.logMessage(f"Raster Source Path: {raster_layer.source()}", 'AMRUT', Qgis.Info)
            QgsMessageLog.logMessage(f"Raster CRS: {raster_crs.authid()}", 'AMRUT', Qgis.Info)
            QgsMessageLog.logMessage(f"Grid CRS: {grid_crs.authid()}", 'AMRUT', Qgis.Info)
            
            # Check if reprojection is needed
            if raster_crs.authid() == grid_crs.authid():
                self.reprojected_raster_layer = raster_layer
                return

            # Clean up existing temporary raster layers
            if self.reprojected_raster_layer is None:
                self.remove_layer_by_name(f"Temporary_{raster_layer.name()}")
            else:
                # Check for existing reprojected layer
                for lyr in QgsProject.instance().mapLayers().values():
                    if lyr.name() == f"Temporary_{raster_layer.name()}" and isinstance(lyr, QgsRasterLayer):
                        existing_layer = lyr
                        break

            # Use existing reprojected layer if available
            if existing_layer:
                self.reprojected_raster_layer = existing_layer
            else:
                # Validate raster source path
                if not os.path.isfile(raster_layer.source()):
                    QgsMessageLog.logMessage(f"Raster layer '{raster_layer.name()}' is not file-based or lacks a valid source path.", 'AMRUT', Qgis.Warning)
                    self.reprojected_raster_layer = raster_layer  # Use original if can't reproject
                    return

                # Set up processing environment
                processing_context = QgsProcessingContext()
                feedback = QgsProcessingFeedback()

                # Configure reprojection parameters
                reproject_params = {
                    'INPUT': raster_layer.source(),
                    'SOURCE_CRS': raster_crs.authid(),
                    'TARGET_CRS': grid_crs.authid(),
                    'RESAMPLING': 0,        # Nearest neighbor resampling
                    'NODATA': -9999,        # No data value
                    'OUTPUT': 'TEMPORARY_OUTPUT'
                }

                try:
                    # Execute raster reprojection
                    reprojected_result = processing.run("gdal:warpreproject", reproject_params, context=processing_context, feedback=feedback)
                    temp_raster_path = reprojected_result['OUTPUT']
                    
                    # Track temporary file for cleanup
                    self.temporary_files.append(temp_raster_path)

                    # Create reprojected raster layer
                    self.reprojected_raster_layer = QgsRasterLayer(temp_raster_path, f"Temporary_{raster_layer.name()}")

                    # Validate reprojected layer
                    if not self.reprojected_raster_layer.isValid():
                        QgsMessageLog.logMessage("Failed to reproject the raster layer.", 'AMRUT', Qgis.Warning)
                        self.reprojected_raster_layer = raster_layer  # Fallback to original
                        return

                    # Log reprojection success
                    QgsMessageLog.logMessage(
                        f"[Reprojected Raster] CRS: {self.reprojected_raster_layer.crs().authid()}, "
                        f"Extent: {self.reprojected_raster_layer.extent().toString()}",
                        'AMRUT', Qgis.Info
                    )

                    # Add reprojected layer to project
                    QgsProject.instance().addMapLayer(self.reprojected_raster_layer)
                
                except Exception as e:
                    QgsMessageLog.logMessage(f"Error reprojecting raster: {str(e)}", 'AMRUT', Qgis.Warning)
                    self.reprojected_raster_layer = raster_layer  # Fallback to original

        except Exception as e:
            QgsMessageLog.logMessage(f"Error in transform_raster_CRS: {str(e)}", 'AMRUT', Qgis.Critical)
            self.reprojected_raster_layer = raster_layer if raster_layer else None

    def create_map_canvas(self, layer):
        """
        Create and configure a map canvas to render the given layer with optional raster background.
        
        Args:
            layer: Primary vector layer to display
            
        Returns:
            QgsMapCanvas: Configured map canvas or None if failed
        """
        try:
            if not layer or not layer.isValid():
                QgsMessageLog.logMessage(f"[Canvas] Invalid layer provided", 'AMRUT', Qgis.Warning)
                return None

            # Create and configure canvas
            canvas = QgsMapCanvas()
            canvas.setCanvasColor(QColor("white"))

            # CRITICAL: Proper layer ordering with vector on top of raster
            layers_to_add = []
            
            # Add vector layer first (will be rendered on top)
            if layer and layer.isValid():
                layers_to_add.append(layer)
                QgsMessageLog.logMessage(f"[Canvas] Added vector layer: {layer.name()}", 'AMRUT', Qgis.Info)
            
            # Add raster layer second (will be rendered at bottom)
            if self.reprojected_raster_layer and self.reprojected_raster_layer.isValid():
                layers_to_add.append(self.reprojected_raster_layer)
                QgsMessageLog.logMessage(f"[Canvas] Added raster layer: {self.reprojected_raster_layer.name()}", 'AMRUT', Qgis.Info)

            # Validate that we have layers to display
            if not layers_to_add:
                QgsMessageLog.logMessage("[Canvas] No valid layers to add", 'AMRUT', Qgis.Warning)
                return None

            # Set layers with proper rendering order
            canvas.setLayers(layers_to_add)                  

            # Set canvas extent - prioritize layer extent, fallback to grid extent
            if layer and layer.isValid() and not layer.extent().isEmpty():
                canvas.setExtent(layer.extent())
                QgsMessageLog.logMessage(f"[Canvas] Set extent from layer: {layer.extent().toString()}", 'AMRUT', Qgis.Info)
            elif self.grid_extent and not self.grid_extent.isEmpty():
                canvas.setExtent(self.grid_extent)
                QgsMessageLog.logMessage(f"[Canvas] Set extent from grid: {self.grid_extent.toString()}", 'AMRUT', Qgis.Info)
            else:
                QgsMessageLog.logMessage("[Canvas] No valid extent available", 'AMRUT', Qgis.Warning)

            # Set minimum canvas size for usability
            canvas.setMinimumSize(400, 300)
            
            # Force canvas refresh to display content
            canvas.refresh()
            canvas.update()
            
            # Log canvas setup details
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
        """
        Create a panel to display error messages to the user.
        
        Args:
            message (str): Error message to display
            
        Returns:
            QVBoxLayout: Layout containing the error message
        """
        try:
            panel_layout = QVBoxLayout()
            
            # Create styled error label
            error_label = QLabel(message)
            error_label.setAlignment(Qt.AlignCenter)
            error_label.setStyleSheet("color: red; font-weight: bold;")
            panel_layout.addWidget(error_label)
            
            return panel_layout
            
        except Exception as e:
            QgsMessageLog.logMessage(f"Error in create_error_panel: {str(e)}", 'AMRUT', Qgis.Critical)
            return QVBoxLayout()

    def add_vertical_divider(self, layout):
        """
        Add a visual vertical divider line between the two panels.
        
        Args:
            layout: Layout to add the divider to
        """
        try:
            # Create divider line
            line = QLabel()
            line.setFixedWidth(2)
            line.setStyleSheet("background-color: gray;")
            layout.addWidget(line)
            
        except Exception as e:
            QgsMessageLog.logMessage(f"Error in add_vertical_divider: {str(e)}", 'AMRUT', Qgis.Critical)

    def closeEvent(self, event):
        """
        Override closeEvent to perform cleanup when dialog is closed.
        
        This includes:
        - Removing temporary layers from QGIS project
        - Deleting temporary files
        - Refreshing main map canvas
        
        Args:
            event: Close event object
        """
        try:
            # Remove temporary vector layers from project
            self.remove_layer_by_name(f"Temporary_{self.selected_layer_name}")
            
            # Remove temporary raster layer if it exists
            if self.selected_raster_layer_name:
                self.remove_layer_by_name(f"Temporary_{self.selected_raster_layer_name}")

            # Clean up all temporary files created during session
            for temp_file in self.temporary_files:
                if os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                        QgsMessageLog.logMessage(f"Deleted temporary file: {temp_file}", 'AMRUT', Qgis.Info)
                    except Exception as e:
                        QgsMessageLog.logMessage(f"Error deleting temp file {temp_file}: {str(e)}", 'AMRUT', Qgis.Warning)
            
            # Refresh main QGIS map canvas to reflect layer removal
            if hasattr(self, 'iface') and self.iface:
                self.iface.mapCanvas().refresh()

        except Exception as e:
            QgsMessageLog.logMessage(f"Error in closeEvent cleanup: {str(e)}", 'AMRUT', Qgis.Critical)
        finally:
            # Ensure parent closeEvent is called regardless of errors
            super().closeEvent(event)