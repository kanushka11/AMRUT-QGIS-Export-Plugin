from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QPushButton, QFileDialog, QMessageBox, QLabel, QLineEdit, QHBoxLayout, QComboBox
)
from PyQt5.QtCore import Qt
import tempfile
import os
import shutil
import zipfile
import json
from qgis.core import (
    QgsProject, QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsRectangle, QgsMapLayer, QgsMessageLog, Qgis
)
from . import export_ui as ui
from . import qc_visualization_dialog as qc
from . import import_reconstruct_dialog as reconstruct_dialog


class ImportDialog(QDialog):
    """
    Main dialog class for importing and processing AMRUT files.
    Provides functionality for quality checking and layer reconstruction.
    """
    
    def __init__(self, iface):
        """
        Initialize the ImportDialog.
        
        Args:
            iface: QGIS interface object for plugin integration
        """
        super().__init__()
        self.iface = iface

    def reconstruct_or_qc_dialog(self):
        """
        Main dialog to choose between reconstructing a layer or performing a quality check.
        This is the entry point dialog that presents two main options to the user.
        """
        # Create the main dialog window
        dialog = self.create_dialog("AMRUT 2.0", 500, 250)
        layout = QVBoxLayout(dialog)

        # Add logo layout at the top of the dialog
        logo_layout = ui.createLogoLayout("SANKALAN 2.0", "Data From Mobile")
        layout.addLayout(logo_layout)

        # Add centered buttons for main functionality
        self.add_centered_button(
            layout, 
            "Quality Check", 
            lambda: self._open_dialog(dialog, self.quality_check_dialog)
        )
        self.add_centered_button(
            layout, 
            "Reconstruct Layer", 
            lambda: self._open_dialog(dialog, self.reconstruct_dialog)
        )
        
        # Add footer note at the bottom
        footer_note = ui.get_footer_note()
        layout.addWidget(footer_note, alignment=Qt.AlignCenter)

        # Show the dialog and wait for user interaction
        dialog.exec_()

    def create_dialog(self, title, width, height):
        """
        Helper function to create a generic dialog window with specified dimensions.
        
        Args:
            title (str): Window title
            width (int): Dialog width in pixels
            height (int): Dialog height in pixels
            
        Returns:
            QDialog: Configured dialog window
        """
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.setFixedSize(width, height)
        return dialog

    def add_centered_button(self, layout, text, callback):
        """
        Helper function to add a centered button to a layout.
        
        Args:
            layout: Layout to add the button to
            text (str): Button text
            callback: Function to call when button is clicked
        """
        button = QPushButton(text)
        button.setFixedSize(200, 25)
        button.clicked.connect(callback)
        layout.addWidget(button, alignment=Qt.AlignCenter)

    def _open_dialog(self, current_dialog, next_dialog):
        """
        Close the current dialog and open the next one.
        Handles dialog transitions with error handling.
        
        Args:
            current_dialog: Dialog to close
            next_dialog: Function that opens the next dialog
        """
        current_dialog.accept()
        try:
            next_dialog()
        except Exception as e:
            QgsMessageLog.logMessage(f"Error opening dialog: {str(e)}", 'AMRUT', Qgis.Critical)

    def reconstruct_dialog(self):
        """
        Opens the layer reconstruction dialog.
        This allows users to reconstruct layers from AMRUT files.
        """
        self.reconstructDialog = reconstruct_dialog.ReconstructLayerTabDialog(self.iface)
        self.reconstructDialog.exec_()

    def quality_check_dialog(self):
        """
        Quality check dialog for layer selection and validation.
        This is the main quality control interface where users can:
        - Select AMRUT files
        - Choose layers for quality checking
        - Optionally select raster layers for extent validation
        """
        try:
            # Create the quality check dialog window
            qc_dialog = self.create_dialog("AMRUT 2.0", 500, 350)
            layout = QVBoxLayout(qc_dialog)

            # Add logo layout at the top
            logo_layout = ui.createLogoLayout("Quality Check")
            layout.addLayout(logo_layout)
            layout.addSpacing(10)

            # Add file input field for .amrut file selection
            self.file_input = self._add_file_input(layout)

            # Initialize dropdown menus for layer selection
            self.layer_dropdown = QComboBox(qc_dialog)
            self.raster_layer_dropdown = QComboBox(qc_dialog)

            # Add spacing and dropdown for optional raster layer selection
            layout.addSpacing(15)
            self._add_dropdown_with_placeholder(
                layout,
                "Select a Raster layer: (Optional)",
                self.raster_layer_dropdown,
                "Select a Raster Layer",
                populate=False
            )
            
            # Add spacing and dropdown for required layer selection
            layout.addSpacing(15)
            self._add_dropdown_with_placeholder(
                layout,
                "Select layer to check:",
                self.layer_dropdown,
                "Select any layer for Quality Check"
            )
            layout.addSpacing(20)

            # Populate raster layers dropdown with available raster layers from QGIS project
            raster_layers = [
                layer.name() for layer in QgsProject.instance().mapLayers().values()
                if layer.type() == QgsMapLayer.RasterLayer
            ]
            self.raster_layer_dropdown.addItems(raster_layers)

            # Add proceed button to start quality check process
            proceed_button = QPushButton("Proceed Quality Check")
            proceed_button.setFixedSize(150, 25)
            proceed_button.clicked.connect(self.proceed_quality_check)
            layout.addWidget(proceed_button, alignment=Qt.AlignCenter)

            # Show the dialog
            qc_dialog.exec_()
            
        except Exception as e:
            QgsMessageLog.logMessage(f"Error in quality_check_dialog: {str(e)}", 'AMRUT', Qgis.Critical)

    def _add_file_input(self, layout):
        """
        Add file input layout with a browse button.
        Creates a horizontal layout with a text field and browse button for file selection.
        
        Args:
            layout: Parent layout to add the file input to
            
        Returns:
            QLineEdit: The file input text field
        """
        file_layout = QHBoxLayout()
        
        # Create text input field for file path display
        file_input = QLineEdit()
        file_input.setPlaceholderText("Select a .amrut file...")
        file_layout.addWidget(file_input)

        # Create browse button to open file dialog
        browse_button = QPushButton("Browse")
        browse_button.clicked.connect(self.browse_file)
        file_layout.addWidget(browse_button)

        layout.addLayout(file_layout)
        return file_input

    def _add_dropdown_with_placeholder(self, layout, label_text, dropdown, placeholder, populate=True):
        """
        Add a dropdown with a label and placeholder text.
        
        Args:
            layout: Parent layout to add the dropdown to
            label_text (str): Label text to display
            dropdown: QComboBox widget to configure
            placeholder (str): Placeholder text for the dropdown
            populate (bool): Whether to populate the dropdown with items
        """
        # Create horizontal layout for label and dropdown
        dropdown_layout = QHBoxLayout()
        label = QLabel(label_text)
        dropdown_layout.addWidget(label)

        # Add placeholder item to dropdown
        dropdown.addItem(placeholder)
        
        # Populate dropdown with additional items if requested
        if populate:
            dropdown.addItems([])  # Placeholder for future population

        dropdown_layout.addWidget(dropdown)
        layout.addLayout(dropdown_layout)

    def browse_file(self):
        """
        Open file dialog to select an .amrut file.
        Validates that the selected file has the correct extension.
        """
        try:
            # Open file dialog filtered for .amrut files
            file, _ = QFileDialog.getOpenFileName(
                self, 
                "Select a File", 
                "", 
                "AMRUT Files (*.amrut);;All Files (*)"
            )

            if file:
                # Validate file extension
                if file.endswith(".amrut"):
                    self.selected_file = file
                    self.validate_amrut_file(file)
                else:
                    QMessageBox.warning(self, "Invalid File", "Please select a valid .amrut file.")
                    self.file_input.clear()
                    
        except Exception as e:
            QgsMessageLog.logMessage(f"Error in browse_file: {str(e)}", 'AMRUT', Qgis.Critical)

    def validate_amrut_file(self, file_path):
        """
        Validate the selected .amrut file and populate layer dropdown.
        
        This method performs comprehensive validation of the AMRUT file:
        - Checks file existence (including resurvey versions)
        - Validates ZIP structure and metadata
        - Checks QC status and completion
        - Populates layer dropdown with pending QC layers
        - Updates metadata with QC progress
        
        Args:
            file_path (str): Path to the .amrut file to validate
        """
        try:
            # Clear and reset layer dropdown
            self.layer_dropdown.clear()
            self.layer_dropdown.addItem("Select any layer for Quality Check")  
            self.layer_dropdown.model().item(0).setEnabled(False)

            # Check if file exists, otherwise try with resurvey_required_ prefix
            if not os.path.exists(file_path):
                directory = os.path.dirname(file_path)
                filename = os.path.basename(file_path)
                prefixed_path = os.path.join(directory, f"resurvey_required_{filename}")
                
                if os.path.exists(prefixed_path):
                    file_path = prefixed_path  # Use the prefixed file instead
                else:
                    QMessageBox.critical(self, "File Not Found", 
                                       "The selected .amrut file or its resurvey version could not be found.")
                    return

            # Create temporary directory for file extraction
            temp_dir = tempfile.mkdtemp()

            # Extract and validate ZIP file structure
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                # Check for required metadata file
                if 'metadata.json' not in zip_ref.namelist():
                    QMessageBox.warning(self, "Missing Metadata File", 
                                      "The .amrut file does not contain 'metadata.json'.")
                    self.file_input.clear()
                    return
                
                # Extract all files to temporary directory
                zip_ref.extractall(temp_dir)
                metadata_path = os.path.join(temp_dir, "metadata.json")

                # Parse metadata JSON file
                try:
                    with open(metadata_path, "r", encoding="utf-8") as f:
                        metadata = json.load(f)
                except (json.JSONDecodeError, FileNotFoundError):
                    QMessageBox.critical(self, "Invalid Metadata", "Failed to parse metadata.json.")
                    self.file_input.clear()
                    return

                # Check if file is already fully verified
                if metadata.get("qc_status") == "verified":
                    QMessageBox.information(self, "File Verified", 
                                          "All layers of this file have been verified.")
                    self.file_input.clear()
                    return
                
                # Check if file is already marked for resurvey
                if ("resurvey" in metadata and len(metadata["resurvey"]) > 0 and 
                    "layers_qc_completed" not in metadata and "qc_status" not in metadata):
                    QMessageBox.information(self, "Marked for Re-Survey", 
                                          "File has already been marked for Re-Survey.")
                    self.file_input.clear()
                    return

                # Validate layers array in metadata
                if 'layers' not in metadata or not isinstance(metadata['layers'], list):
                    QMessageBox.warning(self, "Invalid Metadata", 
                                      "'layers' array is missing or invalid in metadata.json.")
                    self.file_input.clear()
                    return

                # Extract layer names from metadata
                layer_names = [layer.split(" : ")[0].strip("{}").strip() for layer in metadata['layers']]
                
                # Validate layers against current QGIS project
                project_layers = [layer.name().strip().lower() for layer in QgsProject.instance().mapLayers().values()]
                missing_in_project = [layer for layer in layer_names if layer.lower() not in project_layers]

                if missing_in_project:
                    QMessageBox.warning(self, "Missing Layers in QGIS", 
                                      f"The following layers are missing in the project: {', '.join(missing_in_project)}")
                    self.file_input.clear()
                    return

                # Initialize QC completion tracking if not present
                if 'layers_qc_completed' not in metadata:
                    # Mark layers as completed if they don't have corresponding GeoJSON files
                    metadata['layers_qc_completed'] = [
                        layer for layer in layer_names if f"{layer}.geojson" not in zip_ref.namelist()
                    ]
                    # Mark entire file as verified if all layers are completed
                    if set(metadata['layers_qc_completed']) == set(layer_names):
                        metadata["qc_status"] = "verified"

                # Identify layers still pending QC
                layers_qc_pending = [layer for layer in layer_names if layer not in metadata['layers_qc_completed']]

                # Update metadata.json with QC progress
                with open(metadata_path, "w", encoding="utf-8") as metadata_file:
                    json.dump(metadata, metadata_file, indent=4)

            # Create updated .amrut file with modified metadata
            temp_amrut_path = file_path + ".tmp"
            with zipfile.ZipFile(temp_amrut_path, 'w') as new_zip:
                for root, _, files in os.walk(temp_dir):
                    for file in files:
                        temp_file_path = os.path.join(root, file)
                        arcname = os.path.relpath(temp_file_path, temp_dir)
                        new_zip.write(temp_file_path, arcname)

            # Replace original file with updated version
            os.replace(temp_amrut_path, file_path)

            # Extract geographic bounds from metadata for extent validation
            self.metadata_bounds = {key: metadata[key] for key in ["north", "south", "east", "west"] if key in metadata}

            # Update UI with validation results
            self.file_input.setText(file_path)
            if layers_qc_pending:
                self.layer_dropdown.addItems(layers_qc_pending)
            else:
                QMessageBox.information(self, "All Layers Verified", 
                                      "All layers of this file have been verified.")
                self.file_input.clear()
                
        except Exception as e:
            QgsMessageLog.logMessage(f"Error in validate_amrut_file: {str(e)}", 'AMRUT', Qgis.Critical)
            QMessageBox.critical(self, "Error", f"An unexpected error occurred: {str(e)}")

        finally:
            # Clean up temporary directory
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)

    def proceed_quality_check(self):
        """
        Proceed with the quality check process for the selected layer.
        
        This method:
        - Validates layer selection
        - Creates grid extent from metadata bounds
        - Performs optional raster extent validation
        - Opens the Quality Check Visualization Dialog
        - Refreshes the file validation after QC completion
        """
        try:
            selected_layer_name = self.layer_dropdown.currentText()

            # Validate that a proper layer is selected
            if selected_layer_name == "Select any layer for Quality Check" or not selected_layer_name:
                QMessageBox.warning(self, "No Layer Selected", 
                                  "Please select a valid layer for quality check.")
                return

            # Create geographic extent rectangle from metadata bounds
            grid_extent = QgsRectangle(
                self.metadata_bounds['west'],
                self.metadata_bounds['south'],
                self.metadata_bounds['east'],
                self.metadata_bounds['north']
            )

            # Handle optional raster layer selection for extent validation
            selected_raster_layer_name = self.raster_layer_dropdown.currentText()
            if selected_raster_layer_name != "Select a Raster Layer":
                # Find the selected raster layer in the QGIS project
                raster_layer = next(
                    (layer for layer in QgsProject.instance().mapLayers().values()
                     if layer.name() == selected_raster_layer_name and layer.type() == QgsMapLayer.RasterLayer),
                    None
                )

                if not raster_layer:
                    QMessageBox.warning(self, "Raster Layer Not Found", 
                                      "The selected raster layer could not be found.")
                    return

                # Transform raster extent to WGS84 for comparison with grid extent
                extent = raster_layer.extent()
                raster_crs = raster_layer.crs()
                wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")
                coord_transform = QgsCoordinateTransform(raster_crs, wgs84, QgsProject.instance())

                # Transform the raster extent to match grid extent CRS
                transformed_raster_extent = coord_transform.transformBoundingBox(extent)

                # Validate that grid extent falls within raster extent
                if not transformed_raster_extent.contains(grid_extent):
                    QMessageBox.warning(self, "Extent Validation Failed", 
                                      "The grid's extent does not fall within the raster layer's extent.")
                    return
            else:
                selected_raster_layer_name = None

            # Open the Quality Check Visualization Dialog with all necessary parameters
            qualityCheckVisualizationDialog = qc.QualityCheckVisualizationDialog(
                self,
                selected_layer_name=selected_layer_name,
                amrut_file_path=self.file_input.text(),
                selected_raster_layer_name=selected_raster_layer_name,
                grid_extent=grid_extent
            )

            # Execute the quality check dialog
            qualityCheckVisualizationDialog.exec_()

            # Refresh file validation after quality check completion
            self.validate_amrut_file(self.selected_file)

        except Exception as e:
            QgsMessageLog.logMessage(f"Error in proceed_quality_check: {str(e)}", 'AMRUT', Qgis.Critical)