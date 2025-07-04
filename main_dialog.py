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
    QTabBar,
    QCheckBox
)
from qgis.core import (
    QgsProject,
    QgsProcessingFeedback,
    QgsMessageLog,
    Qgis,
    QgsMapLayer,
    QgsApplication
)
from PyQt5.QtCore import QRunnable, QThreadPool, pyqtSignal, QObject, QThread
from . import export_clip as clip, export_grid as grid, export_geometry as geometry, export_ui as ui
from . import export_workers as workers
import os
import sip


selectedLayers = []
gridLayer = None
outputDirectory = ""
selectedLayerForGrid = None

layer_selection_tab_index = 0
grid_selection_tab_index = 1
clipping_tab_index = 2

class ClipMergeExportTabDialog(QDialog):
    def __init__(self, iface):
        super().__init__()
        self.thread = QThread()
        self.iface = iface
        self.setWindowTitle("AMRUT 2.0 Export Data")
        self.setMinimumSize(700, 500)

        # Main layout
        layout = QVBoxLayout(self)

        # Tab widget
        self.logo_layout = ui.createLogoLayout("Export Data for Mobile App")
        self.tabs = QTabWidget()
        self.tabs.setTabBarAutoHide(True)  # Hides the tab bar
        self.tabs.setTabBar(self.CustomTabBar())
        layout.addLayout(self.logo_layout)
        layout.addWidget(self.tabs)

        # Tabs
        self.layer_selection_tab = self.create_layer_selection_tab()
        self.grid_creation_tab = self.create_grid_creation_tab()
        self.clipping_tab = self.create_clipping_tab()

        self.tabs.addTab(self.layer_selection_tab, "Layer Selection")
        self.tabs.addTab(self.grid_creation_tab, "Grid Creation")
        self.tabs.addTab(self.clipping_tab, "Clipping and Export")

        self.progress_bar = QProgressBar()
        self.progress_lable = QLabel()
        layout.addWidget(self.progress_lable)
        layout.addWidget(self.progress_bar)
        self.progress_bar.setVisible(False)

        # Navigation buttons
        self.navigation_layout = QHBoxLayout()
        self.back_button = QPushButton("Back")
        self.back_button.clicked.connect(self.navigate_back)
        self.back_button.setEnabled(False)  # Initially disabled
        self.navigation_layout.addWidget(self.back_button)

        self.next_button = QPushButton("Next")
        self.next_button.clicked.connect(self.navigate_next)
        self.navigation_layout.addWidget(self.next_button)

        layout.addLayout(self.navigation_layout)

    def closeEvent(self, event):
        """Handle cleanup on dialog close."""
        # Stop all running threads
        if hasattr(self, 'thread') and self.thread:
            if not sip.isdeleted(self.thread):  # Check if the thread is already deleted
                if self.thread.isRunning():
                    self.thread.quit()
                    self.thread.wait()

        event.accept()  # Allow the dialog to close


    def create_layer_selection_tab(self):
        """Creates the Layer Selection tab with separate Vector and Raster layer selection."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Vector Layers
        layout.addWidget(QLabel("Select Vector Layers:"))
        self.select_all_vector_checkbox = QCheckBox("Select All Vector Layers")
        self.select_all_vector_checkbox.stateChanged.connect(self.select_all_vector_layers)
        layout.addWidget(self.select_all_vector_checkbox)

        self.vector_layer_list_widget = QListWidget()
        self.vector_layer_list_widget.setSelectionMode(QListWidget.MultiSelection)
        layout.addWidget(self.vector_layer_list_widget)

        # Raster Layers
        layout.addWidget(QLabel("Select Raster Layers:"))
        self.raster_layer_list_widget = QListWidget()
        self.raster_layer_list_widget.setSelectionMode(QListWidget.MultiSelection)
        layout.addWidget(self.raster_layer_list_widget)

        # Populate layers
        all_layers = QgsProject.instance().mapLayers().values()
        for layer in all_layers:
            item = QListWidgetItem(layer.name())
            item.setCheckState(Qt.Unchecked)
            if layer.type() == QgsMapLayer.VectorLayer:
                self.vector_layer_list_widget.addItem(item)
            elif layer.type() == QgsMapLayer.RasterLayer:
                self.raster_layer_list_widget.addItem(item)

        global selectedLayers
        selectedLayers = []
        self.vector_layer_list_widget.itemChanged.connect(self.update_selected_layers)
        self.raster_layer_list_widget.itemChanged.connect(self.update_raster_selection)

        return tab

    def select_all_vector_layers(self, state):
        """Checks or unchecks all vector layers based on the select all checkbox."""
        check_state = Qt.Checked if state == Qt.Checked else Qt.Unchecked
        for i in range(self.vector_layer_list_widget.count()):
            self.vector_layer_list_widget.item(i).setCheckState(check_state)

    def update_selected_layers(self, item):
        """Updates the list of selected layers based on the item check state."""
        global selectedLayers
        layer_name = item.text()
        all_layers = QgsProject.instance().mapLayers().values()

        if item.checkState() == Qt.Checked:
            for layer in all_layers:
                if layer.name() == layer_name and layer not in selectedLayers:
                    selectedLayers.append(layer)
                    break
        else:
            selectedLayers = [layer for layer in selectedLayers if layer.name() != layer_name]

    def update_raster_selection(self, item):
        """Ensures only one raster layer can be selected at a time."""
        if item.checkState() == Qt.Checked:
            for i in range(self.raster_layer_list_widget.count()):
                current_item = self.raster_layer_list_widget.item(i)
                if current_item != item and current_item.checkState() == Qt.Checked:
                    current_item.setCheckState(Qt.Unchecked)
        
        # Update the selected layers list accordingly
        self.update_selected_layers(item)

    def create_grid_creation_tab(self):
        """Creates the Grid Creation tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)

        self.question = "Do you already have grid / segmentation Layer to clip ?"
        self.questionLable = QLabel(self.question)
        
        self.radio_layout = QHBoxLayout()
        self.yes_radio = QRadioButton("Yes")
        self.no_radio = QRadioButton("No")
        self.radio_layout.addWidget(self.yes_radio)
        self.radio_layout.addWidget(self.no_radio)

        self.radio_widget = QWidget()
        self.radio_widget_layout = QVBoxLayout(self.radio_widget)
        self.radio_widget_layout.addWidget(self.questionLable)
        self.radio_widget_layout.addLayout(self.radio_layout)
        self.radio_widget_layout.setContentsMargins(0, 0, 0, 0)  # No extra margins
        layout.addWidget(self.radio_widget, alignment=Qt.AlignTop)


        self.dropdown_lable = QLabel("")
        self.dropdown_lable.setVisible(False)
        self.layer_dropdown = QComboBox()
        self.layer_map = {}
        
        for layer in QgsProject.instance().mapLayers().values():
            self.layer_dropdown.addItem(layer.name())
            self.layer_map[layer.name()] = layer
            global selectedLayerForGrid
            if selectedLayerForGrid is None :
                selectedLayerForGrid = layer

        def on_layer_selected(index):
            global selectedLayerForGrid
            selected_layer_name = self.layer_dropdown.itemText(index)
            selectedLayerForGrid = self.layer_map.get(selected_layer_name)
            QgsMessageLog.logMessage('Layer Selected :'+selectedLayerForGrid.name(), 'AMRUT_Export', Qgis.Info)



        self.layer_dropdown.currentIndexChanged.connect(on_layer_selected)
        self.layer_dropdown.setVisible(False) 

        self.number_input = QSpinBox()
        self.number_input.setRange(100, 10000)  # Set range as needed
        self.number_input.setVisible(False)  # Initially hidden

        number_label = QLabel("Input Grid Size (in Meters) :")  # To be shown with number input
        number_label.setVisible(False)

        layout.addWidget(self.dropdown_lable, alignment=Qt.AlignTop)
        layout.addWidget(self.layer_dropdown, alignment=Qt.AlignTop)
        layout.addWidget(number_label, alignment=Qt.AlignTop)
        layout.addWidget(self.number_input, alignment=Qt.AlignTop)

        def on_radio_button_toggled():
            if self.yes_radio.isChecked():
                self.layer_dropdown.setVisible(True)
                self.dropdown_lable.setText("Select Grid / Segmentation Layer : ")
                self.dropdown_lable.setVisible(True)
                self.number_input.setVisible(False)
                number_label.setVisible(False)
            elif self.no_radio.isChecked():
                self.layer_dropdown.setVisible(True)
                self.dropdown_lable.setText("Select Area Boundary Layer : ")
                self.dropdown_lable.setVisible(True)
                self.number_input.setVisible(True)
                number_label.setVisible(True)
        
        self.yes_radio.toggled.connect(on_radio_button_toggled)
        self.no_radio.toggled.connect(on_radio_button_toggled)
        

        return tab

    def create_clipping_tab(self):
        """Creates the Clipping and Export tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        # Add output directory selection
        self.output_dir_label = QLabel("Output Directory: Not Selected")
        layout.addWidget(self.output_dir_label,  alignment=Qt.AlignTop)

        self.output_dir_button = QPushButton("Select Output Directory")
        self.output_dir_button.clicked.connect(self.select_output_directory)
        layout.addWidget(self.output_dir_button,  alignment=Qt.AlignTop)

        return tab

    def select_output_directory(self):
        """Opens a dialog to select the output directory."""
        output_dir = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if output_dir:
            self.output_dir_label.setText(f"Output Directory: {output_dir}")
            self.output_dir = output_dir

    def run_process(self):
        """Runs the entire process based on the current tab."""
        if not selectedLayers:
            QMessageBox.critical(self, "Error", "No selected Layer")
            return

        try:
            if hasattr(self, "output_dir"):
                    self.progress_bar.setVisible(True)
                    global gridLayer
                    self.progress_lable.setText("Clipping...Please Wait")
                    self.progress_bar.setValue(0)
                    self.progress_bar.setMaximum(gridLayer.featureCount() -2)
                     # Disable navigation buttons
                    self.next_button.setEnabled(False)
                    self.back_button.setEnabled(False)
                    self.thread = QThread()
                    self.clipWorker = workers.ClippingWorker(gridLayer, selectedLayers, self.output_dir)
                    self.clipWorker.moveToThread(self.thread)
                    self.thread.started.connect(self.clipWorker.run)
                    self.clipWorker.finished.connect(self.thread.quit)
                    self.clipWorker.finished.connect(self.clipWorker.deleteLater)
                    self.thread.finished.connect(self.thread.deleteLater)
                    self.clipWorker.success_signal.connect(self.handle_clip_success)
                    self.clipWorker.progress_signal.connect(self.update_clipping_progress)
                    self.clipWorker.error_signal.connect(self.show_error)
                    self.thread.start()
            else:
                QMessageBox.warning(self, "Error", "Output directory not selected.")

        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            self.progress_bar.setVisible(False)
            self.progress_lable.setText("")
            self.next_button.setEnabled(True)  # Re-enable Run button in case of error
            self.back_button.setEnabled(True)


    def navigate_back(self):
        """Navigate to the previous tab."""
        self.progress_bar.setVisible(False)
        self.progress_lable.setText("")
        current_index = self.tabs.currentIndex()
        if current_index > 0:
            self.tabs.setCurrentIndex(current_index - 1)
            self.next_button.setText("Next")  # Reset the button text if changed
            self.back_button.setEnabled(current_index - 1 > 0)

    def navigate_next(self):
        """Navigate to the next tab or run the process."""
        global selectedLayerForGrid
        global gridLayer
        current_index = self.tabs.currentIndex()
        if current_index == clipping_tab_index:
            self.progress_bar.setTextVisible(True)
            # Final tab: Run process
            self.next_button.setEnabled(False)
            self.back_button.setEnabled(False)
            self.run_process()
        else:
            # Move to the next tab
            if(current_index == layer_selection_tab_index) :
                #validate layers
                if len(selectedLayers) > 0 :
                    # Disable next button and show progress bar
                    self.next_button.setEnabled(False)
                    self.progress_bar.setRange(0, 0)  # Indeterminate state
                    self.progress_lable.setText("Validating Layers")
                    QgsMessageLog.logMessage("Validation started...", "AMRUT_Export", Qgis.Info)
                    # Create worker for validation
                    self.layerValidationWorker = workers.LayerValidationWorker(selectedLayers)
                    self.thread = QThread()
                    self.layerValidationWorker.moveToThread(self.thread)
                    self.thread.started.connect(self.layerValidationWorker.run)
                    self.layerValidationWorker.finished.connect(self.thread.quit)
                    self.layerValidationWorker.finished.connect(self.layerValidationWorker.deleteLater)
                    self.thread.finished.connect(self.thread.deleteLater)
                    self.layerValidationWorker.result_signal.connect(self.handle_layer_validation_result)
                    self.thread.start()
                    
                else:
                    QMessageBox.critical(self,"Error", "No Layers slected") 
            
            if current_index == grid_selection_tab_index :
                if self.yes_radio.isChecked() :
                    # get grid /segmanation layer and validate it 
                    gridLayer = selectedLayerForGrid
                    self.layerValidationWorker = workers.GridLayerValidationWorker(gridLayer)
                    self.next_button.setEnabled(False)
                    self.progress_bar.setRange(0, 0)  # Indeterminate state
                    self.progress_lable.setText("Processing...")
                    self.thread = QThread()
                    self.layerValidationWorker.moveToThread(self.thread)
                    self.thread.started.connect(self.layerValidationWorker.run)
                    self.layerValidationWorker.finished.connect(self.thread.quit)
                    self.layerValidationWorker.finished.connect(self.layerValidationWorker.deleteLater)
                    self.thread.finished.connect(self.thread.deleteLater)
                    self.layerValidationWorker.result_signal.connect(self.handle_grid_layer_validation_result)
                    self.thread.start()

                if self.no_radio.isChecked() :
                    #get grid input and admin boundary and then create grid
                    gridLayer = selectedLayerForGrid
                    self.next_button.setEnabled(False)
                    self.progress_bar.setRange(0, 0)  # Indeterminate state
                    print("Grid Size : "+ str(self.number_input.value()))
                    self.progress_lable.setText("Creating Layer...")
                    self.thread = QThread()
                    self.layerValidationWorker = workers.GridLayerCreationWorker(selectedLayers, gridLayer, self.number_input.value())
                    self.layerValidationWorker.moveToThread(self.thread)
                    self.thread.started.connect(self.layerValidationWorker.run)
                    self.layerValidationWorker.finished.connect(self.thread.quit)
                    self.layerValidationWorker.finished.connect(self.layerValidationWorker.deleteLater)
                    self.thread.finished.connect(self.thread.deleteLater)
                    self.layerValidationWorker.layer_signal.connect(self.handle_grid_creation_result)
                    self.layerValidationWorker.error_signal.connect(self.show_error)
                    self.thread.start()
            
            

            # If this is the last tab, change "Next" to "Run"
            if current_index + 1 == self.tabs.count() - 1:
                self.next_button.setText("Run")
    
    def show_error (self, error):
        self.back_button.setEnabled(True)
        self.next_button.setEnabled(True)
        self.progress_bar.setRange(0, 100)  # Reset progress bar range
        self.progress_lable.setText("")
        self.progress_bar.setVisible(False)
        QMessageBox.critical(self,"Error", str(error))
        QgsMessageLog.logMessage(str(error), 'AMRUT_Export', Qgis.Critical)
    
    
    def handle_layer_validation_result(self, valid, error_message):
        """Handle the result of the validation task."""
        self.progress_bar.setRange(0, 100)  # Reset progress bar range
        self.progress_lable.setText("")

        if valid:
            # If validation succeeded, move to the next tab
            QMessageBox.information(self, "Layer Validation", "Selected Layers are valid.")
            self.tabs.setCurrentIndex(self.tabs.currentIndex() + 1)
            self.back_button.setEnabled(True)
            self.next_button.setEnabled(True)
        else:
            # Show an error message if validation failed
            QMessageBox.critical(self, "Validation Error", error_message)
            self.progress_bar.setRange(0, 100)  # Reset progress bar range
            self.progress_lable.setText("")
            self.next_button.setEnabled(True)
    
    def handle_grid_layer_validation_result(self, valid, error_message):
        """Handle the result of the validation task."""
        self.progress_bar.setRange(0, 100)  # Reset progress bar range
        self.progress_lable.setText("")
        global gridLayer
        global selectedLayerForGrid

        if valid:
            # If validation succeeded, move to the next tab
            QMessageBox.information(self, "Layer Validation", "Selected Grid Layer is valid.")
            gridLayer = selectedLayerForGrid
            self.tabs.setCurrentIndex(self.tabs.currentIndex() + 1)
            self.back_button.setEnabled(True)
            self.next_button.setEnabled(True)
        else:
            # Show an error message if validation failed
            QMessageBox.critical(self, "Validation Error", error_message)
            self.progress_bar.setRange(0, 100)  # Reset progress bar range
            self.progress_lable.setText("")
            self.next_button.setEnabled(True)

    def handle_grid_creation_result(self, layer_id):
        """Handle the result of the validation task."""
        try :
            self.progress_bar.setRange(0, 100)  # Reset progress bar range
            self.progress_lable.setText("")
            global gridLayer
            gridLayer = self.get_layer_by_name(str(layer_id))
            QMessageBox.information(self, "Layer Creation", "Grid layer Created Successfully")
            QgsMessageLog.logMessage('Layer Created : '+ layer_id, 'AMRUT_Export', Qgis.Info)
            self.tabs.setCurrentIndex(self.tabs.currentIndex() + 1)
            self.next_button.setEnabled(True)
        except Exception as e : 
            raise Exception(str(e))
    
    def get_layer_by_name(self, layer_name):
        layers = QgsProject.instance().mapLayers().values()  # Get all layers in the project
        for layer in layers:
            if layer.name() == layer_name:  # Check if the layer name matches
                return layer
        return None  
    
    def handle_clip_success(self, success):
        if success:
            self.progress_lable.setText("Clipping completed")
            QMessageBox.information(self, "Clipping", "Clipping completed")
            self.close()  # Close the main dialog
    
    def update_clipping_progress (self, progress) :
        self.progress_bar.setValue(progress)

    class CustomTabBar(QTabBar):
        def mousePressEvent(self, event):
            # Override the mousePressEvent to ignore clicks
            pass

    

