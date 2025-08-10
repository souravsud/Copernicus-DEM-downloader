import pyvista as pv
import numpy as np
import matplotlib.pyplot as plt

def smooth_terrain_boundaries(stl_file, output_file=None, 
                            domain_size=18000, aoi_size=8000, 
                            transition_width=2000, plot=True):
    """
    Smooth terrain boundaries for CFD simulation.
    
    Parameters:
    -----------
    stl_file : str
        Path to input STL file
    output_file : str, optional
        Path for output STL file (if None, adds '_smoothed' to input name)
    domain_size : float
        Total domain size in meters (18km = 18000m)
    aoi_size : float
        Area of interest size in meters (8km = 8000m)
    transition_width : float
        Width of smoothing transition zone in meters
    plot : bool
        Whether to show before/after plots
    """
    
    # Load the mesh
    print("Loading terrain mesh...")
    mesh = pv.read(stl_file)
    
    # Get points (vertices)
    points = mesh.points.copy()
    
    # Find domain center (assuming mesh is centered at origin)
    # If not centered, you might need to adjust this
    center_x = (points[:, 0].min() + points[:, 0].max()) / 2
    center_y = (points[:, 1].min() + points[:, 1].max()) / 2
    
    print(f"Domain center: ({center_x:.1f}, {center_y:.1f})")
    print(f"Elevation range: {points[:, 2].min():.1f} to {points[:, 2].max():.1f} m")
    
    # Calculate distances from center
    distances = np.sqrt((points[:, 0] - center_x)**2 + (points[:, 1] - center_y)**2)
    
    # Define zones
    aoi_radius = aoi_size / 2
    transition_start = aoi_radius + transition_width / 2
    transition_end = domain_size / 2 - 500  # Leave small buffer from boundary
    
    print(f"AOI radius: {aoi_radius:.1f} m")
    print(f"Transition zone: {transition_start:.1f} - {transition_end:.1f} m")
    
    # Calculate target elevation (you can modify this)
    # Option 1: Mean elevation
    target_elevation = points[:, 2].mean()
    
    # Option 2: Median elevation (more robust to outliers)
    # target_elevation = np.median(points[:, 2])
    
    # Option 3: Elevation at domain center
    # center_mask = distances < 1000  # within 1km of center
    # target_elevation = points[center_mask, 2].mean()
    
    print(f"Target elevation for boundaries: {target_elevation:.1f} m")
    
    # Create smoothing factors
    smoothing_factors = np.zeros_like(distances)
    
    # No smoothing in AOI
    smoothing_factors[distances <= transition_start] = 0.0
    
    # Linear transition
    transition_mask = (distances > transition_start) & (distances < transition_end)
    transition_distances = distances[transition_mask]
    smoothing_factors[transition_mask] = (
        (transition_distances - transition_start) / 
        (transition_end - transition_start)
    )
    
    # Full smoothing beyond transition zone
    smoothing_factors[distances >= transition_end] = 1.0
    
    # Apply smoothing
    original_elevations = points[:, 2].copy()
    points[:, 2] = (
        original_elevations * (1 - smoothing_factors) + 
        target_elevation * smoothing_factors
    )
    
    # Update mesh with modified points
    mesh.points = points
    
    # Generate output filename if not provided
    if output_file is None:
        if stl_file.endswith('.stl'):
            output_file = stl_file.replace('.stl', '_smoothed.stl')
        else:
            output_file = stl_file + '_smoothed.stl'
    
    # Save the modified mesh
    print(f"Saving smoothed terrain to: {output_file}")
    mesh.save(output_file)
    
    # Plotting
    if plot:
        fig, axes = plt.subplots(2, 2, figsize=(15, 12))
        
        # Create a grid for plotting (subsample for speed)
        n_plot = min(50000, len(points))
        plot_indices = np.random.choice(len(points), n_plot, replace=False)
        
        plot_x = points[plot_indices, 0]
        plot_y = points[plot_indices, 1]
        plot_z_orig = original_elevations[plot_indices]
        plot_z_new = points[plot_indices, 2]
        plot_dist = distances[plot_indices]
        plot_smooth = smoothing_factors[plot_indices]
        
        # Original elevation
        scatter1 = axes[0,0].scatter(plot_x, plot_y, c=plot_z_orig, cmap='terrain', s=1)
        axes[0,0].set_title('Original Terrain')
        axes[0,0].set_xlabel('X (m)')
        axes[0,0].set_ylabel('Y (m)')
        axes[0,0].axis('equal')
        plt.colorbar(scatter1, ax=axes[0,0], label='Elevation (m)')
        
        # Smoothed elevation  
        scatter2 = axes[0,1].scatter(plot_x, plot_y, c=plot_z_new, cmap='terrain', s=1)
        axes[0,1].set_title('Smoothed Terrain')
        axes[0,1].set_xlabel('X (m)')
        axes[0,1].set_ylabel('Y (m)')
        axes[0,1].axis('equal')
        plt.colorbar(scatter2, ax=axes[0,1], label='Elevation (m)')
        
        # Smoothing factor
        scatter3 = axes[1,0].scatter(plot_x, plot_y, c=plot_smooth, cmap='viridis', s=1)
        axes[1,0].set_title('Smoothing Factor')
        axes[1,0].set_xlabel('X (m)')
        axes[1,0].set_ylabel('Y (m)')
        axes[1,0].axis('equal')
        plt.colorbar(scatter3, ax=axes[1,0], label='Smoothing Factor')
        
        # Elevation vs distance profile
        sorted_indices = np.argsort(plot_dist)
        axes[1,1].plot(plot_dist[sorted_indices]/1000, plot_z_orig[sorted_indices], 
                      'b.', alpha=0.3, label='Original', markersize=0.5)
        axes[1,1].plot(plot_dist[sorted_indices]/1000, plot_z_new[sorted_indices], 
                      'r.', alpha=0.3, label='Smoothed', markersize=0.5)
        axes[1,1].axvline(aoi_radius/1000, color='green', linestyle='--', label='AOI boundary')
        axes[1,1].axvline(transition_start/1000, color='orange', linestyle='--', label='Transition start')
        axes[1,1].axhline(target_elevation, color='red', linestyle='--', alpha=0.7, label='Target elevation')
        axes[1,1].set_xlabel('Distance from center (km)')
        axes[1,1].set_ylabel('Elevation (m)')
        axes[1,1].set_title('Elevation vs Distance Profile')
        axes[1,1].legend()
        axes[1,1].grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.show()
    
    print("Terrain smoothing completed!")
    print(f"Elevation change summary:")
    print(f"  Points unchanged: {np.sum(smoothing_factors == 0):,}")
    print(f"  Points in transition: {np.sum((smoothing_factors > 0) & (smoothing_factors < 1)):,}")
    print(f"  Points fully smoothed: {np.sum(smoothing_factors == 1):,}")
    
    return mesh, output_file

# Example usage:
if __name__ == "__main__":
    # Replace with your STL file path
    input_stl = "/Users/ssudhakaran/Documents/Simulations/2025/Copernicus-DEM-downloader/data/cropped/terrain.stl"
    
    # Run the smoothing
    smoothed_mesh, output_path = smooth_terrain_boundaries(
        stl_file=input_stl,
        domain_size=18000,  # 18 km
        aoi_size=8000,      # 8 km AOI
        transition_width=2000,  # 2 km transition zone
        plot=True
    )
    
    print(f"\nSmoothed terrain saved to: {output_path}")
    
    # Optional: Quick mesh quality check
    print(f"\nMesh info:")
    print(f"  Number of points: {smoothed_mesh.n_points:,}")
    print(f"  Number of faces: {smoothed_mesh.n_faces:,}")
    print(f"  Bounds: {smoothed_mesh.bounds}")