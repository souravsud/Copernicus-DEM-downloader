import pyvista as pv
import numpy as np
import matplotlib.pyplot as plt

def smooth_terrain_boundaries(stl_file, output_file=None, 
                            domain_size=30000, aoi_size=8000, 
                            transition_width=6000, plot=True):
    """
    Smooth terrain boundaries for CFD simulation with 30km domain.
    
    Parameters:
    -----------
    stl_file : str
        Path to input STL file
    output_file : str, optional
        Path for output STL file (if None, adds '_smoothed' to input name)
    domain_size : float
        Total domain size in meters (30km = 30000m)
    aoi_size : float
        Area of interest size in meters (8km = 8000m)
    transition_width : float
        Width of smoothing transition zone in meters (6km recommended)
    plot : bool
        Whether to show before/after plots
    """
    
    # Load the mesh
    print("Loading terrain mesh...")
    mesh = pv.read(stl_file)
    
    # Get points (vertices)
    points = mesh.points.copy()
    
    # Find domain center (assuming mesh is centered at origin)
    center_x = (points[:, 0].min() + points[:, 0].max()) / 2
    center_y = (points[:, 1].min() + points[:, 1].max()) / 2
    
    print(f"Domain center: ({center_x:.1f}, {center_y:.1f})")
    print(f"Elevation range: {points[:, 2].min():.1f} to {points[:, 2].max():.1f} m")
    
    # Calculate distances from center
    distances = np.sqrt((points[:, 0] - center_x)**2 + (points[:, 1] - center_y)**2)
    
    # Define zones for 30km domain
    aoi_radius = aoi_size / 2                           # 4km - preserve original
    transition_start = aoi_radius                       # 4km - start smoothing
    transition_end = domain_size / 2 - 1000            # 14km - end smoothing (1km buffer)
    
    print(f"AOI radius: {aoi_radius/1000:.1f} km")
    print(f"Transition zone: {transition_start/1000:.1f} - {transition_end/1000:.1f} km")
    print(f"Transition width: {(transition_end-transition_start)/1000:.1f} km")
    
    # Calculate target elevation - use mean of AOI region for stability
    aoi_mask = distances <= aoi_radius
    
    # Remove top 20% and bottom 10% of elevations, then take mean
    aoi_elevations = points[aoi_mask, 2]
    low_thresh = np.percentile(aoi_elevations, 10)   # Exclude deep valleys
    high_thresh = np.percentile(aoi_elevations, 80)  # Exclude peaks
    filtered_mask = (aoi_elevations >= low_thresh) & (aoi_elevations <= high_thresh)
    target_elevation = aoi_elevations[filtered_mask].mean()
    
    print(f"Target elevation for boundaries: {target_elevation:.1f} m")
    
    # Create smoothing factors with cosine transition (smoother than linear)
    smoothing_factors = np.zeros_like(distances)
    
    # No smoothing in AOI
    smoothing_factors[distances <= transition_start] = 0.0
    
    # Smooth cosine transition (much better than linear)
    transition_mask = (distances > transition_start) & (distances < transition_end)
    if np.any(transition_mask):
        transition_distances = distances[transition_mask]
        # Cosine transition: 0 to 1 smoothly
        normalized_dist = (transition_distances - transition_start) / (transition_end - transition_start)
        smoothing_factors[transition_mask] = 0.5 * (1 - np.cos(np.pi * normalized_dist))
    
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
            output_file = stl_file.replace('.stl', '_smoothed_30km.stl')
        else:
            output_file = stl_file + '_smoothed_30km.stl'
    
    # Save the modified mesh
    print(f"Saving smoothed terrain to: {output_file}")
    mesh.save(output_file)
    
    # Plotting
    if plot:
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        
        # Create a grid for plotting (subsample for speed)
        n_plot = min(100000, len(points))
        plot_indices = np.random.choice(len(points), n_plot, replace=False)
        
        plot_x = points[plot_indices, 0] / 1000  # Convert to km for plotting
        plot_y = points[plot_indices, 1] / 1000
        plot_z_orig = original_elevations[plot_indices]
        plot_z_new = points[plot_indices, 2]
        plot_dist = distances[plot_indices] / 1000  # km
        plot_smooth = smoothing_factors[plot_indices]
        
        # Original elevation
        scatter1 = axes[0,0].scatter(plot_x, plot_y, c=plot_z_orig, cmap='terrain', s=0.5)
        axes[0,0].set_title('Original Terrain (30km Domain)')
        axes[0,0].set_xlabel('X (km)')
        axes[0,0].set_ylabel('Y (km)')
        axes[0,0].axis('equal')
        # Add AOI boundary circle
        circle1 = plt.Circle((center_x/1000, center_y/1000), aoi_radius/1000, 
                           fill=False, color='red', linewidth=2, linestyle='--')
        axes[0,0].add_patch(circle1)
        plt.colorbar(scatter1, ax=axes[0,0], label='Elevation (m)')
        
        # Smoothed elevation  
        scatter2 = axes[0,1].scatter(plot_x, plot_y, c=plot_z_new, cmap='terrain', s=0.5)
        axes[0,1].set_title('Smoothed Terrain')
        axes[0,1].set_xlabel('X (km)')
        axes[0,1].set_ylabel('Y (km)')
        axes[0,1].axis('equal')
        # Add AOI boundary circle
        circle2 = plt.Circle((center_x/1000, center_y/1000), aoi_radius/1000, 
                           fill=False, color='red', linewidth=2, linestyle='--')
        axes[0,1].add_patch(circle2)
        plt.colorbar(scatter2, ax=axes[0,1], label='Elevation (m)')
        
        # Smoothing factor
        scatter3 = axes[1,0].scatter(plot_x, plot_y, c=plot_smooth, cmap='viridis', s=0.5)
        axes[1,0].set_title('Smoothing Factor (0=Original, 1=Flat)')
        axes[1,0].set_xlabel('X (km)')
        axes[1,0].set_ylabel('Y (km)')
        axes[1,0].axis('equal')
        plt.colorbar(scatter3, ax=axes[1,0], label='Smoothing Factor')
        
        # Elevation vs distance profile
        sorted_indices = np.argsort(plot_dist)
        axes[1,1].plot(plot_dist[sorted_indices], plot_z_orig[sorted_indices], 
                      'b.', alpha=0.2, label='Original', markersize=0.3)
        axes[1,1].plot(plot_dist[sorted_indices], plot_z_new[sorted_indices], 
                      'r.', alpha=0.3, label='Smoothed', markersize=0.3)
        axes[1,1].axvline(aoi_radius/1000, color='red', linewidth=2, linestyle='--', 
                         label=f'AOI boundary ({aoi_radius/1000:.1f} km)')
        axes[1,1].axvline(transition_start/1000, color='orange', linestyle='--', 
                         label=f'Transition start ({transition_start/1000:.1f} km)')
        axes[1,1].axvline(transition_end/1000, color='purple', linestyle='--',
                         label=f'Transition end ({transition_end/1000:.1f} km)')
        axes[1,1].axhline(target_elevation, color='red', linestyle=':', alpha=0.7, 
                         label=f'Target elevation ({target_elevation:.0f} m)')
        axes[1,1].set_xlabel('Distance from center (km)')
        axes[1,1].set_ylabel('Elevation (m)')
        axes[1,1].set_title('Elevation vs Distance Profile')
        axes[1,1].legend(fontsize=8)
        axes[1,1].grid(True, alpha=0.3)
        axes[1,1].set_xlim(0, 16)  # Focus on transition zone
        
        plt.tight_layout()
        plt.show()
    
    print("Terrain smoothing completed!")
    print(f"Elevation change summary:")
    print(f"  Points unchanged: {np.sum(smoothing_factors == 0):,}")
    print(f"  Points in transition: {np.sum((smoothing_factors > 0) & (smoothing_factors < 1)):,}")
    print(f"  Points fully smoothed: {np.sum(smoothing_factors == 1):,}")
    print(f"  Max elevation change: {np.max(np.abs(points[:, 2] - original_elevations)):.1f} m")
    
    # Add this to see if terrain makes geographic sense
    print("Terrain orientation check:")
    print(f"North boundary (max Y) elevation: {points[points[:,1] > 14000, 2].mean():.1f} m")  
    print(f"South boundary (min Y) elevation: {points[points[:,1] < -14000, 2].mean():.1f} m")
    print(f"East boundary (max X) elevation: {points[points[:,0] > 14000, 2].mean():.1f} m")
    print(f"West boundary (min X) elevation: {points[points[:,0] < -14000, 2].mean():.1f} m")
    return mesh, output_file

# Example usage for 30km domain:
if __name__ == "__main__":
    # Replace with your STL file path
    input_stl = "/Users/ssudhakaran/Documents/Simulations/2025/Copernicus-DEM-downloader/data/cropped/rotated_crop_31km_45deg_realigned.stl"
    
    # Run the smoothing with optimized parameters for 30km domain
    smoothed_mesh, output_path = smooth_terrain_boundaries(
        stl_file=input_stl,
        domain_size=30000,     # 30 km domain
        aoi_size=8000,         # 8 km AOI (preserve original terrain)
        transition_width=6000, # 6 km smooth transition (4km to 10km radius)
        plot=True
    )
    
    print(f"\nSmoothed terrain saved to: {output_path}")
    
    # Optional: Quick mesh quality check
    print(f"\nMesh info:")
    print(f"  Number of points: {smoothed_mesh.n_points:,}")
    print(f"  Number of faces: {smoothed_mesh.n_faces:,}")
    print(f"  Domain bounds: {[f'{b/1000:.1f}' for b in smoothed_mesh.bounds]} km")