from PyQt5.QtWidgets import QDialog, QVBoxLayout, QPushButton, QFileDialog, QMessageBox, QLabel, QLineEdit, QHBoxLayout, QComboBox
from PyQt5.QtCore import Qt

from . import open_dialog
import zipfile
import json

from qgis.core import QgsProject

class ImportDialog(QDialog):
    def __init__(self, iface):
        super().__init__()
        self.iface = iface
        self.setWindowTitle("Import Dialog")

    def reconstruct_or_qc_dialog(self):
        # Create a custom dialog for the options
        dialog = QDialog(self)
        dialog.setWindowTitle("Choose Action")
        dialog.setFixedSize(300, 200)

        # Set up layout for the dialog
        layout = QVBoxLayout(dialog)

        # Add the logo layout to the main layout (if needed)
        pluginUsageDialog = open_dialog.OpenPluginDialog(self.iface)
        logo_layout = pluginUsageDialog.createLogoLayout()
        layout.addLayout(logo_layout)

        # Create the buttons for Reconstruct Layer and Quality Check
        reconstruct_button = QPushButton("Reconstruct Layer", dialog)
        quality_check_button = QPushButton("Quality Check", dialog)

        # Set button size
        reconstruct_button.setFixedSize(200, 25)
        quality_check_button.setFixedSize(200, 25)

        # Add buttons to the layout and center them
        layout.addWidget(reconstruct_button, alignment=Qt.AlignCenter)
        layout.addWidget(quality_check_button, alignment=Qt.AlignCenter)

        # Connect button clicks to appropriate functions
        reconstruct_button.clicked.connect(lambda: self.reconstruct_dialog(dialog))
        quality_check_button.clicked.connect(lambda: self.quality_check_dialog(dialog))

        # Show the dialog
        dialog.exec_()


    def reconstruct_dialog(self, dialog):
        # Close the current dialog (reconstruct_or_qc_dialog)
        dialog.accept()  # This closes the current dialog


    def quality_check_dialog(self, dialog):
        # Close the current dialog
        dialog.accept()

        # Create a new dialog for the Quality Check
        qc_dialog = QDialog(self)
        qc_dialog.setWindowTitle("Quality Check")
        qc_dialog.setFixedSize(500, 200)

        # Set up layout for the dialog
        layout = QVBoxLayout(qc_dialog)

        # File input field and Browse button
        file_layout = QHBoxLayout()
        self.file_input = QLineEdit(qc_dialog)
        self.file_input.setPlaceholderText("Select a .amrut file...")
        file_layout.addWidget(self.file_input)

        browse_button = QPushButton("Browse", qc_dialog)
        file_layout.addWidget(browse_button)
        browse_button.clicked.connect(self.browse_file)
        layout.addLayout(file_layout)

        # Dropdown to select a single layer
        layer_selection_layout = QHBoxLayout()
        self.layer_dropdown = QComboBox(qc_dialog)
        self.layer_dropdown.setPlaceholderText("Select layer to check")
        self.layer_dropdown.setEnabled(False)  # Initially disabled
        layer_selection_layout.addWidget(QLabel("Select layer to check:", qc_dialog))
        layer_selection_layout.addWidget(self.layer_dropdown)
        layout.addLayout(layer_selection_layout)

        # Show the Quality Check dialog
        qc_dialog.exec_()

    def browse_file(self):
        # Open file dialog to select a file
        file, _ = QFileDialog.getOpenFileName(self, "Select a File", "", "AMRUT Files (*.amrut);;All Files (*)")

        if file:
            if file.endswith(".amrut"):
                # Validate the .amrut file
                self.validate_amrut_file(file)
            else:
                QMessageBox.warning(self, "Invalid File", "Please select a valid .amrut file.")
                self.file_input.clear()

    def validate_amrut_file(self, file_path):
        """Validate the .amrut file, including metadata and GeoJSON files."""
        try:
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                # Check if metadata.json exists
                if 'metadata.json' not in zip_ref.namelist():
                    QMessageBox.warning(self, "Invalid File", "The file does not contain 'metadata.json'.")
                    self.file_input.clear()
                    return

                # Load metadata.json
                metadata = json.loads(zip_ref.read('metadata.json'))

                # Check if layers array exists in metadata
                if 'layers' not in metadata or not isinstance(metadata['layers'], list):
                    QMessageBox.warning(self, "Invalid Metadata", "'layers' array is missing or invalid in metadata.json.")
                    self.file_input.clear()
                    return

                # Validate GeoJSON files in the .amrut archive
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
                    return

                # Validate GeoJSON files in the QGIS project
                project_layers = [layer.name() for layer in QgsProject.instance().mapLayers().values()]
                missing_in_project = [
                    layer for layer in metadata['layers']
                    if layer not in project_layers
                ]
                if missing_in_project:
                    QMessageBox.warning(
                        self,
                        "Missing Layers in QGIS",
                        f"The following layers are missing in the QGIS project: {', '.join(missing_in_project)}"
                    )
                    self.file_input.clear()
                    return

                # If all validations pass, populate the dropdown
                self.file_input.setText(file_path)
                self.populate_layer_dropdown(metadata['layers'])
                QMessageBox.information(self, "Validation Successful", "All checks passed successfully!")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occurred: {str(e)}")
            self.file_input.clear()

    def populate_layer_dropdown(self, layers):
        """Populate the dropdown with layers from the metadata."""
        self.layer_dropdown.clear()
        self.layer_dropdown.addItems(layers)
        self.layer_dropdown.setEnabled(True)
        