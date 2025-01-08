from PyQt5.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout, QMessageBox
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

class OpenPluginDialog(QDialog):
    def __init__(self, iface):
        super().__init__()
        self.iface = iface
        self.setWindowTitle("AMRUT 2.0 Export Data")
        self.setMinimumSize(400, 200)

        layout = QVBoxLayout(self)

        # Add label and buttons for the dialog
        label = QLabel("Welcome to AMRUT 2.0 Export Data", self)

        # Center align the welcome message and increase font size
        label.setAlignment(Qt.AlignCenter)
        font = QFont()
        font.setPointSize(12)  # Increase the font size
        label.setFont(font)
        
        layout.addWidget(label)

        # Create the button, reduce width, and center it
        self.yes_button = QPushButton("Open Plugin", self)
        self.yes_button.setFixedWidth(200)  # Reduce the width of the button
        self.yes_button.clicked.connect(self.on_yes)

        # Add the button to the layout and center it
        layout.addWidget(self.yes_button, alignment=Qt.AlignCenter)

    def on_yes(self):
        # If user clicks Yes, open the main dialog
        self.accept()  # This will close the PluginUsageDialog and trigger the next steps in the `run` method
