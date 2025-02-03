import os
import zipfile
import json

def get_amrut_files(directory):
    """Returns a list of all files in the directory ending with .amrut extension."""
    if not os.path.isdir(directory):
        print("Invalid directory path")
        return []
    print(f"f Path : {directory}")
    return [f for f in os.listdir(directory) if f.endswith(".amrut")]

def validate_amrut_files(directory):
    """Returns a Pair of <Boolean and Message/Data>"""
    amrut_files = get_amrut_files(directory)
    print(f"f Files : {amrut_files}")

    if len(amrut_files) == 0:
        return False, "No valid AMRUT files found"

    layer_map = {}

    for amrut_file in amrut_files:
        amrut_path = os.path.join(directory, amrut_file)
        print(f"f Reading File : {amrut_path}")
        # Open the .amrut file as a ZIP archive
        with zipfile.ZipFile(amrut_path, 'r') as zip_ref:
            # Check if metadata.json exists in the archive
            if "metadata.json" not in zip_ref.namelist():
                return False, f"metadata.json not found in {amrut_file}"

            # Read metadata.json
            with zip_ref.open("metadata.json") as metadata_file:
                metadata = json.load(metadata_file)

                # Check qc_status
                if metadata.get("qc_status") != "verified":
                    return False, f"{amrut_file} is not verified"

                # Read layers and extract layer names
                layers = metadata.get("layers", [])
                for layer in layers:
                    layer_name = next(iter(layer))  # Extracting layer_name
                    layer_map[layer_name] = layer[layer_name]  # Storing geometry info

    return True, (amrut_files, layer_map)  # Successfully validated, return layer map
