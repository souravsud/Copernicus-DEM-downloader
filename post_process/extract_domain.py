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

# Directories
directory = "./output_dir"
save_dir = os.path.join(directory, "extracted")
input_folder= os.path.join(directory, "downloaded_files")
output_tif= os.path.join(save_dir, "clipped_dem.tif")
output_tif_UTM = os.path.join(save_dir, "clipped_dem_UTM.tif")
output_stl = os.path.join(save_dir, "cropped_terrain.stl")

#Location details
center_lat=39.7  # example: Perdigão
center_lon=-7.725
utm_zone = 29  # Change this based on location
utm_epsg = 32600 + utm_zone  # For Northern Hemisphere, use 32600 + zone number

# Crop sizes
firstCropSizeKm = 30  # Initial crop size in km
finalCropSizeKm = 12  # Final crop size in km-- this is the size of the cropped DEM in UTM coordinates

def tif_to_stl_cropped(tif_path, stl_path, z_exaggeration=1.0, crop_margin_km=0.5):
    with rasterio.open(tif_path) as src:
        band = src.read(1)
        transform = src.transform
        nodata = src.nodata

        # Mask no-data values
        band = np.where(band == nodata, np.nan, band)
        band *= z_exaggeration

        nrows, ncols = band.shape

        # Get x, y coords for all pixels
        x_coords = np.zeros((nrows, ncols))
        y_coords = np.zeros((nrows, ncols))
        for row in range(nrows):
            for col in range(ncols):
                x, y = rasterio.transform.xy(transform, row, col)
                x_coords[row, col] = x
                y_coords[row, col] = y

        # Determine cropping bounds (crop_margin_km in meters)
        xmin = x_coords.min() + crop_margin_km * 1000
        xmax = x_coords.max() - crop_margin_km * 1000
        ymin = y_coords.min() + crop_margin_km * 1000
        ymax = y_coords.max() - crop_margin_km * 1000

        # Create mask for points inside crop box
        mask = (x_coords >= xmin) & (x_coords <= xmax) & (y_coords >= ymin) & (y_coords <= ymax)

        # Find bounding rows and cols inside mask
        rows, cols = np.where(mask)
        row_min, row_max = rows.min(), rows.max()
        col_min, col_max = cols.min(), cols.max()

        # Crop arrays
        band_cropped = band[row_min:row_max+1, col_min:col_max+1]
        x_cropped = x_coords[row_min:row_max+1, col_min:col_max+1]
        y_cropped = y_coords[row_min:row_max+1, col_min:col_max+1]

        # Build PyVista grid with cropped data
        surf = pv.StructuredGrid(x_cropped, y_cropped, band_cropped)

        # Extract surface mesh (for STL)
        surface = surf.extract_surface()

        # Save STL
        import os
        os.makedirs(os.path.dirname(stl_path), exist_ok=True)
        surface.save(stl_path)
        print(f"✅ Cropped STL saved to: {stl_path}")

def tif_to_stl(tif_path, stl_path, z_exaggeration=1.0):
    with rasterio.open(tif_path) as src:
        band = src.read(1)
        transform = src.transform

        # Mask no-data values
        band = np.where(band == src.nodata, np.nan, band)
        band *= z_exaggeration

        # Grid dimensions
        nrows, ncols = band.shape
        x_coords = np.zeros((nrows, ncols))
        y_coords = np.zeros((nrows, ncols))

        for row in range(nrows):
            for col in range(ncols):
                x, y = xy(transform, row, col)
                x_coords[row, col] = x
                y_coords[row, col] = y

        # Create the surface grid
        surf = pv.StructuredGrid(x_coords, y_coords, band)

        # Convert to surface mesh (needed for STL)
        surface = surf.extract_surface()

        # Ensure output folder exists
        os.makedirs(os.path.dirname(stl_path), exist_ok=True)

        # Save STL
        surface.save(stl_path)
        print(f"✅ STL saved to: {stl_path}")


def reproject_and_crop_to_utm(input_tif, output_tif, utm_epsg, crop_size_km=13):
    crop_size_km = crop_size_km + 1
    with rasterio.open(input_tif) as src:
        # Reproject
        transform, width, height = calculate_default_transform(
            src.crs, f"EPSG:{utm_epsg}", src.width, src.height, *src.bounds
        )
        kwargs = src.meta.copy()
        kwargs.update({
            'crs': f"EPSG:{utm_epsg}",
            'transform': transform,
            'width': width,
            'height': height
        })

        # Ensure output folder exists
        os.makedirs(os.path.dirname(output_tif), exist_ok=True)

        # Step 1: Reproject and save to a temporary in-memory array
        temp_arr = src.read(
            out_shape=(src.count, height, width),
            resampling=Resampling.bilinear
        )
        reprojected = temp_arr

    # Calculate cropping bounds
    center_x = transform.c + (width * transform.a) / 2
    center_y = transform.f + (height * transform.e) / 2

    crop_half = (crop_size_km * 1000) / 2
    xmin = center_x - crop_half
    xmax = center_x + crop_half
    ymin = center_y - crop_half
    ymax = center_y + crop_half

    # Compute window for cropping
    crop_window = from_bounds(xmin, ymin, xmax, ymax, transform)

    # Crop the array
    cropped = reprojected[:, 
        int(crop_window.row_off):int(crop_window.row_off + crop_window.height),
        int(crop_window.col_off):int(crop_window.col_off + crop_window.width)
    ]

    # Adjust metadata for cropped output
    new_transform = rasterio.windows.transform(crop_window, transform)
    kwargs.update({
        'height': cropped.shape[1],
        'width': cropped.shape[2],
        'transform': new_transform
    })

    # Save cropped UTM GeoTIFF
    with rasterio.open(output_tif, "w", **kwargs) as dst:
        dst.write(cropped)


def merge_and_clip_dem(input_folder, output_tif, center_lat, center_lon, size_km=12):
    
    output_dir = os.path.dirname(output_tif)
    os.makedirs(output_dir, exist_ok=True)
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
    half_size_deg = size_km / 111 / 2  # half size in degrees

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

    with rasterio.open(output_tif, "w", **out_meta) as dest:
        dest.write(clipped)

    print(f"✅ Clipped DEM saved to: {output_tif}")

merge_and_clip_dem(input_folder, output_tif, center_lat, center_lon, size_km=firstCropSizeKm)
reproject_and_crop_to_utm(output_tif, output_tif_UTM, utm_epsg, crop_size_km=finalCropSizeKm)
tif_to_stl_cropped(output_tif_UTM, output_stl, z_exaggeration=1.0)