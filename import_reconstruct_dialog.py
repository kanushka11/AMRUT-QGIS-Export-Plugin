from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QDialog,
    QTabWidget,
    QVBoxLayout,
    QWidget,
    QPushButton,
    QLabel,
    QProgressBar,
    QComboBox,
    QMessageBox,
    QFileDialog,
    QListWidget,
    QListWidgetItem,
    QHBoxLayout,
    QRadioButton,
    QSpinBox,
    QTabBar

)
from PyQt5.QtCore import QRunnable, QThreadPool, pyqtSignal, QObject, QThread
from . import export_ui as ui

class ReconstructLayerTabDialog(QDialog):
    def __init__(self, iface):
        super().__init__()
        self.thread = QThread()
        self.iface = iface
        self.setWindowTitle("Sankalan 2.0")
        self.setMinimumSize(700, 500)

        # Main layout
        layout = QVBoxLayout(self)

        # Tab widget
        self.logo_layout = ui.createLogoLayout("Reconstruct Vetted Data")
        self.tabs = QTabWidget()
        self.tabs.setTabBarAutoHide(True)  # Hides the tab bar
        self.tabs.setTabBar(self.CustomTabBar())
        layout.addLayout(self.logo_layout)
        layout.addWidget(self.tabs)

        # Create Tabs
        self.data_input_tab = self.create_data_input_tab()

        # Add Tabs
        self.tabs.addTab(self.data_input_tab, "Data Selection")


        self.progress_bar = QProgressBar()
        self.progress_lable = QLabel()
        layout.addWidget(self.progress_lable)
        layout.addWidget(self.progress_bar)

    def create_data_input_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        #Info lable
        information_lable = QLabel("Select the directory which contains the QC Verified AMRUT files")
        layout.addWidget(information_lable, alignment=Qt.AlignTop)

        # Add output directory selection
        self.data_dir_label = QLabel("Data Directory: Not Selected")
        layout.addWidget(self.data_dir_label, alignment=Qt.AlignTop)

        data_dir_button = QPushButton("Select Data Directory")
        data_dir_button.clicked.connect(self.select_data_directory)
        layout.addWidget(data_dir_button, alignment=Qt.AlignTop)

        return tab





    def select_data_directory(self):
        """Opens a dialog to select the output directory."""
        data_dir = QFileDialog.getExistingDirectory(self, "Select Data Directory")
        if data_dir:
            self.data_dir_label.setText(f"Data Directory: {output_dir}")
            self.data_dir = data_dir

    class CustomTabBar(QTabBar):
        def mousePressEvent(self, event):
            # Override the mousePressEvent to ignore clicks
            pass