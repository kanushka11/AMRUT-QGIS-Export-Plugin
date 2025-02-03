from qgis.core import QgsMessageLog, Qgis
from qgis.core import QgsVectorLayer
from PyQt5.QtCore import QRunnable, QThreadPool, pyqtSignal, QObject
from . import import_validation as validation

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






