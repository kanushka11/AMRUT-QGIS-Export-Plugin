# Centralized error messages dictionary
ERROR_MESSAGES = {
    # Geometry and Layer Errors
    'INVALID_GEOMETRY': "Invalid geometry detected in grid cell {grid_cell_id}. Skipping due to invalid geometry.",
    'NO_FEATURE_FOUND': "No feature found in the layer.",
    'EMPTY_GEOMETRY': "Geometry is empty.",
    'NO_OVERLAPPING_EXTENTS': "No overlapping extents found among layers.",
    'INVALID_GEOMETRIES_DETECTED': "Invalid geometries detected:\n{details}",
    'FEATURE_NOT_FOUND_IN_LAYER': "Feature with feature_id {feature_id} not found in the .amrut file.",
    'BUFFER_CALCULATION_ERROR': "Error calculating dynamic buffer: {error}",
    
    # Grid Creation Errors
    'INVALID_POLYGON_LAYER': "Invalid polygon layer provided.",
    'SINGLE_POLYGON_REQUIRED': "Layer must contain exactly one polygon feature.",
    'EMPTY_POLYGON_GEOMETRY': "Polygon geometry is empty or invalid.",
    'LAYER_EXTENT_ERROR': "Selected Layer(s) extent is greater than that of AOI/ROI Layer.",
    'GRID_CREATION_ERROR': "Error during grid creation: {error}",
    'GRID_VALIDATION_ERROR': "Grid validation failed:\n{details}",
    'LAYER_TYPE_ERROR': "grid_layer must be a QgsVectorLayer.",
    'FILE_SAVE_ERROR': "Error saving file to disk: {error}",
    'DIRECTORY_CREATION_ERROR': "Error creating directory: {error}",
    
    # Processing Errors
    'VECTOR_CLIP_ERROR': "Error clipping vector layer '{layer_name}' with grid cell {grid_cell_id}: {error}",
    'RASTER_CLIP_ERROR': "Error clipping raster layer '{layer_name}' with grid cell {grid_cell_id}: {error}",
    'MERGE_LAYERS_ERROR': "Error merging {geometry_type} layers: {error}",
    'ARCHIVE_CREATION_ERROR': "Error creating .amrut archive for grid: {error}",
    'FILE_DELETION_ERROR': "Error deleting {file_path}: {error}",
    'CLIPPING_ERROR': "Error during clipping operation: {error}",
    
    # Plugin and Project Errors
    'PLUGIN_INITIALIZATION_ERROR': "Plugin initialization error: {error}",
    'PROJECT_NOT_SAVED_ERROR': "Please save the QGIS project before proceeding.",
    'LAYERS_IN_EDITING_MODE_ERROR': "Please ensure no layers are in editing mode before proceeding.",
    'NO_PROJECT_LOADED_ERROR': "No project is currently loaded. Please load a project first.",
    'ALGORITHM_NOT_AVAILABLE_ERROR': "Please make sure the following Algorithms are available from Core Plugin Processing: {algorithms}",
    'EXPORT_HANDLER_ERROR': "Error in export handler: {error}",
    'IMPORT_HANDLER_ERROR': "Error in import handler: {error}",
    'ALGORITHM_CHECK_ERROR': "Error checking algorithm '{algorithm}': {error}",
    'ERROR_DISPLAY_FAILED': "Failed to display error dialog. Original error: {original_error}, Display error: {display_error}",
    'PROJECT_STATUS_CHECK_ERROR': "Error checking project save status: {error}",
    'LAYER_EDITING_CHECK_ERROR': "Error checking layer editing status: {error}",
    
    # Import Dialog Specific Errors
    'DIALOG_OPEN_ERROR': "Error opening dialog: {error}",
    'INVALID_FILE_EXTENSION': "Please select a valid .amrut file.",
    'FILE_BROWSE_ERROR': "Error browsing file: {error}",
    'MISSING_METADATA_FILE': "The .amrut file does not contain 'metadata.json'.",
    'INVALID_METADATA_FORMAT': "Failed to parse metadata.json.",
    'FILE_ALREADY_VERIFIED': "All layers of this file have been verified.",
    'FILE_MARKED_FOR_RESURVEY': "File has already been marked for Re-Survey.",
    'INVALID_LAYERS_ARRAY': "'layers' array is missing or invalid in metadata.json.",
    'MISSING_LAYERS_IN_PROJECT': "The following layers are missing in the project: {layers}",
    'NO_LAYER_SELECTED': "Please select a valid layer for quality check.",
    'RASTER_LAYER_NOT_FOUND': "The selected raster layer could not be found.",
    'EXTENT_VALIDATION_FAILED': "The grid's extent does not fall within the raster layer's extent.",
    'ALL_LAYERS_VERIFIED': "All layers of this file have been verified.",
    'AMRUT_FILE_VALIDATION_ERROR': "Error validating .amrut file: {error}",
    'QUALITY_CHECK_PROCEED_ERROR': "Error proceeding with quality check: {error}",
    'TEMP_DIR_CLEANUP_ERROR': "Error cleaning up temporary directory: {error}",
    'METADATA_UPDATE_ERROR': "Error updating metadata file: {error}",
    'FILE_EXTRACTION_ERROR': "Error extracting .amrut file: {error}",
    'FILE_NOT_FOUND_ERROR': "The selected .amrut file or its resurvey version could not be found.",
    'QUALITY_CHECK_DIALOG_ERROR': "Error in quality check dialog: {error}",
    
    # Import Reconstruct Dialog Specific Errors
    'NO_DIRECTORY_SELECTED': "No directory selected. Please select a data directory before proceeding.",
    'LAYER_RETRIEVAL_ERROR': "Error retrieving layer '{layer_name}': {error}",
    'THREAD_CLEANUP_ERROR': "Error during thread cleanup: {error}",
    'LAYER_FILTER_CLEAR_ERROR': "Error clearing layer filter: {error}",
    'PROJECT_WRITE_ERROR': "Error writing project: {error}",
    'DIALOG_CLOSE_ERROR': "Error closing dialog: {error}",
    'TEMP_LAYER_PROCESSING_ERROR': "Error processing temporary layer '{layer_name}': {error}",
    'LAYER_CONSTRUCTION_WORKER_ERROR': "Error in layer construction worker: {error}",
    'COMPARE_CHANGES_ERROR': "Error comparing changes: {error}",
    'LAYER_RENAMING_ERROR': "Error renaming layer: {error}",
    'RASTER_LAYER_FETCH_ERROR': "Error fetching raster layers: {error}",
    'LAYER_STATUS_CHECK_ERROR': "Error checking layer status: {error}",
    'TEMPORARY_LAYER_CHECK_ERROR': "Error checking temporary layer status: {error}",
    
    # Canvas and UI Specific Errors
    'CANVAS_FRAME_CREATION_ERROR': "Error creating canvas frame: {error}",
    'LAYER_OPACITY_ERROR': "Error setting opacity for layer '{layer_name}': {error}",
    'CANVAS_SYNCHRONIZATION_ERROR': "Error synchronizing {canvas} canvas: {error}",
    'PAN_TOOL_SETUP_ERROR': "Error setting up panning tools: {error}",
    'CANVAS_UPDATE_ERROR': "Error updating canvases: {error}",
    'CANVAS_ZOOM_ERROR': "Error zooming to feature {feature_id}: {error}",
    
    # Generic Errors
    'PROCESSING_ERROR': "Processing error occurred: {error}",
    'FILE_ACCESS_ERROR': "File access error: {error}",
    'VALIDATION_ERROR': "Validation error:\n{details}",
    'UNKNOWN_ERROR': "An unknown error occurred: {error}",
    'LAYER_UPDATE_ERROR': "Error updating feature attributes in layer: {error}",
    'LAYER_MERGE_ERROR': "Error merging features in layer: {error}",
    'LAYER_RENAME_ERROR': "Error renaming layer: {error}",
    'REMOVE_LAYER_ERROR': "Error removing layer '{layer_name}': {error}",
    'LAYER_CONSTRUCTION_ERROR': "Error during layer construction: {error}",
    'LAYER_COMPARISON_ERROR': "Error during layer comparison: {error}",
    'RASTER_TRANSFORM_ERROR': "Error transforming raster layer: {error}"
}

