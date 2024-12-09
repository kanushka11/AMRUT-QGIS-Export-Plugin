from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, QVariant,Qt
from qgis.PyQt.QtGui import QIcon, QFont
from qgis.PyQt.QtWidgets import QAction, QFileDialog, QMessageBox, QProgressDialog, QDialog,QVBoxLayout,QPushButton,QLabel
from . import main_dialog
from qgis.core import QgsApplication,  QgsMessageLog, Qgis


import processing
import os

# Initialize Qt resources from file resources.py
from .resources import *
# Import the code for the dialog
from .export_dialog import ClipMergeExportDialog

# Initialize Qt resources from file resources.py
from .resources import *
# Import the code for the dialog
from .export_dialog import ClipMergeExportDialog
import os.path
class AMRUT:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'AMRUT_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&AMRUT')

        # Check if plugin was started the first time in current QGIS session
        # Must be set in initGui() to survive plugin reloads
        self.first_start = None

    def tr(self, message):
        """Get the translation for a string using Qt translation API."""
        return QCoreApplication.translate('AMRUT', message)

    def add_action(self, icon_path, text, callback, enabled_flag=True, add_to_menu=True, add_to_toolbar=True, status_tip=None, whats_this=None, parent=None):
        """Add a toolbar icon to the toolbar."""
        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.iface.addToolBarIcon(action)

        if add_to_menu:
            self.iface.addPluginToMenu(self.menu, action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""
        icon_path = ':/plugins/export/icon.png'
        self.add_action(icon_path, text=self.tr(u'AMRUT'), callback=self.run, parent=self.iface.mainWindow())

        # will be set False in run()
        self.first_start = True

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(self.tr(u'&AMRUT'), action)
            self.iface.removeToolBarIcon(action)

    def run(self):
        try :
            self.required_algorithms = ["qgis:clip", 'gdal:cliprasterbymasklayer', 'gdal:gdal2tiles', 'gdal:warpreproject']
            self.prerequisits_avalaible = True
            for algorithm in self.required_algorithms :
                if not self.is_algorithm_available(algorithm) :
                    self.prerequisits_avalaible = False

            if(self.prerequisits_avalaible) :
                mainDialog = main_dialog.ClipMergeExportTabDialog(self.iface)
                mainDialog.exec_()
            else :
                error_msg = f"""Please make sure the following Algorithms are available from processing : {self.required_algorithms}"""
                self.show_error(error_msg)
        except Exception as e :
            raise  Exception(str(e))

    def is_algorithm_available(self, algorithm_id):
        """Check if a processing algorithm is available."""
        return QgsApplication.processingRegistry().algorithmById(algorithm_id) is not None

    def show_error (self, error):
        error_dialog = QDialog(self.iface.mainWindow())
        error_dialog.setWindowTitle("Error")
        error_dialog.setModal(True)
        error_dialog.setMinimumWidth(400)

        # Layout for the dialog
        layout = QVBoxLayout()

        # Label for displaying the error message
        error_label = QLabel(str(error))
        error_label.setWordWrap(True)  # Wrap long error messages
        layout.addWidget(error_label)

        # OK button to close the dialog
        ok_button = QPushButton("OK")
        ok_button.clicked.connect(error_dialog.accept)  # Closes the dialog
        layout.addWidget(ok_button)

        error_dialog.setLayout(layout)
        error_dialog.exec_()  # Show the dialog modally

        # Log the error in the QGIS message log
        QgsMessageLog.logMessage(str(error), 'AMRUT', Qgis.Critical)







