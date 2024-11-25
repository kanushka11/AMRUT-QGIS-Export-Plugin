
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
    QListWidgetItem

)
from qgis.core import QgsProject, QgsProcessingFeedback
from . import clip, grid, geometry, ui
import os


class ClipMergeExportTabDialog(QDialog):
    def __init__(self, iface):
        super().__init__()
        self.iface = iface
        self.setWindowTitle("Clip and Merge Export")
        self.setMinimumSize(600, 400)

        # Main layout
        layout = QVBoxLayout(self)

        # Tab widget
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # Tabs
        self.layer_selection_tab = self.create_layer_selection_tab()
        self.grid_creation_tab = self.create_grid_creation_tab()
        self.clipping_tab = self.create_clipping_tab()

        self.tabs.addTab(self.layer_selection_tab, "Layer Selection")
        self.tabs.addTab(self.grid_creation_tab, "Grid Creation")
        self.tabs.addTab(self.clipping_tab, "Clipping and Export")

        # Final action buttons
        self.run_button = QPushButton("Run")
        self.run_button.clicked.connect(self.run_process)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.close)
        layout.addWidget(self.run_button)
        layout.addWidget(self.cancel_button)

    def create_layer_selection_tab(self):
        """Creates the Layer Selection tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Add layer selection combo box
        self.layer_combo_box = QComboBox()
        selectedLayers = []
        all_layers = [layer for layer in QgsProject.instance().mapLayers().values() if layer.isValid()]
        selectionLayout = QVBoxLayout()


        # Add list widget to show layers
        layer_list_widget = QListWidget()
        for layer in all_layers:
            item = QListWidgetItem(layer.name())
            item.setCheckState(Qt.Unchecked)
            layer_list_widget.addItem(item)

        selectionLayout.addWidget(layer_list_widget)

        # Collect selected layers
        for i in range(layer_list_widget.count()):
            item = layer_list_widget.item(i)
            if item.checkState() == Qt.Checked:
                layer_name = item.text()
                for layer in all_layers:
                    if layer.name() == layer_name:
                        selectedLayers.append(layer)
                        break
                    
        layout.addWidget(QLabel("Select Layers:"))
        layout.addLayout(selectionLayout)

        return tab

    def create_grid_creation_tab(self):
        """Creates the Grid Creation tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Add instructions
        layout.addWidget(QLabel("Create a grid for the selected layers."))

        # Add progress bar
        self.grid_progress_bar = QProgressBar()
        layout.addWidget(self.grid_progress_bar)

        return tab

    def create_clipping_tab(self):
        """Creates the Clipping and Export tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Add output directory selection
        self.output_dir_label = QLabel("Output Directory: Not Selected")
        layout.addWidget(self.output_dir_label)

        self.output_dir_button = QPushButton("Select Output Directory")
        self.output_dir_button.clicked.connect(self.select_output_directory)
        layout.addWidget(self.output_dir_button)

        return tab

    def select_output_directory(self):
        """Opens a dialog to select the output directory."""
        output_dir = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if output_dir:
            self.output_dir_label.setText(f"Output Directory: {output_dir}")
            self.output_dir = output_dir

    def run_process(self):
        """Runs the entire process based on the current tab."""
        selected_layer_name = self.layer_combo_box.currentText()
        if not selected_layer_name:
            QMessageBox.warning(self, "Error", "No layer selected!")
            return

        # Validate geometries
        selected_layer = next(
            (layer for layer in QgsProject.instance().mapLayers().values() if layer.name() == selected_layer_name), None
        )
        if not selected_layer:
            QMessageBox.critical(self, "Error", "Selected layer not found!")
            return

        try:
            # Step 1: Validate geometries and extents
            combined_extent = geometry.check_geometries_and_extents([selected_layer])

            # Step 2: Create a grid
            grid_layer = grid.create_500m_grid(combined_extent.toRectF().getCoords())
            grid.add_grid_labels(grid_layer)
            QgsProject.instance().addMapLayer(grid_layer)
            QMessageBox.information(self, "Grid Creation", "Grid created successfully.")

            # Step 3: Clip layers
            if hasattr(self, "output_dir"):
                clip.clip_layers_to_grid(grid_layer, [selected_layer], self.output_dir, QgsProcessingFeedback())
                QMessageBox.information(self, "Clipping Complete", "Layers clipped and exported successfully.")
            else:
                QMessageBox.warning(self, "Error", "Output directory not selected.")

        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
