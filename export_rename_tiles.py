import os
import math

def flip_y_coordinate(zoom, y):
    """Flip the Y-coordinate for TMS compatibility."""
    max_tiles = 2 ** zoom  # Total number of tiles at this zoom level
    return max_tiles - 1 - y

def rename_tiles(base_dir):
    """Rename tiles in the specified base directory to flip Y-coordinates."""
    for zoom_level in os.listdir(base_dir):
        zoom_path = os.path.join(base_dir, zoom_level)
        if not os.path.isdir(zoom_path):
            continue

        for x_folder in os.listdir(zoom_path):
            x_path = os.path.join(zoom_path, x_folder)
            if not os.path.isdir(x_path):
                continue

            for tile in os.listdir(x_path):
                if not tile.endswith(".png"):
                    continue

                # Parse the original Y-coordinate
                original_y = int(tile.split(".")[0])  # Assuming filenames are like 'y.png'
                zoom = int(zoom_level)  # Current zoom level

                # Compute the flipped Y-coordinate
                flipped_y = flip_y_coordinate(zoom, original_y)

                # Rename the file
                original_path = os.path.join(x_path, tile)
                new_tile_name = f"{flipped_y}.png"
                new_path = os.path.join(x_path, new_tile_name)

                # Rename the file
                os.rename(original_path, new_path)
                print(f"Renamed: {original_path} -> {new_path}")

if __name__ == "__main__":
    # Base directory containing the tiles
    tiles_base_dir = "/path/to/tiles_output_dir"
    rename_tiles(tiles_base_dir)
