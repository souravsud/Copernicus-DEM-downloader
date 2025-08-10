import rasterio
from rasterio.merge import merge
from rasterio.mask import mask
from shapely.geometry import box, mapping
import os
import pyproj
from rasterio.warp import transform_geom


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
    """
    Merges and clips DEMs with accurate handling of coordinate systems.

    This function first merges all GeoTIFFs in a folder, then accurately clips the
    merged raster to a specified size (in km) around a given latitude and longitude.
    It does this by leveraging a projected CRS (UTM) for the clipping operation,
    ensuring that the crop size is accurate regardless of the location on Earth.
    """
    lat_val, lat_hem, lon_val, lon_hem = latlon_to_hemispheric(center_lat, center_lon)

    filename = (
                f"DEM_crop_lat{lat_val}{lat_hem}_"
                f"lon{lon_val}{lon_hem}_"
                f"utm{utm_epsg}_"
                f"size{crop_size_km}km.tif"
            )
    
    output_file = os.path.join(output_folder, filename)
    os.makedirs(output_folder, exist_ok=True)

    tifs = [os.path.join(input_folder, f) for f in os.listdir(input_folder) if f.endswith('.tif')]
    if not tifs:
        raise ValueError("No .tif files found.")

    src_files_to_mosaic = [rasterio.open(f) for f in tifs]

    # Merge into a single raster
    mosaic, out_trans = merge(src_files_to_mosaic)
    crs_dem = src_files_to_mosaic[0].crs  # CRS of the DEM, likely EPSG:4326

    out_meta = src_files_to_mosaic[0].meta.copy()
    out_meta.update({
        "driver": "GTiff",
        "height": mosaic.shape[1],
        "width": mosaic.shape[2],
        "transform": out_trans,
        "crs": crs_dem
    })

    # --- ACCURATE CLIPPING LOGIC ---

    # 1. Define the projected CRS for accurate distance calculation
    # We will use the UTM zone specified by utm_epsg for this
    utm_crs = f"EPSG:{utm_epsg}"

    # 2. Define the center point in both WGS84 and the projected UTM CRS
    wgs84_point = (center_lon, center_lat)

    # Use pyproj to transform the center point from WGS84 to the UTM CRS
    transformer = pyproj.Transformer.from_crs("EPSG:4326", utm_crs, always_xy=True)
    center_lon_utm, center_lat_utm = transformer.transform(center_lon, center_lat)

    # 3. Create the bounding box in the projected UTM CRS
    # All calculations are now in meters, ensuring accuracy
    half_size_m = (crop_size_km * 1000) / 2
    
    utm_min_x = center_lon_utm - half_size_m
    utm_min_y = center_lat_utm - half_size_m
    utm_max_x = center_lon_utm + half_size_m
    utm_max_y = center_lat_utm + half_size_m

    # Create the box in the UTM CRS
    utm_bbox = box(utm_min_x, utm_min_y, utm_max_x, utm_max_y)

    print(f"Clipping bounds in UTM (m): X={utm_min_x}:{utm_max_x}, Y={utm_min_y}:{utm_max_y}")

    # 4. Transform the UTM bounding box back to the DEM's CRS (EPSG:4326)
    # This is necessary because rasterio's mask function expects the geometry to be
    # in the same CRS as the raster it's clipping.
    geo = [transform_geom(utm_crs, crs_dem, mapping(utm_bbox))]

    # --- END OF ACCURATE CLIPPING LOGIC ---

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