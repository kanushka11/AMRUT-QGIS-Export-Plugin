import os
from PyQt5.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QMessageBox
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QPixmap
from . import export_ui as ui

class OpenPluginDialog(QDialog):
    def __init__(self, iface):
        super().__init__()
        self.iface = iface
        self.setWindowTitle("AMRUT 2.0")
        self.setMinimumSize(500, 250)

        layout = QVBoxLayout(self)

        # Create the logo layout (which now includes the label)
        logo_layout = ui.createLogoLayout("SANKALAN 2.0", "Mobile Import-Export Plugin")

        # Add the logo layout to the main layout
        layout.addLayout(logo_layout)

        # Create the Export button
        self.export_button = QPushButton("Data to Mobile", self)
        self.export_button.setFixedSize(200, 25)  # Set fixed width for consistency
        self.export_button.clicked.connect(self.on_export)

        # Create the Import button
        self.import_button = QPushButton("Data from Mobile", self)
        self.import_button.setFixedSize(200, 25)  # Set fixed width for consistency
        self.import_button.clicked.connect(self.on_import)

        #Footer Note
        footer_label = ui.get_footer_note()

        # Add buttons to the layout and center them
        layout.addWidget(self.export_button, alignment=Qt.AlignCenter)
        layout.addWidget(self.import_button, alignment=Qt.AlignCenter)
        layout.addWidget(footer_label, alignment=Qt.AlignCenter)

        # Variable to store the action chosen by the user
        self.selected_action = None

    def on_export(self):
        # Set selected action and accept the dialog
        self.selected_action = 'export'
        self.done(QDialog.Accepted)

    def on_import(self):
        # Set selected action and accept the dialog
        self.selected_action = 'import'
        self.done(QDialog.Accepted) 

    def get_action(self):
        """ Return the action chosen by the user. """
        return self.selected_action
