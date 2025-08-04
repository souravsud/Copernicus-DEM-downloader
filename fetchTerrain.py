from cdse_copernicus_dem_downloader.cdse_copernicus_dem_downloader import main as dem_downloader
from post_process.MergeAndCrop import merge_and_clip_dem
from post_process.rotate_Crop import reproject_and_crop_to_utm_rotated
import sys
import mgrs

def find_tile_from_coordinates(lat, lon):
    m = mgrs.MGRS()
    #lat, lon = 39.7, -7.8  # Example: Perdigão, Portugal
    lat, lon = 57.2181, -7.3398
    tile = m.toMGRS(lat, lon, MGRSPrecision=0)
    print(tile)  # Output: e.g., 29SNC

    utm_zone = int((lon + 180) / 6) + 1
    if lat >= 0:
        epsg = 32600 + utm_zone  # Northern Hemisphere
    else:
        epsg = 32700 + utm_zone  # Southern Hemisphere
    print(f"EPSG code for UTM zone {utm_zone}: {epsg}")

    return tile, epsg

def run_dem_download_workflow(tile, resolution, download_folder):
    """
    Runs the DEM download script with a specific configuration.
    """
    print("Starting DEM download workflow...")
    
    # You can now define your arguments as a list of strings,
    # just like they would appear on the command line.
    
    # Arguments for downloading a single tile
    args_for_single_tile = [
        '--t', tile, 
        '--r', f'{resolution}',
        '--m', 'DGED',
        '--o', download_folder,
    ]
    
    # Arguments for using a config file
    args_from_config_file = [
        '--config', './configuration/my_custom_config.xml'
    ]
    
    # Arguments for resetting credentials
    args_reset_credentials = [
        '--reset'
    ]

    # Choose which set of arguments you want to use for the call
    # For this demonstration, we'll run the first example
    print(f"Executing with arguments: {args_for_single_tile}")
    exit_code = dem_downloader(args_for_single_tile)
    
    if exit_code == 0:
        print("DEM download script completed successfully.")
    else:
        print(f"DEM download script failed with exit code: {exit_code}.")
    
    print("Finished DEM download workflow.")

if __name__ == "__main__":
    download_folder = "/Users/ssudhakaran/Documents/Simulations/2025/Copernicus-DEM-downloader/data/downloaded/"
    output_folder = "/Users/ssudhakaran/Documents/Simulations/2025/Copernicus-DEM-downloader/data/extracted/"
    stl_folder = "/Users/ssudhakaran/Documents/Simulations/2025/Copernicus-DEM-downloader/data/stl/"

    #Location details

    center_lat=57.3511  # example: Perdigão
    center_lon=-7.3858
    crop_size_km = 40  # Crop size in km
    resolution_m = 30  # resolution in meters
    final_crop_size_km = 12  # Final crop size in km
    wind_direction_deg = 270  # Example wind direction in degrees

    tile, epsg =find_tile_from_coordinates(center_lat, center_lon)
    run_dem_download_workflow(tile, resolution_m, download_folder)
    tif_file= merge_and_clip_dem(download_folder, output_folder, center_lat, center_lon, epsg, crop_size_km)
    reproject_and_crop_to_utm_rotated(tif_file, stl_folder, center_lat, center_lon, epsg, wind_direction_deg, final_crop_size_km)