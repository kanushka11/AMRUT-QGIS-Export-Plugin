from PyQt5.QtWidgets import QDialog, QHBoxLayout, QVBoxLayout, QLabel, QWidget
from PyQt5.QtCore import Qt
from qgis.core import QgsProject, QgsVectorLayer
from qgis.gui import QgsMapCanvas, QgsMapToolPan

import zipfile
import tempfile
import os

class QualityCheckVisualizationDialog(QDialog):
    def __init__(self, parent, selected_layer_name, amrut_file_path):
        super().__init__(parent)
        self.selected_layer_name = selected_layer_name
        self.amrut_file_path = amrut_file_path  # AMRUT file path for GeoJSON extraction

        self.setWindowTitle("Quality Check Visualization")
        self.setWindowState(Qt.WindowMaximized)

        # Main layout
        layout = QHBoxLayout(self)

        # Left panel: Visualization of selected project layer
        layer = self.get_layer_by_name(self.selected_layer_name)
        if layer:
            left_panel = self.create_layer_visualization_panel(layer, "Selected Layer Visualization")
        else:
            left_panel = self.create_error_panel(f"Layer '{self.selected_layer_name}' not found.")
        
        # Right panel: Visualization of GeoJSON from AMRUT file
        right_panel = self.create_geojson_visualization_panel()

        # Adding panels and vertical divider to layout
        layout.addLayout(left_panel)
        self.add_vertical_divider(layout)
        layout.addLayout(right_panel)

    def create_geojson_visualization_panel(self):
        """Create a panel to visualize the GeoJSON extracted from the AMRUT file."""
        panel_layout = QVBoxLayout()

        # Load GeoJSON from AMRUT file
        geojson_layer = self.load_geojson_from_amrut(self.amrut_file_path, self.selected_layer_name)
        if geojson_layer:
            map_canvas = self.create_map_canvas(geojson_layer)
            panel_layout.addWidget(map_canvas)

            label = QLabel(f"AMRUT Layer Visualization: {self.selected_layer_name}")
            label.setAlignment(Qt.AlignCenter)
            panel_layout.addWidget(label)
        else:
            panel_layout.addWidget(QLabel("GeoJSON layer not found in AMRUT file."))

        return panel_layout

    def load_geojson_from_amrut(self, amrut_file_path, layer_name):
        """Extract and load the GeoJSON file from the AMRUT archive."""
        try:
            with zipfile.ZipFile(amrut_file_path, 'r') as zip_ref:
                geojson_filename = f"{layer_name}.geojson"

                if geojson_filename in zip_ref.namelist():
                    # Extract and read the GeoJSON content
                    with zip_ref.open(geojson_filename) as geojson_file:
                        geojson_content = geojson_file.read().decode('utf-8')

                    # Create a temporary file to load the GeoJSON
                    geojson_layer = QgsVectorLayer(geojson_content, layer_name, "GeoJSON")
                    if geojson_layer.isValid():
                        return geojson_layer
                    else:
                        raise ValueError(f"GeoJSON layer '{layer_name}' is not valid.")
                else:
                    raise FileNotFoundError(f"GeoJSON file '{geojson_filename}' not found in the AMRUT file.")
        except Exception as e:
            print(f"Error loading GeoJSON: {str(e)}")
            return None

    def get_layer_by_name(self, layer_name):
        """Retrieve a layer from the QGIS project by its name."""
        for layer in QgsProject.instance().mapLayers().values():
            if layer.name() == layer_name:
                return layer
        return None

    def create_layer_visualization_panel(self, layer, title):
        """Create a panel to visualize a specific project layer."""
        panel_layout = QVBoxLayout()
        
        map_canvas = self.create_map_canvas(layer)
        panel_layout.addWidget(map_canvas)

        label = QLabel(title)
        label.setAlignment(Qt.AlignCenter)
        panel_layout.addWidget(label)

        return panel_layout

    def create_map_canvas(self, layer):
        """Create a map canvas to render the given layer."""
        canvas = QgsMapCanvas()
        
        # Set canvas properties for better visualization
        canvas.setLayers([layer])
        canvas.setExtent(layer.extent())
        canvas.setCanvasColor(Qt.white)
        
        # Enable panning tool for better interaction
        canvas.setMapTool(QgsMapToolPan(canvas))
        
        canvas.refresh()
        
        return canvas

    def create_error_panel(self, message):
        """Create a panel to display an error message."""
        panel_layout = QVBoxLayout()
        
        error_label = QLabel(message)
        error_label.setAlignment(Qt.AlignCenter)
        
        panel_layout.addWidget(error_label)
        
        return panel_layout

    def add_vertical_divider(self, layout):
        """Add a vertical divider to the layout."""
        
        line_widget = QWidget()
        
        line_widget.setFixedWidth(2)  # Set width of divider line
        line_widget.setStyleSheet("background-color: black;")  # Set color of divider
        
        layout.addWidget(line_widget)
