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
    QHBoxLayout,
    QTabBar

)
from qgis.core import (
    QgsProject,
    QgsMessageLog,
    Qgis,
    QgsVectorLayer,
    QgsProcessingFeatureSourceDefinition,
)
from PyQt5.QtCore import QThread, Qt
from PyQt5.QtGui import QPixmap
from . import export_ui as ui
from . import import_workers as workers
from . import import_process_layer as process
from . import import_reconstruct_feature

from qgis.core import QgsProject, QgsMapLayer
import os
import sip
import processing



data_selection_tab_index = 0
layer_reconstruction_tab_index = 1



class ReconstructLayerTabDialog(QDialog):
    def __init__(self, iface):
        super().__init__()
        self.thread = QThread()
        self.iface = iface
        self.setWindowTitle("Sankalan 2.0")
        self.setMinimumSize(700, 500)
        self.processing_layer = False
        self.selected_raster_layer_name = None

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
        self.reprojected_raster_layer = None

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

    def closeEvent(self, event):
        """Handle cleanup on dialog close."""
        # Stop all running threads
        if hasattr(self, 'thread') and self.thread:
            if not sip.isdeleted(self.thread):  # Check if the thread is already deleted
                if self.thread.isRunning():
                    self.thread.quit()
                    self.thread.wait()
        if hasattr(self, 'layer_thread') and self.layer_thread:
            if not sip.isdeleted(self.layer_thread):  # Check if the thread is already deleted
                if self.layer_thread.isRunning():
                    self.layer_thread.quit()
                    self.layer_thread.wait()

        event.accept()  # Allow the dialog to close

    """R E S U L T S    H A N D L I N G"""

    def data_validation_result (self, result, data) :
        if result :
            self.show_success("Validation", "All AMRUT files are valid")
            self.amrut_files = data[0]
            self.layers_map = data[1]
            self.layer_construction_tab = self.create_layer_construction_tab()
            self.tabs.addTab(self.layer_construction_tab, "Construct Layer")
            self.tabs.setCurrentIndex(layer_reconstruction_tab_index)
            print(f"Layers : {self.layers_map}")

        else:
            error_msg = data
            self.show_error(error_msg)

    def layer_construction_result (self, result, data) :
        if result :
            self.show_success("Layer", f"Layer successfully re-constructed and saved at {data}")
            temporary_layer_name = f"Temporary_{self.selected_layer_for_processing}"
            self.saved_temp_layer = QgsVectorLayer(data, temporary_layer_name, "ogr")
            QgsProject.instance().addMapLayer(self.saved_temp_layer)
            self.compare_changes()

        else :
            self.show_error(data)
            self.processing_layer = False

    def get_layer_by_name(self, layer_name):
        """Retrieve a layer from the QGIS project by its name."""
        try:
            for layer in QgsProject.instance().mapLayers().values():
                if layer.name() == layer_name:
                    return layer
            return None
        except Exception as e:
            QgsMessageLog.logMessage(f"Error in get_layer_by_name: {str(e)}", 'AMRUT', Qgis.Critical)
            return None

    def compare_changes_result(self, result, data):
        if result :
            if len(data) == 0 :
                self.show_success("Layer", "All changes processed")
                self.processing_layer = False
            else :
                self.selected_raster_layer = self.get_layer_by_name(self.selected_raster_layer_name)
                selected_layer = self.get_layer_by_name(self.selected_layer_for_processing)
                reconstruct_feature = import_reconstruct_feature.ReconstructFeatures(selected_layer, self.saved_temp_layer, self.selected_raster_layer, data)
                reconstruct_feature.merge_attribute_dialog()
                # self.transform_raster_CRS(self.saved_temp_layer, self.selected_raster_layer)
                # merged_layer = self.merge_features_by_attribute(self.saved_temp_layer, "feature_id")
                # print(merged_layer)
        else :
            self.show_error(data)
            self.processing_layer = False

    def merge_features_by_attribute(self, input_layer, attribute):
        """
        Merges features in a given layer based on a common attribute using QGIS's Dissolve algorithm.

        :param input_layer: The input vector layer (QgsVectorLayer)
        :param attribute: The attribute name to dissolve by (string)
        :return: The output layer containing merged features
        """
        print(input_layer)
        if not input_layer or not isinstance(input_layer, QgsVectorLayer):
            print("Invalid input layer")
            return None

        # Define the parameters for the dissolve algorithm
        params = {
            'INPUT': QgsProcessingFeatureSourceDefinition(input_layer.source(), selectedFeaturesOnly=False),
            'FIELD': [attribute],  # Field to dissolve by
            'OUTPUT': 'memory:'  # Output to a temporary memory layer
        }

        # Run the dissolve algorithm
        result = processing.run("native:dissolve", params)

        # Get the output layer
        output_layer = result['OUTPUT']
        QgsProject.instance().addMapLayer(output_layer)
        return output_layer

    """C O N S T R U C T    L A Y E R S"""
    def construct_layer (self, layer_name) :
        if not self.processing_layer :
            self.processing_layer = True
            self.selected_layer_for_processing = layer_name
            is_in_temporary_stage = self.is_layer_in_temporary_stage(layer_name)
            if is_in_temporary_stage :
                process.process_temp_layer(layer_name)
            else:
                try :
                    self.progress_lable.setText("Constructing Layer...")
                    self.progress_bar.setRange(0, 0)
                    self.layer_construction_worker = workers.LayerConstructionWorker(self.data_dir, self.amrut_files,
                                                                                   layer_name)
                    self.layer_thread = QThread()
                    self.layer_construction_worker.moveToThread(self.layer_thread)
                    self.layer_thread.started.connect(self.layer_construction_worker.run)
                    self.layer_construction_worker.finished.connect(self.layer_thread.quit)
                    self.layer_construction_worker.finished.connect(self.layer_construction_worker.deleteLater)
                    self.layer_thread.finished.connect(self.layer_thread.deleteLater)
                    self.layer_construction_worker.result_signal.connect(self.layer_construction_result)
                    self.layer_thread.start()
                except Exception as e :
                    raise Exception (str(e))

    def compare_changes(self):
        self.progress_lable.setText("Comparing Changes...")
        self.compare_changes_worker = workers.CompareChangesWorker(self.selected_layer_for_processing)
        self.compare_changes_thread = QThread()
        self.compare_changes_worker.moveToThread(self.compare_changes_thread)
        self.compare_changes_thread.started.connect(self.compare_changes_worker.run)
        self.compare_changes_worker.finished.connect(self.compare_changes_thread.quit)
        self.compare_changes_worker.finished.connect(self.compare_changes_worker.deleteLater)
        self.compare_changes_thread.finished.connect(self.compare_changes_thread.deleteLater)
        self.compare_changes_worker.result_signal.connect(self.compare_changes_result)
        self.compare_changes_thread.start()


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


    def create_layer_construction_tab (self) :
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(2, 2, 2, 2)
        information_label = QLabel("Layers available to Re-Construct")
        layout.addWidget(information_label, alignment=Qt.AlignTop)
        layers_name = list(self.layers_map.keys())
        layers_layout = QVBoxLayout()

        for layer in layers_name :
            layers_layout.addLayout(self.get_layer_layout(layer))  # Get the layout

        layers_widget = QWidget()
        layers_widget.setLayout(layers_layout)
        layout.addWidget(layers_widget, alignment=Qt.AlignTop)

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
            self.selected_raster_layer_name = None
        else:
            self.selected_raster_layer_name = selected_layer_name

        print(f"Selected Raster Layer: {self.selected_raster_layer_name}")

    def show_error (self, error):
        self.progress_bar.setRange(0, 100)  # Reset progress bar range
        self.progress_lable.setText("")
        QMessageBox.critical(self,"Error", str(error))
        QgsMessageLog.logMessage(str(error), 'AMRUT', Qgis.Critical)

    def show_success (self, title, message):
        self.progress_bar.setRange(0, 100)  # Reset progress bar range
        self.progress_lable.setText("")
        QMessageBox.information(self, title, message)

    class CustomTabBar(QTabBar):
        def mousePressEvent(self, event):
            # Override the mousePressEvent to ignore clicks
            pass

    def get_layer_layout (self, layer_name):
        layout = QHBoxLayout(self)
        name_label = QLabel(layer_name)
        status_icon = QLabel()
        process_button = QPushButton("Process")

        layer_status_processed = self.get_layer_status(layer_name)
        if layer_status_processed :
            pixmap = ui.get_checked_icon()
        else:
            pixmap = ui.get_warning_icon()
        status_icon.setPixmap(pixmap)
        process_button.clicked.connect(lambda: self.construct_layer(layer_name))

        layout.addWidget(name_label)
        layout.addWidget(process_button)
        layout.addWidget(status_icon)
        return layout

    def get_layer_status( self,layer_name):
        """Update the symbol based on status"""
        processed = False
        processed_layer_name = f"{layer_name}_vetted"
        for layer in QgsProject.instance().mapLayers().values():
            if layer.name() == processed_layer_name:
                processed = True

        return processed
    def is_layer_in_temporary_stage (self, layer_name) :
        print(f"Checking for Temporary layer for {layer_name} layer")
        temporary = False
        temporary_layer_name = f"Temporary_{layer_name}"
        for layer in QgsProject.instance().mapLayers().values():
            if layer.name() == temporary_layer_name:
                temporary = True

        return temporary

    class LayerItem(QWidget):
        def __init__(self, layer_name, parent=None):
            super().__init__(parent)

            self.layer_name = layer_name
            self.status = "pending"  # Default status

            # Create layout
            layout = QHBoxLayout(self)

            # Layer name label
            self.name_label = QLabel(layer_name)
            layout.addWidget(self.name_label)

            # Process button
            self.process_button = QPushButton("Process")
            # self.process_button.clicked.connect(self.process_layer)
            layout.addWidget(self.process_button)

            # Status icon
            self.status_icon = QLabel()
            self.update_status_icon()
            layout.addWidget(self.status_icon)

            self.setLayout(layout)

        def process_layer(self):
            """Simulate processing and update status"""
            self.status = "processed"
            self.update_status_icon()

        def update_status_icon(self):
            """Update the symbol based on status"""
            if self.status == "pending":
                pixmap = QPixmap(20, 20)
                pixmap.fill(Qt.red)  # Red for pending
            else:
                pixmap = QPixmap(20, 20)
                pixmap.fill(Qt.green)  # Green for processed

            self.status_icon.setPixmap(pixmap)

    class LayerList(QWidget):
        def __init__(self, layers, parent):
            super().__init__(None)
            self.layout = QVBoxLayout(self)
            self.parent = parent

            self.layer_items = []

            for layer in layers:
                item = ReconstructLayerTabDialog.LayerItem(layer)
                self.layout.addWidget(item)
                self.layer_items.append(item)


        def get_layout(self):
            return self.layout

