from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QPushButton, QFileDialog, QMessageBox, QLabel, QLineEdit, QHBoxLayout, QComboBox
)
from PyQt5.QtCore import Qt

from . import export_ui as ui
import zipfile
import json
from qgis.core import QgsProject, QgsMapLayer

class ImportDialog(QDialog):
    def __init__(self, iface):
        super().__init__()
        self.iface = iface
        self.setWindowTitle("Import Dialog")
        metadata_bounds = {}

    def reconstruct_or_qc_dialog(self):
        dialog = self._create_dialog("AMRUT 2.0", 350, 200)
        layout = QVBoxLayout(dialog)

        logo_layout = ui.createLogoLayout("Sankalan 2.0")
        layout.addLayout(logo_layout)

        self._add_centered_button(layout, "Reconstruct Layer", lambda: self._open_dialog(dialog, self.reconstruct_dialog))
        self._add_centered_button(layout, "Quality Check", lambda: self._open_dialog(dialog, self.quality_check_dialog))

        dialog.exec_()

    def _create_dialog(self, title, width, height):
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.setFixedSize(width, height)
        return dialog

    def _add_centered_button(self, layout, text, callback):
        button = QPushButton(text)
        button.setFixedSize(200, 25)
        button.clicked.connect(callback)
        layout.addWidget(button, alignment=Qt.AlignCenter)

    def _open_dialog(self, current_dialog, next_dialog):
        current_dialog.accept()
        next_dialog()

    def quality_check_dialog(self):
        qc_dialog = self._create_dialog("AMRUT 2.0", 500, 250)
        layout = QVBoxLayout(qc_dialog)
        logo_layout = ui.createLogoLayout("")
        layout.addLayout(logo_layout)
        layout.addSpacing(10) 
        self.file_input = self._add_file_input(layout)

        self.layer_dropdown = QComboBox(qc_dialog)
        self.raster_layer_dropdown = QComboBox(qc_dialog)
        layout.addSpacing(15) 
        self._add_dropdown_with_placeholder(layout, "Select a Raster layer: (Optional)", self.raster_layer_dropdown, "Select a Raster Layer", populate=False)
        layout.addSpacing(15) 
        self._add_dropdown_with_placeholder(layout, "Select layer to check:", self.layer_dropdown, "Select any layer for Quality Check")
        layout.addSpacing(20) 
        raster_layers = [
            layer.name() for layer in QgsProject.instance().mapLayers().values()
            if layer.type() == QgsMapLayer.RasterLayer
        ]
        self.raster_layer_dropdown.addItems(raster_layers)

        proceed_button = QPushButton("Proceed Quality Check")
        proceed_button.setFixedSize(150, 25)
        proceed_button.clicked.connect(self.proceed_quality_check)
        layout.addWidget(proceed_button, alignment=Qt.AlignCenter)

        qc_dialog.exec_()

    def _add_file_input(self, layout):
        file_layout = QHBoxLayout()
        file_input = QLineEdit()
        file_input.setPlaceholderText("Select a .amrut file...")
        file_layout.addWidget(file_input)

        browse_button = QPushButton("Browse")
        browse_button.clicked.connect(self.browse_file)
        file_layout.addWidget(browse_button)

        layout.addLayout(file_layout)
        return file_input

    def _add_dropdown_with_placeholder(self, layout, label_text, dropdown, placeholder, populate=True):
        dropdown_layout = QHBoxLayout()  # Use a horizontal layout for label and dropdown
        label = QLabel(label_text)
        dropdown_layout.addWidget(label)
        
        dropdown.addItem(placeholder)
        dropdown.model().item(0).setEnabled(False)
        if populate:
            dropdown.addItems([])  
        
        dropdown_layout.addWidget(dropdown)
        layout.addLayout(dropdown_layout)  

    def browse_file(self):
        file, _ = QFileDialog.getOpenFileName(self, "Select a File", "", "AMRUT Files (*.amrut);;All Files (*)")

        if file:
            if file.endswith(".amrut"):
                self.validate_amrut_file(file)
            else:
                QMessageBox.warning(self, "Invalid File", "Please select a valid .amrut file.")
                self.file_input.clear()

    def validate_amrut_file(self, file_path):
        try:
            self.layer_dropdown.clear()
            self.layer_dropdown.addItem("Select any layer for Quality Check")  # Add default text
            self.layer_dropdown.model().item(0).setEnabled(False)

            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                if not self._validate_metadata(zip_ref):
                    return

                metadata = json.loads(zip_ref.read('metadata.json'))
                if not self._validate_geojson_files(zip_ref, metadata):
                    return
                
                project_layers = [layer.name() for layer in QgsProject.instance().mapLayers().values()]
                missing_in_project = [
                    layer for layer in metadata['layers']
                    if layer not in project_layers
                ]
                if missing_in_project:
                    QMessageBox.warning(self,"Missing Layers in QGIS",f"The following layers are missing in the QGIS project: {', '.join(missing_in_project)}")
                    self.file_input.clear()
                    return
                
                if 'layers_qc_completed' not in metadata:
                    metadata['layers_qc_completed'] = []

                layers_qc_completed = metadata['layers_qc_completed']
                layers_qc_pending = [
                    layer for layer in metadata['layers']
                    if layer not in layers_qc_completed
                ]

                self.metadata_bounds = {key: metadata[key] for key in ["north", "south", "east", "west"]}
                self.file_input.setText(file_path)
                self.layer_dropdown.addItems(layers_qc_pending)
                # QMessageBox.information(self, "Validation Successful", "All checks passed successfully!")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occurred: {str(e)}")
            self.file_input.clear()

    def _validate_metadata(self, zip_ref):
        if 'metadata.json' not in zip_ref.namelist():
            QMessageBox.warning(self, "Invalid File", "The file does not contain 'metadata.json'.")
            self.file_input.clear()
            return False
        return True

    def _validate_geojson_files(self, zip_ref, metadata):
        if 'layers' not in metadata or not isinstance(metadata['layers'], list):
            QMessageBox.warning(self, "Invalid Metadata", "'layers' array is missing or invalid in metadata.json.")
            self.file_input.clear()
            return False

        missing_files = [
            layer for layer in metadata['layers']
            if f"{layer}.geojson" not in zip_ref.namelist()
        ]
        if missing_files:
            QMessageBox.warning(
                self,
                "Missing GeoJSON Files",
                f"The following GeoJSON files are missing in the .amrut file: {', '.join(missing_files)}"
            )
            self.file_input.clear()
            return False

        return True
    
    def proceed_quality_check(self):
        selected_layer = self.layer_dropdown.currentText()
        if selected_layer == "Select any layer for Quality Check" or not selected_layer:
            QMessageBox.warning(self, "No Layer Selected", "Please select a valid layer for quality check.")
            return
        else:
            selected_raster_layer = self.raster_layer_dropdown.currentText()
            if selected_raster_layer != "Select a Raster Layer":
                raster_layer = next(
                    (layer for layer in QgsProject.instance().mapLayers().values()
                    if layer.name() == selected_raster_layer and layer.type() == QgsMapLayer.RasterLayer),
                    None
                )
                extent = raster_layer.extent()
                raster_bounds = {"north": extent.yMaximum(), "south": extent.yMinimum(),
                                "east": extent.xMaximum(), "west": extent.xMinimum()}
                if not all(raster_bounds[key] >= self.metadata_bounds[key] for key in ["north", "east"]) or \
                not all(raster_bounds[key] <= self.metadata_bounds[key] for key in ["south", "west"]):
                    QMessageBox.warning(self, "Extent Validation Failed",
                                        "The selected raster layer's extent does not cover the metadata extent.")
                    return
                # else:
                #     QMessageBox.information(self, "Proceeding", f"Proceeding with Quality Check for layer: {selected_layer}")
