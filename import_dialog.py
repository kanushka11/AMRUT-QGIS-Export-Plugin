from PyQt5.QtWidgets import QDialog, QVBoxLayout, QPushButton, QFileDialog, QMessageBox, QLabel, QLineEdit
from PyQt5.QtCore import Qt

from . import open_dialog
import zipfile

class ImportDialog(QDialog):
    def __init__(self, iface):
        super().__init__()
        self.iface = iface
        self.setWindowTitle("Import Dialog")

    def reconstruct_or_qc_dialog(self):
        # Create a custom dialog for the options
        dialog = QDialog(self)
        dialog.setWindowTitle("Choose Action")
        dialog.setFixedSize(300, 200)  # Set the dialog size to make it larger

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
        reconstruct_button.setFixedSize(200, 25)  # Make buttons larger
        quality_check_button.setFixedSize(200, 25)  # Make buttons larger

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
        # Create a new dialog for the quality check
        qc_dialog = QDialog(self)
        qc_dialog.setWindowTitle("Quality Check")

        # Set up layout for the dialog
        layout = QVBoxLayout(qc_dialog)

        # Input box to select the file with .amrut extension
        self.file_input = QLineEdit(qc_dialog)
        self.file_input.setPlaceholderText("Select a .amrut file...")
        layout.addWidget(self.file_input)

        # Button to browse for a file
        browse_button = QPushButton("Browse", qc_dialog)
        layout.addWidget(browse_button)
        browse_button.clicked.connect(self.browse_file)

        # Proceed and cancel buttons
        proceed_button = QPushButton("Proceed", qc_dialog)
        cancel_button = QPushButton("Cancel", qc_dialog)

        layout.addWidget(proceed_button)
        layout.addWidget(cancel_button)

        # Connect the buttons to their respective actions
        proceed_button.clicked.connect(self.proceed_with_quality_check)
        cancel_button.clicked.connect(qc_dialog.reject)

        # Execute the quality check dialog
        qc_dialog.exec_()


    def browse_file(self):
        # Open file dialog to select a file
        file, _ = QFileDialog.getOpenFileName(self, "Select a File", "", "AMRUT Files (*.amrut);;All Files (*)")
        
        if file:  # If a file was selected
            if file.endswith(".amrut"):
                # Check if it's a ZIP file and contains metadata.json
                if self.is_valid_amrut_file(file):
                    self.file_input.setText(file)  # Set the file path in the input box
                else:
                    QMessageBox.warning(self, "Invalid File", "The .amrut file must contain a 'metadata.json' file inside the ZIP.")
                    self.file_input.clear()  # Clear the input box to prompt for valid file again
            else:
                # Show an error message if the file is not .amrut
                QMessageBox.warning(self, "Invalid File", "Please select a valid .amrut file.")
                self.file_input.clear()  # Clear the input box to prompt for valid file again

    def is_valid_amrut_file(self, file_path):
        """Check if the selected .amrut file is a ZIP file and contains metadata.json."""
        try:
            # Check if it's a zip file and contains metadata.json
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                if 'metadata.json' in zip_ref.namelist():
                    return True
                else:
                    return False
        except zipfile.BadZipFile:
            # Handle the case where the file is not a valid ZIP file
            QMessageBox.warning(self, "Invalid ZIP", "The selected file is not a valid ZIP file.")
            return False

    def proceed_with_quality_check(self):
        # Logic for proceeding with quality check
        file_path = self.file_input.text()

        if not file_path:
            QMessageBox.warning(self, "No File Selected", "Please select a valid .amrut file to proceed.")
            return

        # Proceed with the quality check using the selected file
        print(f"Proceeding with quality check on file: {file_path}")
        # Further logic for quality check can go here...
            