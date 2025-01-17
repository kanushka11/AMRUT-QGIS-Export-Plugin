from PyQt5.QtWidgets import QDialog, QVBoxLayout, QPushButton, QLabel, QHBoxLayout
from PyQt5.QtCore import Qt
from qgis.core import QgsProject


class NewFeatureFoundDialog:
    def __init__(self, selected_layer_name):
        self.selected_layer_name = selected_layer_name
        self.selected_layer = self.get_layer_by_name(selected_layer_name)
        self.temporary_layer_name = f"Temporary_{selected_layer_name}"
        self.temporary_layer = self.get_layer_by_name(self.temporary_layer_name)

    def check_for_new_features(self):
        """Compare the feature_id attribute of both layers and prompt the user if new features are found."""
        if self.selected_layer and self.temporary_layer:
            # Store all feature_id values from the selected layer
            selected_feature_ids = {f['feature_id'] for f in self.selected_layer.getFeatures()}
            self.new_feature_ids = set()

            # Traverse feature_id of the temporary layer and find new ones
            for feature in self.temporary_layer.getFeatures():
                temp_feature_id = feature['feature_id']
                if temp_feature_id not in selected_feature_ids:
                    self.new_feature_ids.add(temp_feature_id)

            # If new feature IDs are found, prompt the user
            if self.new_feature_ids:
                self.show_new_features_dialog(self.new_feature_ids)

    def show_new_features_dialog(self, new_features):
        """Show dialog box asking user to proceed to verify new features."""
        feature_count = len(self.new_feature_ids)
        message = f"{feature_count} new features found in the temporary layer."

        # Create a custom dialog
        dialog = QDialog(None)
        dialog.setWindowTitle("New Features Found")
        
        # Set minimum size for dialog
        dialog.setMinimumSize(300, 150)  # Width: 400px, Height: 200px

        # Set up layout
        layout = QVBoxLayout(dialog)
        
        # Add message label
        message_label = QLabel(message)
        message_label.setAlignment(Qt.AlignCenter) 
        layout.addWidget(message_label)
        
        # Add Proceed to Verify button
        button_layout = QHBoxLayout()
        proceed_button = QPushButton("Proceed to Verify")
        button_layout.addWidget(proceed_button, alignment=Qt.AlignCenter)
        
        # Set button width
        proceed_button.setFixedWidth(150)  # Set a fixed width for the button
        layout.addLayout(button_layout)
        
        # Set dialog's buttons to respond to user action
        proceed_button.clicked.connect(self.save_selected_layer_names)
        
        # Show dialog
        dialog.exec_()

    def save_selected_layer_names(self):
        """Dummy implementation of save_selected_layer_names."""
        # For now, let's just print a message to indicate this function was called
        print("Selected layer names have been saved.")

    def get_layer_by_name(self, layer_name):
        """Retrieve a layer from the QGIS project by its name."""
        for layer in QgsProject.instance().mapLayers().values():
            if layer.name() == layer_name:
                return layer
        return None
