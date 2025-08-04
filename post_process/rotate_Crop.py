import os
import rasterio
import numpy as np
from rasterio.warp import calculate_default_transform, Resampling
from rasterio.mask import mask
from shapely.geometry import Polygon
from shapely.affinity import rotate

def sanitize_float_for_filename(value, decimals=3):
    # Limit decimals and replace dot with underscore
    return f"{value:.{decimals}f}".replace('.', '_')

def create_new_filename(lat, lon, epsg, final_crop_size_km, wind_direction, extension=".tif"):
    lat_val_str = sanitize_float_for_filename(abs(lat))
    lon_val_str = sanitize_float_for_filename(abs(lon))
    # Extract hemisphere components
    lat_hem = 'N' if lat >= 0 else 'S'
    lon_hem = 'E' if lon >= 0 else 'W'
    
    # Reconstruct filename with updated crop size and new wind_direction
    filename = (
        f"crop_lat{lat_val_str}{lat_hem}_"
        f"lon{lon_val_str}{lon_hem}_"
        f"utm{epsg}_"
        f"size{final_crop_size_km}km_"
        f"wind{int(wind_direction)}deg"
        f"{extension}"
    )
    
    return filename

def reproject_and_crop_to_utm_rotated(input_tif, output_dir, lat, lon, utm_epsg, wind_direction_deg, crop_size_km=13):
    """
    Reprojects a GeoTIFF to UTM, rotates a crop window based on a wind direction,
    and crops the raster data. The final output is an axis-aligned bounding box
    of the rotated crop, with corners filled with nodata values.

    Args:
        input_tif (str): Path to the input GeoTIFF.
        output_dir (str): Directory where the output GeoTIFF will be saved.
        lat (float): Center latitude of the crop.
        lon (float): Center longitude of the crop.
        utm_epsg (int): EPSG code for the target UTM zone.
        wind_direction_deg (float): Wind direction in degrees (0 = North, 90 = East).
        crop_size_km (float, optional): Side length of the square crop area in kilometers.
                                        Defaults to 13.
    """
    # Define output file path early
    output_filename = create_new_filename(lat, lon, utm_epsg, crop_size_km, wind_direction_deg)
    output_tif_path = os.path.join(output_dir, output_filename)
    
    os.makedirs(output_dir, exist_ok=True)

    with rasterio.open(input_tif) as src:
        # Step 1: Calculate new transform and dimensions for UTM projection
        dst_transform, dst_width, dst_height = calculate_default_transform(
            src.crs, f"EPSG:{utm_epsg}", src.width, src.height, *src.bounds
        )
        
        # Keep a copy of the source metadata and update with destination info
        dst_meta = src.meta.copy()
        dst_meta.update({
            'driver': 'GTiff',
            'crs': f"EPSG:{utm_epsg}",
            'transform': dst_transform,
            'width': dst_width,
            'height': dst_height,
            'nodata': -9999
        })

        # Step 2: Reproject the data into a NumPy array in memory
        reprojected_array = np.zeros(
            (src.count, dst_height, dst_width), 
            dtype=src.dtypes[0]
        )
        
        rasterio.warp.reproject(
            source=rasterio.band(src, 1),
            destination=reprojected_array,
            src_crs=src.crs,
            src_transform=src.transform,
            dst_crs=f"EPSG:{utm_epsg}",
            dst_transform=dst_transform,
            resampling=Resampling.bilinear,
            src_nodata=src.nodata,
            dst_nodata=dst_meta['nodata']
        )

    # Step 3: Create the rotated cropping polygon
    center_x = dst_transform.c + (dst_width * dst_transform.a) / 2
    center_y = dst_transform.f + (dst_height * dst_transform.e) / 2
    crop_half = (crop_size_km * 1000) / 2
    rotation_angle = 90 - wind_direction_deg
    
    unrotated_box = Polygon([
        (-crop_half, -crop_half),
        (crop_half, -crop_half),
        (crop_half, crop_half),
        (-crop_half, crop_half)
    ])
    rotated_box = rotate(unrotated_box, rotation_angle, origin='center')
    
    rotated_box_at_center = Polygon([
        (p[0] + center_x, p[1] + center_y) for p in rotated_box.exterior.coords
    ])
    
    geo_shapes = [rotated_box_at_center]
    
    # Step 4: Mask the reprojected array using the rotated polygon
    # This block is the workaround for older rasterio versions
    with rasterio.io.MemoryFile() as memfile:
        with memfile.open(**dst_meta) as temp_ds:
            temp_ds.write(reprojected_array)
            clipped_array, clipped_transform = mask(
                temp_ds,
                geo_shapes,
                crop=True,
                nodata=dst_meta['nodata']
            )

    # Step 5: Update metadata for the final clipped raster and save
    dst_meta.update({
        'height': clipped_array.shape[1],
        'width': clipped_array.shape[2],
        'transform': clipped_transform,
        'count': src.count
    })
    
    with rasterio.open(output_tif_path, "w", **dst_meta) as dst:
        dst.write(clipped_array)

    print(f"✅ Rotated and cropped GeoTIFF saved to: {output_tif_path}")