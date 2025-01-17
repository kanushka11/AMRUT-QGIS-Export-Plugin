import os
from PyQt5.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QMessageBox
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QPixmap

class OpenPluginDialog(QDialog):
    def __init__(self, iface):
        super().__init__()
        self.iface = iface
        self.setWindowTitle("AMRUT 2.0")
        self.setMinimumSize(400, 200)

        layout = QVBoxLayout(self)

        # Create the logo layout (which now includes the label)
        logo_layout = self.createLogoLayout()

        # Add the logo layout to the main layout
        layout.addLayout(logo_layout)

        # Create the Export button
        self.export_button = QPushButton("Data to Mobile", self)
        self.export_button.setFixedWidth(200)  # Set fixed width for consistency
        self.export_button.clicked.connect(self.on_export)

        # Create the Import button
        # self.import_button = QPushButton("Data from Mobile", self)
        # self.import_button.setFixedWidth(200)  # Set fixed width for consistency
        # self.import_button.clicked.connect(self.on_import)

        # Add buttons to the layout and center them
        # Import button Disabled it is still work in progress.
        layout.addWidget(self.export_button, alignment=Qt.AlignCenter)
        #layout.addWidget(self.import_button, alignment=Qt.AlignCenter)

        # Variable to store the action chosen by the user
        self.selected_action = None

    def createLogoLayout(self):
        # Get the current script path and assets directory
        pwd = os.path.dirname(os.path.abspath(__file__))
        assets_dir = os.path.join(pwd, "assets")
        logo1_name = 'iirs.png'
        logo2_name = 'amrut.png'
        logo_size = (50, 50)
        label_text = "Sankalan 2.0"

        logo1_path = os.path.join(assets_dir, logo1_name)
        logo2_path = os.path.join(assets_dir, logo2_name)

        # Debugging: Check paths
        print(f"Logo 1 Path: {logo1_path}")
        print(f"Logo 2 Path: {logo2_path}")

        # Check if files exist
        if not os.path.exists(logo1_path) or not os.path.exists(logo2_path):
            QMessageBox.critical(None, "Error", f"Logos not found!\n{logo1_path}\n{logo2_path}")
            return QHBoxLayout()

        logo_layout = QHBoxLayout()

        logo1_label = QLabel()
        logo2_label = QLabel()
        text_label = QLabel(label_text)

        # Load logos
        logo1_pixmap = QPixmap(logo1_path).scaled(logo_size[0], logo_size[1], Qt.KeepAspectRatio, Qt.SmoothTransformation)
        logo2_pixmap = QPixmap(logo2_path).scaled(logo_size[0], logo_size[1], Qt.KeepAspectRatio, Qt.SmoothTransformation)

        # Debugging: Check pixmap validity
        if logo1_pixmap.isNull():
            logo1_label.setText("Logo 1 Missing")
        else:
            logo1_label.setPixmap(logo1_pixmap)

        if logo2_pixmap.isNull():
            logo2_label.setText("Logo 2 Missing")
        else:
            logo2_label.setPixmap(logo2_pixmap)
        
        # Set font style for the label text
        font = QFont()
        font.setBold(True)  # Removed the underline from the font
        font.setPointSize(18)  # Increased font size for better visibility
        text_label.setFont(font)
        text_label.setContentsMargins(10, 10, 10, 10)
        
        # Align labels properly
        text_label.setAlignment(Qt.AlignCenter)
        logo1_label.setAlignment(Qt.AlignCenter)
        logo2_label.setAlignment(Qt.AlignCenter)

        # Add the widgets to the layout with stretches for positioning
        logo_layout.addWidget(logo1_label)
        logo_layout.addStretch()
        logo_layout.addWidget(text_label)
        logo_layout.addStretch()
        logo_layout.addWidget(logo2_label)

        return logo_layout

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
