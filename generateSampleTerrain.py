import os
import numpy as np
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
from rasterio.crs import CRS
import pyproj
from pyproj import Transformer
import pyvista as pv
from scipy.ndimage import rotate
import matplotlib.pyplot as plt
from scipy.interpolate import griddata
from scipy.ndimage import gaussian_filter
import warnings
warnings.filterwarnings('ignore', category=rasterio.errors.NotGeoreferencedWarning)

def get_utm_crs(longitude, latitude):
    """
    Determine the appropriate UTM CRS for given coordinates.
    """
    # Calculate UTM zone
    utm_zone = int((longitude + 180) / 6) + 1
    
    # Determine hemisphere
    if latitude >= 0:
        epsg_code = 32600 + utm_zone  # Northern hemisphere
    else:
        epsg_code = 32700 + utm_zone  # Southern hemisphere
    
    return CRS.from_epsg(epsg_code)

def reproject_to_utm(input_path, output_path=None):
    """
    Reproject a DEM from geographic coordinates to UTM projection.
    """
    with rasterio.open(input_path) as src:
        # Get the center coordinates to determine UTM zone
        bounds = src.bounds
        center_lon = (bounds.left + bounds.right) / 2
        center_lat = (bounds.bottom + bounds.top) / 2
        
        # Get appropriate UTM CRS
        dst_crs = get_utm_crs(center_lon, center_lat)
        
        print(f"Reprojecting to {dst_crs}")
        
        # Calculate transform and new dimensions
        transform, width, height = calculate_default_transform(
            src.crs, dst_crs, src.width, src.height, *src.bounds)
        
        # Define output profile
        kwargs = src.meta.copy()
        kwargs.update({
            'crs': dst_crs,
            'transform': transform,
            'width': width,
            'height': height
        })
        
        if output_path is None:
            # Create temporary file name
            base_name = os.path.splitext(input_path)[0]
            output_path = f"{base_name}_utm.tif"
        
        # Reproject and save
        with rasterio.open(output_path, 'w', **kwargs) as dst:
            reproject(
                source=rasterio.band(src, 1),
                destination=rasterio.band(dst, 1),
                src_transform=src.transform,
                src_crs=src.crs,
                dst_transform=transform,
                dst_crs=dst_crs,
                resampling=Resampling.bilinear)
        
        print(f"UTM reprojection saved to: {output_path}")
        return output_path, dst_crs

def latlon_to_utm(lat, lon, utm_crs):
    """
    Convert lat/lon coordinates to UTM coordinates.
    """
    # Create transformer from WGS84 to UTM
    transformer = Transformer.from_crs(CRS.from_epsg(4326), utm_crs, always_xy=True)
    utm_x, utm_y = transformer.transform(lon, lat)
    return utm_x, utm_y

def create_rotated_crop_mask(center_x, center_y, crop_size_m, rotation_deg, x_coords, y_coords):
    """
    Create a mask for a rotated rectangular crop.
    """
    # Convert rotation to radians
    rotation_rad = np.deg2rad(rotation_deg-90)
    
    # Half dimensions of the crop
    half_size = crop_size_m / 2
    
    # Create coordinate grids relative to center
    rel_x = x_coords - center_x
    rel_y = y_coords - center_y
    
    # Apply inverse rotation to coordinates (rotate coordinate system, not the crop)
    cos_theta = np.cos(-rotation_rad)
    sin_theta = np.sin(-rotation_rad)
    
    rotated_x = rel_x * cos_theta - rel_y * sin_theta
    rotated_y = rel_x * sin_theta + rel_y * cos_theta
    
    # Check if points fall within the rectangular bounds
    mask = ((np.abs(rotated_x) <= half_size) & (np.abs(rotated_y) <= half_size))
    
    return mask

