from qgis.core import QgsMessageLog, Qgis
from qgis.core import QgsVectorLayer
from PyQt5.QtCore import QRunnable, QThreadPool, pyqtSignal, QObject, QThread
from . import import_validation as validation
from . import import_construct_layer as construction
from . import import_process_layer as process
from qgis.core import (
    QgsProcessingFeedback, QgsProcessingContext, QgsRasterLayer
)
import processing

class AmrutFilesValidationWorker(QObject) :
    result_signal = pyqtSignal(bool, object)  # Signal to send results back
    finished = pyqtSignal()

    def __init__(self, data_dir):
        super().__init__()
        self.dir = data_dir

    def run(self):
        try :
            validation_result = validation.validate_amrut_files(self.dir)
            print(f" Validation Result : {validation_result}")
            if validation_result[0] :
                self.result_signal.emit(True, validation_result[1])
            else :
                self.result_signal.emit(False, validation_result[1])
            self.finished.emit()
        except Exception as e :
            self.result_signal.emit(False, str(e))
            self.finished.emit()


class LayerConstructionWorker (QObject) :
    result_signal = pyqtSignal(bool, str)
    finished = pyqtSignal()

    def __init__(self, directory,amrut_files,layer_name) :
        super().__init__()
        self.amrut_files = amrut_files
        self.layer_name = layer_name
        self.directory = directory
    def run(self):
        try :
            layer_construction_result = construction.construct_layer(self.directory,self.amrut_files, self.layer_name)
            print(f"Layer Reconstruction_result : {layer_construction_result}")
            if layer_construction_result[0] :
                self.result_signal.emit(True, layer_construction_result[1])
            else :
                self.result_signal.emit(False, layer_construction_result[1])
            self.finished.emit()
        except Exception as e :
            self.result_signal.emit(False, str(e))
            self.finished.emit()

class CompareChangesWorker(QObject):
    result_signal = pyqtSignal(bool, object)
    finished = pyqtSignal()

    def __init__(self, layer_name):
        super().__init__()
        self.layer_name = layer_name

    def run(self):
        try:
            compare_changes_result = process.process_temp_layer(self.layer_name)
            self.result_signal.emit(True, compare_changes_result)
        except Exception as e:
            self.result_signal.emit(False, str(e))
        finally:
            self.finished.emit()

class RasterTransformWorker(QObject):
    progress_signal = pyqtSignal(int)  # Emit progress percentage
    finished_signal = pyqtSignal(object)  # Emit when transformation is done

    def __init__(self, layer, raster_layer):
        super().__init__()
        self.layer = layer
        self.raster_layer = raster_layer

    def run(self):
        """ Perform raster transformation and emit progress updates """
        try:
            processing_context = QgsProcessingContext()
            feedback = QgsProcessingFeedback()

            # Define parameters for transformation
            reproject_params = {
                'INPUT': self.raster_layer.source(),
                'SOURCE_CRS': self.raster_layer.crs().authid(),
                'TARGET_CRS': self.layer.crs().authid(),
                'RESAMPLING': 0,
                'NODATA': 0,
                'OUTPUT': 'TEMPORARY_OUTPUT'
            }

            # Simulate progress update (since processing.run is blocking)
            for progress in range(0, 101, 20):  # Simulated steps
                self.progress_signal.emit(progress)
                QThread.msleep(500)  # Simulate work being done

            # Run the transformation
            transform_result = processing.run("gdal:warpreproject", reproject_params, context=processing_context, feedback=feedback)

            # Create and validate the transformed raster layer
            reprojected_raster = QgsRasterLayer(transform_result['OUTPUT'], f"Temporary_{self.raster_layer.name()}")
            if not reprojected_raster.isValid():
                raise ValueError("Raster transformation failed.")

            # Emit success signal with the reprojected raster layer
            self.progress_signal.emit(100)
            self.finished_signal.emit(reprojected_raster)

        except Exception as e:
            print(f"Raster Transformation Error: {e}")
            self.finished_signal.emit(None)








