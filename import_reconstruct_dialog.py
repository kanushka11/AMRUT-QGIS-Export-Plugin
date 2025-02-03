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
from qgis.core import (
    QgsProject,
    QgsProcessingFeedback,
    QgsMessageLog,
    Qgis,
    QgsVectorLayer,
    QgsApplication
)
from PyQt5.QtCore import QRunnable, QThreadPool, pyqtSignal, QObject, QThread
from . import export_ui as ui
from . import import_workers as workers
from qgis.core import QgsProject, QgsMapLayer

data_selection_tab_index = 0
layer_reconstruction_tab_index = 1


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

        self.navigation_layout = QHBoxLayout()
        self.next_button = QPushButton("Next")
        self.next_button.clicked.connect(self.navigate_next)
        self.navigation_layout.addWidget(self.next_button)

        layout.addLayout(self.navigation_layout)

    """N A V I G A T I O N      M E T H O D S"""
    def navigate_next(self):
        current_tab_index = self.tabs.currentIndex()
        if current_tab_index == data_selection_tab_index :
            if hasattr(self, "data_dir"):
                self.progress_lable.setText("Validating Data...")
                self.progress_bar.setRange(0,0)
                self.data_validation_worker = workers.AmrutFilesValidationWorker(self.data_dir)
                self.thread = QThread()
                self.data_validation_worker.moveToThread(self.thread)
                self.thread.started.connect(self.data_validation_worker.run)
                self.data_validation_worker.finished.connect(self.thread.quit)
                self.data_validation_worker.finished.connect(self.data_validation_worker.deleteLater)
                self.thread.finished.connect(self.thread.deleteLater)
                self.data_validation_worker.result_signal.connect(self.data_validation_result)
                self.thread.start()
            else :
                self.show_error("No directory selected")


    """R E S U L T S    H A N D L I N G"""
    def data_validation_result (self, result, data) :
        if result :
            self.show_success("Validation", "All AMRUT files are valid")
            self.amrut_files = data[0]
            self.layers_map = data[1]
            self.tabs.setCurrentIndex(layer_reconstruction_tab_index)
        else:
            error_msg = data
            self.show_error(error_msg)
    """T A B S      L A Y O U T"""

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

        # Raster Layer Selection
        self.raster_layer_dropdown = QComboBox()
        self.raster_layer_dropdown.addItem("Select a Raster Layer")  # Default option
        # Connect dropdown selection event
        self.raster_layer_dropdown.currentIndexChanged.connect(self.on_raster_layer_selected)

        # Assuming you have a method to get available raster layers
        raster_layers = self.get_available_raster_layers()
        self.raster_layer_dropdown.addItems(raster_layers)

        raster_information_lable = QLabel("Select a Raster Layer (optional) to correspond changes :")
        layout.addWidget(raster_information_lable, alignment=Qt.AlignTop)
        layout.addWidget(self.raster_layer_dropdown, alignment=Qt.AlignTop)

        return tab



    """U T L I T Y      M E T H O D S"""

    def select_data_directory(self):
        """Opens a dialog to select the output directory."""
        data_dir = QFileDialog.getExistingDirectory(self, "Select Data Directory")
        if data_dir:
            self.data_dir_label.setText(f"Data Directory: {data_dir}")
            self.data_dir = data_dir


    def get_available_raster_layers(self):
        """
        Fetches available raster layers from the current QGIS project.
        Returns a list of raster layer names.
        """
        raster_layers = []

        for layer in QgsProject.instance().mapLayers().values():
            if layer.type() == QgsMapLayer.RasterLayer:  # Check if the layer is a raster layer
                raster_layers.append(layer.name())  # Append raster layer name

        return raster_layers

    def on_raster_layer_selected(self):
        """Handles selection of a raster layer from the dropdown."""
        selected_layer_name = self.raster_layer_dropdown.currentText()

        # Ignore default option
        if selected_layer_name == "Select a Raster Layer":
            self.selected_raster_layer = None
        else:
            self.selected_raster_layer = selected_layer_name

        print(f"Selected Raster Layer: {self.selected_raster_layer}")

    def show_error (self, error):
        self.progress_bar.setRange(0, 100)  # Reset progress bar range
        self.progress_lable.setText("")
        QMessageBox.critical(self,"Error", str(error))
        QgsMessageLog.logMessage(str(error), 'AMRUT', Qgis.Critical)

    def show_success (self, title, message):
        self.progress_bar.setRange(0, 100)  # Reset progress bar range
        self.progress_lable.setText("")
        QMessageBox.information(self, title, message)
        QgsMessageLog.logMessage(str(error), 'AMRUT', Qgis.Critical)

    class CustomTabBar(QTabBar):
        def mousePressEvent(self, event):
            # Override the mousePressEvent to ignore clicks
            pass