def crop_dem_around_point_rotated(dem_path, center_lat, center_lon, crop_size_km, rotation_deg=0, utm_crs=None):
    """
    Create a rotated crop of a DEM around a specified center point.
    """
    with rasterio.open(dem_path) as src:
        # If no UTM CRS provided, determine it
        if utm_crs is None:
            utm_crs = get_utm_crs(center_lon, center_lat)
        
        # Convert center point to UTM if the DEM is in UTM
        if src.crs != CRS.from_epsg(4326):
            # Assume DEM is already in UTM
            center_utm_x, center_utm_y = latlon_to_utm(center_lat, center_lon, src.crs)
        else:
            # DEM is in geographic coordinates, need to reproject first
            print("DEM appears to be in geographic coordinates. Reprojecting...")
            utm_dem_path, utm_crs = reproject_to_utm(dem_path)
            return crop_dem_around_point_rotated(utm_dem_path, center_lat, center_lon, crop_size_km, rotation_deg, utm_crs)
        
        crop_size_m = crop_size_km * 1000
        
        # Calculate expanded bounds to ensure we capture all rotated pixels
        # For a rotated square, the diagonal is sqrt(2) times the side length
        buffer_size = crop_size_m * np.sqrt(2) / 2
        
        expanded_bounds = [
            center_utm_x - buffer_size,  # left
            center_utm_y - buffer_size,  # bottom
            center_utm_x + buffer_size,  # right
            center_utm_y + buffer_size   # top
        ]
        
        print(f"Expanded bounds for rotation (UTM): {expanded_bounds}")
        
        # Convert bounds to pixel coordinates
        left_px = int((expanded_bounds[0] - src.bounds.left) / src.res[0])
        right_px = int((expanded_bounds[2] - src.bounds.left) / src.res[0])
        bottom_px = int((src.bounds.top - expanded_bounds[3]) / src.res[1])
        top_px = int((src.bounds.top - expanded_bounds[1]) / src.res[1])
        
        # Ensure we don't go outside the image bounds
        left_px = max(0, left_px)
        right_px = min(src.width, right_px)
        bottom_px = max(0, bottom_px)
        top_px = min(src.height, top_px)
        
        print(f"Expanded pixel window: ({left_px}, {bottom_px}, {right_px}, {top_px})")
        
        # Read the expanded data
        window = rasterio.windows.Window.from_slices((bottom_px, top_px), (left_px, right_px))
        expanded_data = src.read(1, window=window)
        
        if expanded_data.size == 0:
            raise ValueError("Expanded crop area is empty. Check your coordinates and crop size.")
        
        # Calculate transform for expanded data
        expanded_transform = rasterio.windows.transform(window, src.transform)
        
        # Create coordinate arrays for the expanded data
        nrows, ncols = expanded_data.shape
        
        # Create x, y coordinate arrays in UTM
        x_coords = np.arange(ncols) * src.res[0] + expanded_transform.c
        y_coords = np.arange(nrows) * (-src.res[1]) + expanded_transform.f  # Note: y resolution is typically negative
        
        # Create coordinate grids
        x_grid, y_grid = np.meshgrid(x_coords, y_coords)
        
        # Create the rotated crop mask
        print(f"Creating rotated crop mask (rotation: {rotation_deg}°)...")
        crop_mask = create_rotated_crop_mask(center_utm_x, center_utm_y, crop_size_m, rotation_deg, x_grid, y_grid)
        
        # Apply mask to elevation data
        cropped_data = expanded_data.copy()
        cropped_data[~crop_mask] = np.nan
        
        print(f"Rotated crop completed. Valid pixels: {np.sum(crop_mask)} / {crop_mask.size}")
        
        return cropped_data, expanded_transform, src.crs, src.res, crop_mask

def create_mesh_from_dem(elevation_data, transform, pixel_res, crop_mask=None):
    """
    Create a PyVista mesh from elevation data with optional mask for rotated crops.
    """
    print(f"Creating mesh from DEM data with shape: {elevation_data.shape}")
    
    # Handle NaN values (these will be the areas outside our rotated crop)
    if np.any(np.isnan(elevation_data)):
        print("Handling areas outside rotated crop (NaN values)...")
        valid_mask = ~np.isnan(elevation_data)
        if not np.any(valid_mask):
            raise ValueError("No valid elevation data in the rotated crop area.")
    else:
        valid_mask = np.ones_like(elevation_data, dtype=bool)
    
    # Get dimensions
    nrows, ncols = elevation_data.shape
    
    # Create coordinate arrays
    pixel_width, pixel_height = pixel_res
    
    # Create x, y coordinate arrays
    x = np.arange(ncols) * pixel_width
    y = np.arange(nrows) * abs(pixel_height)  # Use abs since pixel_height might be negative
    
    # Center the coordinates
    x = x - np.mean(x)
    y = y - np.mean(y)
    
    # Create meshgrid
    X, Y = np.meshgrid(x, y)
    
    # Flip Y to match typical image orientation
    Y = np.flipud(Y)
    elevation_flipped = np.flipud(elevation_data)
    valid_mask_flipped = np.flipud(valid_mask)
    
    # Only create points for valid (non-NaN) areas
    valid_indices = np.where(valid_mask_flipped)
    n_valid_points = len(valid_indices[0])
    
    if n_valid_points == 0:
        raise ValueError("No valid points found in the rotated crop.")
    
    print(f"Valid points in rotated crop: {n_valid_points}")
    
    # Create points array for valid data only
    valid_x = X[valid_indices]
    valid_y = Y[valid_indices]
    valid_z = elevation_flipped[valid_indices]
    
    # Create a point cloud first
    points = np.column_stack((valid_x, valid_y, valid_z))
    point_cloud = pv.PolyData(points)
    
    # For irregularly distributed points (due to rotation), we need to create a surface
    # Using Delaunay triangulation on the XY plane
    print("Creating Delaunay triangulation for rotated crop...")
    
    # Project points to 2D for triangulation
    points_2d = points[:, :2]  # Just X, Y coordinates
    
    # Create 2D triangulation
    from scipy.spatial import Delaunay
    tri = Delaunay(points_2d)
    
    # Create faces for PyVista (triangles)
    faces = []
    for simplex in tri.simplices:
        faces.append([3, simplex[0], simplex[1], simplex[2]])  # 3 vertices per face
    faces = np.hstack(faces)
    
    # Create the mesh
    mesh = pv.PolyData(points, faces)
    
    # Add elevation data
    mesh.point_data['elevation'] = valid_z
    
    print(f"Created triangulated mesh with {mesh.n_points} points and {mesh.n_cells} faces")
    
    return mesh

