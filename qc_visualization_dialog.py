from PyQt5.QtWidgets import QDialog, QHBoxLayout, QVBoxLayout, QLabel
from PyQt5.QtCore import Qt, QTimer  
from qgis.core import QgsProject, QgsVectorLayer, QgsCoordinateTransform, QgsCoordinateReferenceSystem
from qgis.gui import QgsMapCanvas, QgsMapToolPan
from . import new_feature_choice
import zipfile
import tempfile
import os

class QualityCheckVisualizationDialog(QDialog):
    def __init__(self, parent, selected_layer_name, amrut_file_path, selected_raster_layer_name, grid_extent):
        super().__init__(parent)
        self.selected_layer_name = selected_layer_name
        self.amrut_file_path = amrut_file_path  # AMRUT file path for GeoJSON extraction
        self.selected_raster_layer_name = selected_raster_layer_name
        self.grid_extent = grid_extent
        self.setWindowTitle("Quality Check Visualization")
        self.setWindowState(Qt.WindowMaximized)

        # Main layout
        layout = QHBoxLayout(self)

        # Left panel: Visualization of selected project layer
        layer = self.get_layer_by_name(self.selected_layer_name)
        raster_layer = self.get_layer_by_name(self.selected_raster_layer_name)

        if layer:
            left_panel = self.create_layer_visualization_panel(layer, "Selected Layer Visualization", raster_layer)
        else:
            left_panel = self.create_error_panel(f"Layer '{self.selected_layer_name}' not found.")
        layout.addLayout(left_panel)

        # Add a vertical divider
        self.add_vertical_divider(layout)

        # Right panel: Visualization of GeoJSON from AMRUT file
        right_panel = self.create_geojson_visualization_panel(raster_layer)
        layout.addLayout(right_panel)

        QTimer.singleShot(1000, self.show_new_feature_dialog)  # Delay in ms before triggering check

    def show_new_feature_dialog(self):
        """Show dialog box after both layers are visualized."""
        # Initialize the feature handler for new features
        feature_handler = new_feature_choice.NewFeatureFoundDialog(self.selected_layer_name)
        feature_handler.check_for_new_features()

    def create_geojson_visualization_panel(self, raster_layer):
        """Create a panel to visualize the GeoJSON extracted from the AMRUT file."""
        panel_layout = QVBoxLayout()

        # Load GeoJSON from AMRUT file
        geojson_layer = self.load_geojson_from_amrut(self.amrut_file_path, self.selected_layer_name)

        if geojson_layer:
            # Check if a layer with the prefix 'Temporary_' already exists in the project
            temporary_layer_name = f"Temporary_{self.selected_layer_name}"
            existing_layer = self.get_layer_by_name(temporary_layer_name)

            if existing_layer:
                # If a temporary layer with the same name exists, remove it
                QgsProject.instance().removeMapLayer(existing_layer.id())

            # Rename and add the GeoJSON layer with the prefix 'Temporary_'
            geojson_layer.setName(temporary_layer_name)
            QgsProject.instance().addMapLayer(geojson_layer)

            # Create and return the visualization panel
            panel_layout = self.create_layer_visualization_panel(geojson_layer, f"Visualization of {temporary_layer_name}", raster_layer)
            return panel_layout
        else:
            # If GeoJSON layer is not found, show an error message
            panel_layout.addWidget(QLabel("GeoJSON layer not found in AMRUT file."))

        return panel_layout

    def load_geojson_from_amrut(self, amrut_file_path, layer_name):
        """Extract and load the GeoJSON file from the AMRUT archive."""
        try:
            # Open the AMRUT file (which is a zip)
            with zipfile.ZipFile(amrut_file_path, 'r') as zip_ref:
                geojson_filename = f"{layer_name}.geojson"

                if geojson_filename in zip_ref.namelist():
                    # Extract the GeoJSON content
                    geojson_content = zip_ref.read(geojson_filename).decode('utf-8')

                    # Check if a temporary file with the prefix exists
                    temp_dir = tempfile.gettempdir()
                    temp_geojson_file_path = os.path.join(temp_dir, f"Temporary_{geojson_filename}")

                    # Save the GeoJSON content to the temporary file
                    with open(temp_geojson_file_path, 'w', encoding='utf-8') as temp_geojson_file:
                        temp_geojson_file.write(geojson_content)

                    # Load the GeoJSON into a vector layer using the temporary file path
                    geojson_layer = QgsVectorLayer(temp_geojson_file_path, layer_name, "ogr")

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

    def create_layer_visualization_panel(self, layer, title, raster_layer):
        """Create a panel to visualize a specific project layer."""
        panel_layout = QVBoxLayout()
        map_canvas = self.create_map_canvas(layer, raster_layer)
        panel_layout.addWidget(map_canvas)

        label = QLabel(title)
        label.setAlignment(Qt.AlignCenter)
        panel_layout.addWidget(label)

        return panel_layout

    def create_map_canvas(self, layer, raster_layer):
        """Create a map canvas to render the given layer."""
        canvas = QgsMapCanvas()
        print(layer.crs())
        canvas.setLayers([raster_layer, layer])
        print(self.grid_extent)
        canvas.setExtent(self.grid_extent)
        canvas.setCanvasColor(Qt.white)
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

    def create_placeholder_panel(self, title, message):
        """Create a placeholder panel with a title and message."""
        panel_layout = QVBoxLayout()
        label = QLabel(title)
        label.setAlignment(Qt.AlignCenter)
        panel_layout.addWidget(label)

        placeholder = QLabel(message)
        placeholder.setAlignment(Qt.AlignCenter)
        panel_layout.addWidget(placeholder)

        return panel_layout

    def add_vertical_divider(self, layout):
        """Add a vertical divider to the layout."""
        line = QLabel()
        line.setFixedWidth(1)
        line.setStyleSheet("background-color: black;")
        layout.addWidget(line)
