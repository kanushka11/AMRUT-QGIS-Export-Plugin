from qgis.core import QgsMessageLog, Qgis
from qgis.core import QgsVectorLayer
from PyQt5.QtCore import QRunnable, QThreadPool, pyqtSignal, QObject
from . import import_validation as validation
from . import import_construct_layer as construction
from . import import_process_layer as process

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
            self.finished.emmit()
        except Exception as e :
            self.result_signal.emmit(False, str(e))
            self.finished.emmit()


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