def create_rotated_stl_from_dem(dem_path, output_stl, crop_km, rotation_deg, center_lat, center_lon, intermediate_save=True):
    """
    Main function to create a rotated STL file from a DEM.
    """
    print(f"Processing DEM: {dem_path}")
    print(f"Crop size: {crop_km} km")
    print(f"Rotation: {rotation_deg} degrees")
    print(f"Center: {center_lat}, {center_lon}")
    
    try:
        # Check if input file exists
        if not os.path.exists(dem_path):
            raise FileNotFoundError(f"DEM file not found: {dem_path}")
        
        # Create output directory if it doesn't exist
        os.makedirs(os.path.dirname(output_stl), exist_ok=True)
        
        # Step 1: Check if DEM needs reprojection to UTM
        with rasterio.open(dem_path) as src:
            print(f"Original CRS: {src.crs}")
            if src.crs == CRS.from_epsg(4326) or 'geographic' in str(src.crs).lower():
                print("Reprojecting to UTM...")
                if intermediate_save:
                    utm_path = dem_path.replace('.tif', '_utm.tif')
                    utm_dem_path, utm_crs = reproject_to_utm(dem_path, utm_path)
                else:
                    utm_dem_path, utm_crs = reproject_to_utm(dem_path)
            else:
                print("DEM appears to already be in projected coordinates")
                utm_dem_path = dem_path
                utm_crs = src.crs
        
        # Step 2: Create rotated crop of the DEM around the center point
        print("Creating rotated crop of DEM...")
        elevation_data, transform, crs, pixel_res, crop_mask = crop_dem_around_point_rotated(
            utm_dem_path, center_lat, center_lon, crop_km, rotation_deg, utm_crs
        )
        
        if elevation_data.size == 0:
            raise ValueError("Cropped area is empty. Check your coordinates and crop size.")
        
        print("Smoothing terrain for CFD mesh quality...")
        elevation_data = smooth_terrain_for_cfd(elevation_data, sigma=2.0)

        print(f"Rotated crop elevation data shape: {elevation_data.shape}")
        valid_elevations = elevation_data[~np.isnan(elevation_data)]
        if len(valid_elevations) > 0:
            print(f"Elevation range: {np.min(valid_elevations):.1f} to {np.max(valid_elevations):.1f} meters")
        else:
            raise ValueError("No valid elevation data in rotated crop area.")
        
        # Step 3: Create mesh from rotated crop (no additional rotation needed)
        print("Creating 3D mesh from rotated crop...")
        mesh = create_mesh_from_dem(elevation_data, transform, pixel_res, crop_mask)
        
        # Step 4: Save as STL
        print(f"Saving STL file: {output_stl}")
        mesh.save(output_stl)
        
        print(f"Successfully created STL file: {output_stl}")
        print(f"Final mesh statistics:")
        print(f"  - Points: {mesh.n_points}")
        print(f"  - Faces: {mesh.n_cells}")
        print(f"  - Bounds: {mesh.bounds}")
        
        return output_stl
        
    except Exception as e:
        print(f"Error processing DEM: {str(e)}")
        raise

