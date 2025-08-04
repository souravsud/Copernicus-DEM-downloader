import os
import rasterio
from rasterio.merge import merge
from rasterio.mask import mask
from shapely.geometry import box, mapping
import geopandas as gpd
from rasterio.warp import calculate_default_transform, reproject, Resampling
import numpy as np
import pyvista as pv
from rasterio.transform import xy
from rasterio.transform import Affine
from rasterio.windows import from_bounds


def latlon_to_hemispheric(lat, lon):
    lat_val_str = sanitize_float_for_filename(abs(lat))
    lon_val_str = sanitize_float_for_filename(abs(lon))
    lat_hem = 'N' if lat >= 0 else 'S'
    lon_hem = 'E' if lon >= 0 else 'W'
    return lat_val_str, lat_hem, lon_val_str, lon_hem

def sanitize_float_for_filename(value, decimals=3):
    # Limit decimals and replace dot with underscore
    return f"{value:.{decimals}f}".replace('.', '_')

def merge_and_clip_dem(input_folder, output_folder, center_lat, center_lon, utm_epsg, crop_size_km):
    
    lat_val, lat_hem, lon_val, lon_hem = latlon_to_hemispheric(center_lat, center_lon)

    filename = (
                f"DEM_crop_lat{lat_val}{lat_hem}_"
                f"lon{lon_val}{lon_hem}_"
                f"utm{utm_epsg}_"
                f"size{crop_size_km}km.tif"
            )
    
    output_file = os.path.join(output_folder, filename)
    os.makedirs(output_folder, exist_ok=True)
    # Load all .tif files from folder
    tifs = [os.path.join(input_folder, f) for f in os.listdir(input_folder) if f.endswith('.tif')]
    if not tifs:
        raise ValueError("No .tif files found.")

    src_files_to_mosaic = [rasterio.open(f) for f in tifs]

    # Merge into a single raster
    mosaic, out_trans = merge(src_files_to_mosaic)
    crs = src_files_to_mosaic[0].crs  # CRS of DEM

    out_meta = src_files_to_mosaic[0].meta.copy()
    out_meta.update({
        "driver": "GTiff",
        "height": mosaic.shape[1],
        "width": mosaic.shape[2],
        "transform": out_trans,
        "crs": crs
    })

    # Since CRS is EPSG:4326, convert km to degrees (~1 deg ≈ 111 km)
    half_size_deg = crop_size_km / 111 / 2  # half size in degrees

    # Create bounding box in EPSG:4326
    lat_min = center_lat - half_size_deg
    lat_max = center_lat + half_size_deg
    lon_min = center_lon - half_size_deg
    lon_max = center_lon + half_size_deg
    print(f"Clipping bounds: lat_min={lat_min}, lat_max={lat_max}, lon_min={lon_min}, lon_max={lon_max}")

    bbox = box(lon_min, lat_min, lon_max, lat_max)
    geo = [mapping(bbox)]

    # Clip the merged DEM
    with rasterio.io.MemoryFile() as memfile:
        with memfile.open(**out_meta) as tmp_ds:
            tmp_ds.write(mosaic)
            clipped, clipped_transform = mask(tmp_ds, geo, crop=True)

    # Save the clipped result
    out_meta.update({
        "height": clipped.shape[1],
        "width": clipped.shape[2],
        "transform": clipped_transform
    })

    with rasterio.open(output_file, "w", **out_meta) as dest:
        dest.write(clipped)

    print(f"✅ Clipped DEM saved to: {output_file}")
    return output_file

#merge_and_clip_dem(input_folder, output_folder, center_lat, center_lon, utm_epsg, size_km=crop_size_km)