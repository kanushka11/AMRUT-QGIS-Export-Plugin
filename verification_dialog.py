from PyQt5.QtWidgets import QDialog, QHBoxLayout, QVBoxLayout, QLabel, QPushButton
from PyQt5.QtCore import Qt
from qgis.core import QgsProject
from qgis.gui import QgsMapCanvas, QgsMapToolPan


def get_layer_by_name(layer_name):
        """Retrieve a layer from the QGIS project by its name."""
        for layer in QgsProject.instance().mapLayers().values():
            if layer.name() == layer_name:
                return layer
        return None

class IntroDialog(QDialog):
    def __init__(self, parent, selected_layer_name, selected_raster_layer_name, grid_extent):
        super().__init__(parent)
        self.selected_layer_name = selected_layer_name
        self.selected_layer = get_layer_by_name(selected_layer_name)
        self.selected_raster_layer_name =selected_raster_layer_name
        self.temporary_layer_name = f"Temporary_{selected_layer_name}"
        self.temporary_layer = get_layer_by_name(self.temporary_layer_name)
        self.grid_extent = grid_extent

        if self.selected_layer and self.temporary_layer:
            selected_feature_ids = {f['feature_id'] for f in self.selected_layer.getFeatures()}
            self.new_feature_ids = set()

            for feature in self.temporary_layer.getFeatures():
                temp_feature_id = feature['feature_id']
                if temp_feature_id not in selected_feature_ids:
                    self.new_feature_ids.add(temp_feature_id)

            if self.new_feature_ids:
                self.show_new_features_dialog()

    def show_new_features_dialog(self):
        """Show dialog box asking user to proceed to verify new features."""
        feature_count = len(self.new_feature_ids)
        message = f"{feature_count} new features found in the temporary layer."

        dialog = QDialog(None)
        dialog.setWindowTitle("Feature Verification")
        dialog.setMinimumSize(300, 150)

        layout = QVBoxLayout(dialog)
        message_label = QLabel(message)
        message_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(message_label)
        
        if feature_count > 0:
            button_layout = QHBoxLayout()
            proceed_button = QPushButton("Proceed to Verify")
            button_layout.addWidget(proceed_button, alignment=Qt.AlignCenter)
            proceed_button.setFixedWidth(150)
            layout.addLayout(button_layout)

            proceed_button.clicked.connect(lambda: self.proceed_to_verify(dialog))
        dialog.exec_()

    def proceed_to_verify(self,dialog):
        """Close this dialog and open the verification dialog."""
        # Close the intro dialog
        dialog.close()

        qualityCheckVisualizationDialog = VerificationDialog(
            parent=self.parent(),  # Use the main window or the correct parent dialog
            selected_layer_name=self.selected_layer_name,
            selected_raster_layer_name=self.selected_raster_layer_name,
            grid_extent=self.grid_extent,
        )
        qualityCheckVisualizationDialog.exec_()

class VerificationDialog(QDialog):
    def __init__(self, parent, selected_layer_name, selected_raster_layer_name, grid_extent):
        super().__init__(parent)
        self.selected_layer_name = selected_layer_name
        self.selected_raster_layer_name =f"Temporary_{selected_raster_layer_name}" 
        self.temporary_layer_name = f"Temporary_{self.selected_layer_name}"
    
        self.grid_extent = grid_extent
        self.setWindowTitle("Quality Check Visualization")

        # Main layout
        layout = QHBoxLayout(self)

        # Left panel: Visualization of selected project layer
        layer = get_layer_by_name(self.selected_layer_name)
        raster_layer = get_layer_by_name(self.selected_raster_layer_name)
        amrut_layer = get_layer_by_name(self.temporary_layer_name)

        if layer:
            left_panel = self.create_layer_visualization_panel(layer, "Selected Layer Visualization", raster_layer)
        else:
            left_panel = self.create_error_panel(f"Layer '{self.selected_layer_name}' not found.")
        layout.addLayout(left_panel)

        # Add a vertical divider
        self.add_vertical_divider(layout)

        # Right panel: Visualization of GeoJSON from AMRUT file
        right_panel = self.create_layer_visualization_panel(amrut_layer, "Selected Layer Visualization", raster_layer)
        layout.addLayout(right_panel)


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
        canvas.setLayers([layer, raster_layer])
        print(self.grid_extent)
        canvas.setExtent(self.grid_extent)
        canvas.setCanvasColor(Qt.white)
        canvas.setMapTool(QgsMapToolPan(canvas))  # Enable panning
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