def smooth_terrain_for_cfd(elevation_data, sigma=2.0, preserve_nan=True):
    """
    Smooth terrain data for better CFD mesh quality
    
    Parameters:
    - sigma: smoothing strength (higher = more smoothing)
    - preserve_nan: keep NaN areas (outside rotated crop) as NaN
    """
    if preserve_nan:
        valid_mask = ~np.isnan(elevation_data)
        smoothed = elevation_data.copy()
        
        # Only smooth valid areas
        valid_data = elevation_data[valid_mask]
        if len(valid_data) > 0:
            # Create temporary array for smoothing
            temp_array = np.zeros_like(elevation_data)
            temp_array[valid_mask] = valid_data
            temp_array[~valid_mask] = np.mean(valid_data)  # Fill NaN with mean for smoothing
            
            # Apply smoothing
            smoothed_temp = gaussian_filter(temp_array, sigma=sigma)
            
            # Restore only valid areas
            smoothed[valid_mask] = smoothed_temp[valid_mask]
    else:
        smoothed = gaussian_filter(elevation_data, sigma=sigma)
    
    return smoothed


def realign_rotated_stl(input_stl_path, output_stl_path, rotation_deg):
    """
    Realign a rotated STL to axis-aligned coordinates
    Applies counter-rotation to make terrain features align with X/Y axes
    
    Parameters:
    - input_stl_path: your current rotated STL file
    - output_stl_path: output path for aligned STL
    - rotation_deg: original rotation angle applied to terrain (to reverse it)
    """
    
    print(f"Loading rotated STL: {input_stl_path}")
    mesh = pv.read(input_stl_path)
    
    print(f"Original mesh bounds: {mesh.bounds}")
    print(f"Applying counter-rotation of {-rotation_deg}°...")
    
    # Get current points
    points = mesh.points.copy()
    
    # Apply counter-rotation (negative of original rotation)
    theta = np.deg2rad(-rotation_deg)  # Negative to reverse rotation
    cos_theta = np.cos(theta)
    sin_theta = np.sin(theta)
    
    # Rotate X,Y coordinates (Z stays the same)
    x_new = points[:, 0] * cos_theta - points[:, 1] * sin_theta
    y_new = points[:, 0] * sin_theta + points[:, 1] * cos_theta
    
    # Create new mesh with realigned coordinates
    new_mesh = mesh.copy()
    new_mesh.points[:, 0] = x_new
    new_mesh.points[:, 1] = y_new
    # Z coordinates unchanged
    
    print(f"Realigned mesh bounds: {new_mesh.bounds}")
    
    # Save the realigned STL
    new_mesh.save(output_stl_path)
    print(f"Axis-aligned STL saved: {output_stl_path}")
    
    return output_stl_path

