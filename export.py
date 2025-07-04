from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, QVariant,Qt
from qgis.PyQt.QtGui import QIcon, QFont
from qgis.PyQt.QtWidgets import QAction, QFileDialog, QMessageBox, QProgressDialog, QDialog,QVBoxLayout,QPushButton,QLabel
from . import main_dialog
from qgis.core import QgsApplication,  QgsMessageLog, Qgis,   QgsProject,  QgsVectorLayer, QgsRasterLayer
from . import open_dialog
from . import import_dialog

import processing
import os
from. import export_ui as ui

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
            'Sankalan_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&Sankalan2.0')

        # Check if plugin was started the first time in current QGIS session
        # Must be set in initGui() to survive plugin reloads
        self.first_start = None

    def tr(self, message):
        """Get the translation for a string using Qt translation API."""
        return QCoreApplication.translate('Sankalan2.0', message)

    def add_action(self, text, callback, enabled_flag=True, add_to_menu=True, add_to_toolbar=True, status_tip=None, whats_this=None, parent=None):
        """Add a toolbar icon to the toolbar."""
        icon = ui.get_icon()
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
        self.add_action( text=self.tr(u'Sanakalan 2.0'), callback=self.run, parent=self.iface.mainWindow())

        # will be set False in run()
        self.first_start = True

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(self.tr(u'&Sankalan2.0'), action)
            self.iface.removeToolBarIcon(action)
    
    def run(self):
        try:
            # Step 1: Ask if the user wants to use the plugin
            pluginUsageDialog = open_dialog.OpenPluginDialog(self.iface)
            
            if pluginUsageDialog.exec_() == QDialog.Accepted:
                action = pluginUsageDialog.get_action()  # Get the selected action
                
                if action == 'export':
                    self.handle_export()
                elif action == 'import':
                    self.handle_import()
                else:
                    return

        except Exception as e:
            self.show_error(f"An error occurred: {str(e)}")


    def handle_export(self):
        if not self.is_project_saved():
            self.show_error("Please save the QGIS project before proceeding.")
            return

        if self.is_any_layer_in_editing_mode():
            self.show_error("Please ensure no layers are in editing mode before proceeding.")
            return

        self.required_algorithms = ["qgis:clip", 'gdal:cliprasterbymasklayer', 'gdal:gdal2tiles', 'gdal:warpreproject', 'gdal:warpreproject', 'gdal:cliprasterbyextent', 'native:dissolve']
        prerequisites_available = True

        for algorithm in self.required_algorithms:
            if not self.is_algorithm_available(algorithm):
                prerequisites_available = False

        if prerequisites_available:
            # Pass the open_dialog reference to ClipMergeExportTabDialog
            mainDialog = main_dialog.ClipMergeExportTabDialog(self.iface)
            mainDialog.exec_()  # Use exec_() to show the dialog and block until it finishes
        else:
            error_msg = f"""Please make sure the following Algorithms are available from Core Plugin Processing: {self.required_algorithms}"""
            self.show_error(error_msg)


    def handle_import(self):
        # Check if there is a valid project loaded
        project = QgsProject.instance()
        
        if not project.isDirty() and project.fileName() == '':
            self.show_error("No project is currently loaded. Please load a project first.")
            return
        
        if not self.is_project_saved():
            self.show_error("Please save the QGIS project before proceeding.")
            return

        if self.is_any_layer_in_editing_mode():
            self.show_error("Please ensure no layers are in editing mode before proceeding.")
            return

        # Create and show the Import_Dialog
        importDialog = import_dialog.ImportDialog(self.iface)  # Pass the parent if necessary
        importDialog.reconstruct_or_qc_dialog()


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
        QgsMessageLog.logMessage(str(error), 'Sankalan2.0', Qgis.Critical)

    def is_project_saved(self):
        """Check if the QGIS project is saved."""
        project = QgsProject.instance()
        return not project.isDirty()  # isDirty() returns True if the project has unsaved changes

    def is_any_layer_in_editing_mode(self):
        """Check if any layer in the project is in editing mode."""
        layers = QgsProject.instance().mapLayers().values()
        for layer in layers:
            # Check for vector layer editing mode
            if isinstance(layer, QgsVectorLayer) and layer.isEditable():
                return True
            # Check for raster layer editing mode (if applicable)
            if isinstance(layer, QgsRasterLayer):
                provider = layer.dataProvider()
                if provider.isEditable():  # Check if raster layer's data provider allows editing
                    return True
        return False