# Error titles for message boxes
ERROR_TITLES = {
    'GEOMETRY_ERROR': "Geometry Error",
    'GRID_ERROR': "Grid Creation Error",
    'VALIDATION_ERROR': "Validation Error",
    'PROCESSING_ERROR': "Processing Error", 
    'FILE_ERROR': "File Error",
    'ARCHIVE_ERROR': "Archive Error",
    'IMPORT_ERROR': "Import Error",
    'DIALOG_ERROR': "Dialog Error",
    'METADATA_ERROR': "Metadata Error",
    'LAYER_ERROR': "Layer Error",
    'THREAD_ERROR': "Thread Error",
    'PROJECT_ERROR': "Project Error",
    'CANVAS_ERROR': "Canvas Error",
    'UI_ERROR': "User Interface Error",
    'GENERAL_ERROR': "Error"
}

def get_error_message(error_key, **kwargs):
    """
    Get formatted error message from the centralized dictionary.
    
    Args:
        error_key (str): Key to identify the error message
        **kwargs: Format parameters for the error message
    
    Returns:
        str: Formatted error message
    """
    if error_key in ERROR_MESSAGES:
        return ERROR_MESSAGES[error_key].format(**kwargs)
    return ERROR_MESSAGES['UNKNOWN_ERROR'].format(error=f"Unknown error key: {error_key}")

def get_error_title(title_key):
    """
    Get error title for message boxes.
    
    Args:
        title_key (str): Key to identify the error title
    
    Returns:
        str: Error title
    """
    return ERROR_TITLES.get(title_key, ERROR_TITLES['GENERAL_ERROR'])