def visualize_dem_and_stl_2d(original_tiff_path, stl_file_path, center_lat, center_lon, crop_size_km, rotation_deg):
    """
    Simple 2D visualization:
    1) Original DEM with crop area marked (left)
    2) STL data as 2D elevation map (right)
    """
    print("Creating 2D visualization of DEM and STL...")
    
    # Read original DEM (left plot)
    with rasterio.open(original_tiff_path) as src:
        full_terrain = src.read(1)
        transform = src.transform
        crs = src.crs
        bounds = src.bounds
        res = src.res
    
    # Handle coordinate conversion if needed
    if crs != CRS.from_epsg(4326):
        center_utm_x, center_utm_y = latlon_to_utm(center_lat, center_lon, crs)
    else:
        utm_path, utm_crs = reproject_to_utm(original_tiff_path)
        return visualize_dem_and_stl_2d(utm_path, stl_file_path, center_lat, center_lon, crop_size_km, rotation_deg)
    
    # Create side-by-side plots
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 8))
    
    # Left plot: Full terrain with crop outline
    im1 = ax1.imshow(full_terrain, 
                     extent=[bounds.left, bounds.right, bounds.bottom, bounds.top], 
                     cmap='terrain', origin='upper')
    
    # Draw crop rectangle
    crop_size_m = crop_size_km * 1000
    half_size = crop_size_m / 2
    angle_rad = np.deg2rad(rotation_deg)
    
    corners = np.array([
        [-half_size, -half_size], [half_size, -half_size], 
        [half_size, half_size], [-half_size, half_size], 
        [-half_size, -half_size]
    ])
    
    cos_theta, sin_theta = np.cos(angle_rad), np.sin(angle_rad)
    rotated_corners = np.zeros_like(corners)
    rotated_corners[:, 0] = corners[:, 0] * cos_theta - corners[:, 1] * sin_theta + center_utm_x
    rotated_corners[:, 1] = corners[:, 0] * sin_theta + corners[:, 1] * cos_theta + center_utm_y
    
    ax1.plot(rotated_corners[:, 0], rotated_corners[:, 1], 'red', linewidth=3, label=f'Crop Area ({crop_size_km}km)')
    ax1.plot(center_utm_x, center_utm_y, 'r+', markersize=12, markeredgewidth=3, label='Center')
    
    # NEW: Add directional arrow to show the "top" of the rotated crop
    # Calculate arrow pointing to the top edge of the rotated rectangle
    arrow_length = half_size * 0.8  # Make arrow slightly shorter than half the crop size
    # Top direction after rotation (pointing from center to top edge midpoint)
    arrow_end_x = center_utm_x + (0 * cos_theta - arrow_length * sin_theta)
    arrow_end_y = center_utm_y + (0 * sin_theta + arrow_length * cos_theta)
    
    # Draw arrow from center pointing to top
    ax1.annotate('', xy=(arrow_end_x, arrow_end_y), xytext=(center_utm_x, center_utm_y),
                arrowprops=dict(arrowstyle='->', color='red', lw=2, alpha=0.8))

    
    ax1.set_title(f'Original DEM with Crop Area\n(Rotation: {rotation_deg}°)')
    ax1.set_xlabel('Easting (m)')
    ax1.set_ylabel('Northing (m)')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    ax1.set_aspect('equal')
    
    # Right plot: STL data as 2D elevation map
    try:
        stl_mesh = pv.read(stl_file_path)
        points = stl_mesh.points
        
        # Create regular grid for interpolation
        x_min, x_max = points[:, 0].min(), points[:, 0].max()
        y_min, y_max = points[:, 1].min(), points[:, 1].max()
        
        # Create grid with similar resolution to original TIFF
        grid_size = 200  # Adjust for desired resolution
        xi = np.linspace(x_min, x_max, grid_size)
        yi = np.linspace(y_min, y_max, grid_size)
        xi_grid, yi_grid = np.meshgrid(xi, yi)
        
        # Interpolate STL points to regular grid
        zi_grid = griddata((points[:, 0], points[:, 1]), points[:, 2], 
                          (xi_grid, yi_grid), method='cubic')
        
        # Plot as image like the TIFF
        im2 = ax2.imshow(zi_grid, extent=[x_min, x_max, y_min, y_max], 
                cmap='terrain', origin='upper')  # Same as TIFF
        
        ax2.set_title(f'Cropped Content \nInterpolated to Grid')
        plt.colorbar(im2, ax=ax2, shrink=0.8, label='Elevation (m)')
        
    except Exception as e:
        print(f"Error: {e}")
    
    # Add colorbar for DEM
    plt.colorbar(im1, ax=ax1, shrink=0.8, label='Elevation (m)')
    
    plt.tight_layout()
    plt.show()
    
    return fig





# Example usage (you can modify this as needed)
if __name__ == "__main__":
    # Your example parameters
    input_file = "/Users/ssudhakaran/Documents/Simulations/2025/Copernicus-DEM-downloader/data/extracted/DEM_crop_lat39_709N_lon7_736W_utm32629_size50km.tif"
    output_folder_final = "/Users/ssudhakaran/Documents/Simulations/2025/Copernicus-DEM-downloader/data/cropped"
    center_lat = 39.7088333
    center_lon = -7.7355556
    
    # Parameters for the final STL
    rotation_deg = 200
    final_crop_km = 30
    output_stl = os.path.join(output_folder_final, f"rotated_crop_{final_crop_km}km_{rotation_deg}deg.stl")
    aligned_stl = os.path.join(output_folder_final, f"rotated_crop_{final_crop_km}km_{rotation_deg}deg_realigned.stl")
    
    # Create the rotated STL from the DEM
    create_rotated_stl_from_dem(
        dem_path=input_file,
        output_stl=output_stl,
        crop_km=final_crop_km,
        rotation_deg=rotation_deg,
        center_lat=center_lat,
        center_lon=center_lon
    )


    realign_rotated_stl(
        input_stl_path=output_stl,
        output_stl_path=aligned_stl,
        rotation_deg=-rotation_deg  # Your original rotation angle
    )

    """ visualize_dem_and_stl_2d(
        original_tiff_path=input_file,
        stl_file_path=aligned_stl,
        center_lat=center_lat, 
        center_lon=center_lon,
        crop_size_km=final_crop_km,
        rotation_deg=rotation_deg
    ) """

