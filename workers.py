from PyQt5.QtCore import QRunnable, QThreadPool, pyqtSignal, QObject
from . import geometry, clip, grid
from qgis.core import QgsMessageLog, Qgis
from qgis.core import QgsVectorLayer

class LayerValidationWorker(QObject):
    """Worker to validate geometries and extents in a background thread."""

    result_signal = pyqtSignal(bool, str)  # Signal to send results back
    finished = pyqtSignal()
    def __init__(self, layers):
        super().__init__()
        self.layers = layers

    def run(self):
        """Run validation in the background."""
        try:
            # Example: Validate layers (replace with your own validation code)
            QgsMessageLog.logMessage('Validation started.', 'AMRUT_Export', Qgis.Info)  # Check if the task is started
            valid = geometry.check_geometries_and_extents(self.layers)
            QgsMessageLog.logMessage('Validation Completed.', 'AMRUT_Export', Qgis.Info)  # Check result
            self.result_signal.emit(valid, "") 
            self.finished.emit() # Emit result back to the main thread
        except Exception as e:
            print(f"Error during validation: {e}")
            self.result_signal.emit(False, str(e))
            self.finished.emit() # Emit error message

class GridLayerValidationWorker(QObject):
    """Worker to validate geometries and extents in a background thread."""

    result_signal = pyqtSignal(bool, str)  # Signal to send results back
    finished = pyqtSignal()
    def __init__(self, layer):
        super().__init__()
        self.layer = layer

    def run(self):
        """Run validation in the background."""
        try:
            # Example: Validate layers (replace with your own validation code)
            QgsMessageLog.logMessage('Validation started.', 'AMRUT_Export', Qgis.Info)  # Check if the task is started
            valid = geometry.check_polygon_in_a_layer(self.layer)
            QgsMessageLog.logMessage('Validation Completed.', 'AMRUT_Export', Qgis.Info)  # Check result
            self.result_signal.emit(valid, "") 
            self.finished.emit() # Emit result back to the main thread
        except Exception as e:
            QgsMessageLog.logMessage('Validation error : ' + str(e), 'AMRUT_Export', Qgis.Critical)
            self.result_signal.emit(False, str(e))
            self.finished.emit() # Emit error message

class GridLayerCeationWorker(QObject):

    layer_signal = pyqtSignal(str)  # Signal to send results back
    error_signal = pyqtSignal(str)
    finished = pyqtSignal()
    
    def __init__(self, selectedLayers,layer, size):
        super().__init__()
        self.layer = layer
        self.size = size
        self.selectedLayers = selectedLayers

    def run(self):
        try:
            # Example: Validate layers (replace with your own validation code)
            QgsMessageLog.logMessage('Creating Grid Layer', 'AMRUT_Export', Qgis.Info)  # Check if the task is started
            layer_id = grid.create_grid_within_single_polygon(self.selectedLayers,self.layer,self.size, self.layer.crs().authid())
            self.layer_signal.emit(layer_id) 
            self.finished.emit() # Emit result back to the main thread
        except Exception as e:
            print(f"Error during validation: {e}")
            self.error_signal.emit(str(e))
            self.finished.emit() # Emit error message

class ClippingWorker(QObject):

    success_signal = pyqtSignal(bool)  # Signal to send results back
    error_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    finished = pyqtSignal()
    
    def __init__(self, gridLayer, selectedLayers, output_dir):
        super().__init__()
        self.gridLayer = gridLayer
        self.selectedLayers = selectedLayers
        self.output_dir = output_dir

    def run(self):
        try:
            # Example: Validate layers (replace with your own validation code)
            QgsMessageLog.logMessage('Creating Grid Layer', 'AMRUT_Export', Qgis.Info)  # Check if the task is started
            clip.clip_layers_to_grid(grid_layer= self.gridLayer, layers= self.selectedLayers, progress_signal= self.progress_signal, output_base_dir=self.output_dir)
            self.success_signal.emit(True) 
            self.finished.emit() # Emit result back to the main thread
        except Exception as e:
            print(f"Error during validation: {e}")
            self.error_signal.emit(str(e))
            self.finished.emit() # Emit error message

