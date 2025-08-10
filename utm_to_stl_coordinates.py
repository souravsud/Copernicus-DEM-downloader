import numpy as np
from pyproj import Transformer, CRS

def get_utm_crs(longitude, latitude):
    """Determine appropriate UTM CRS from lat/lon"""
    utm_zone = int((longitude + 180) / 6) + 1
    if latitude >= 0:
        epsg_code = 32600 + utm_zone
    else:
        epsg_code = 32700 + utm_zone
    return CRS.from_epsg(epsg_code)

def convert_coordinates_to_utm(coords, coord_type="wgs84"):
    """Convert coordinates to UTM"""
    if isinstance(coords, list) and len(coords) > 0 and isinstance(coords[0], (tuple, list)):
        utm_results = []
        for coord_pair in coords:
            utm_result = convert_coordinates_to_utm(coord_pair, coord_type)
            utm_results.append(utm_result)
        return utm_results
    
    if coord_type == "wgs84":
        lon, lat = coords
        utm_crs = get_utm_crs(lon, lat)
        transformer = Transformer.from_crs("epsg:4326", utm_crs.to_epsg(), always_xy=True)
        return transformer.transform(lon, lat)
    
    elif coord_type == "etrs89":
        etrs89_x, etrs89_y = coords
        transformer = Transformer.from_crs("epsg:3763", "epsg:32629", always_xy=True)
        return transformer.transform(etrs89_x, etrs89_y)

def update_probe_coordinates_for_aligned_terrain(utm_coords, center_lat, center_lon, original_rotation_deg):
    """
    Calculate probe coordinates for aligned (counter-rotated) terrain
    This applies the NEGATIVE of the original rotation to align with unrotated terrain
    
    Parameters:
    - utm_coords: list of UTM coordinates [(utm_x, utm_y, utm_z), ...]
    - center_lat, center_lon: terrain center
    - original_rotation_deg: ORIGINAL rotation that was applied to terrain (will be reversed)
    
    Returns: STL coordinates for aligned terrain
    """
    # Get UTM CRS and terrain center
    utm_crs = get_utm_crs(center_lon, center_lat)
    transformer = Transformer.from_crs(CRS.from_epsg(4326), utm_crs, always_xy=True)
    center_utm_x, center_utm_y = transformer.transform(center_lon, center_lat)
    
    aligned_coords = []
    
    for utm_x, utm_y, utm_z in utm_coords:
        # Step 1: Translate to center at (0,0)
        x_centered = utm_x - center_utm_x
        y_centered = utm_y - center_utm_y
        
        # Step 2: Apply counter-rotation (NEGATIVE of original rotation)
        theta = np.deg2rad(-original_rotation_deg)  # Negative to align with unrotated terrain
        cos_theta = np.cos(theta)
        sin_theta = np.sin(theta)
        
        x_aligned = x_centered * cos_theta - y_centered * sin_theta
        y_aligned = x_centered * sin_theta + y_centered * cos_theta
        z_aligned = utm_z
        
        aligned_coords.append((x_aligned, y_aligned, z_aligned))
    
    return aligned_coords

def generate_openfoam_sets_aligned(tower_locations, center_lat, center_lon, original_rotation_deg,
                                  max_height=3000, n_points=100, set_name_prefix="tower"):
    """Generate OpenFOAM sets for aligned terrain"""
    sets_text = "      sets\n      (\n"
    
    for i, tower in enumerate(tower_locations):
        x_stl, y_stl, z_stl = tower['aligned_coords']
        tower_name = tower.get('name', f"{set_name_prefix}_{i+1:02d}")
        
        start_point = f"({x_stl:.2f} {y_stl:.2f} {z_stl})"
        end_point = f"({x_stl:.2f} {y_stl:.2f} {z_stl + max_height})"
        
        sets_text += f"""          {tower_name}
          {{
              type            lineUniform;
              axis            z;
              start           {start_point};
              end             {end_point};
              nPoints         {n_points};
          }}"""
        
        if i < len(tower_locations) - 1:
            sets_text += "\n\n"
    
    sets_text += "\n      );"
    return sets_text

# Main processing for your specific input
if __name__ == "__main__":
    # Your parameters
    center_lat = 39.7088333
    center_lon = -7.7355556
    rotation_deg = 30  # Original rotation applied to terrain
    
    # Your tower data
    tower_data = [
        {
            'name': 'tower_SE_04',
            'wgs84': None,
            'etrs89': (33394.18, 4258.87)
        },
        {
            'name': 'tower_SE_09', 
            'wgs84': None,
            'etrs89': (34153.02, 4844.78)
        },
        {
            'name': 'tower_SE_13',
            'wgs84': None,
            'etrs89': (34533.6, 5112.01)
        },
    ]

    print("Processing Tower Locations for Aligned Terrain:")
    print("=" * 70)
    
    # Process all towers
    tower_locations = []
    
    for i, tower in enumerate(tower_data):
        print(f"\nTower: {tower['name']}")
        print("-" * 30)
        
        # Convert ETRS89 to UTM
        if tower['etrs89'] is not None:
            utm_x, utm_y = convert_coordinates_to_utm(tower['etrs89'], "etrs89")
            print(f"ETRS89: {tower['etrs89']} → UTM({utm_x:.2f}, {utm_y:.2f})")
        else:
            print("No coordinates provided!")
            continue
        
        # Convert to aligned terrain coordinates
        utm_z = 0  # Ground level
        aligned_coords = update_probe_coordinates_for_aligned_terrain(
            [(utm_x, utm_y, utm_z)], center_lat, center_lon, rotation_deg
        )[0]
        
        x_aligned, y_aligned, z_aligned = aligned_coords
        print(f"Aligned coordinates: ({x_aligned:.2f}, {y_aligned:.2f}, {z_aligned:.2f})")
        
        # Check domain bounds
        domain_bounds = [-8000, 8000]
        within_domain = (domain_bounds[0] <= x_aligned <= domain_bounds[1] and 
                        domain_bounds[0] <= y_aligned <= domain_bounds[1])
        status = "✓" if within_domain else "✗"
        print(f"Domain check: {status} {'Within bounds' if within_domain else 'Outside bounds'}")
        
        tower_locations.append({
            'name': tower['name'],
            'etrs89_coords': tower['etrs89'],
            'utm_coords': (utm_x, utm_y, utm_z),
            'aligned_coords': aligned_coords,
            'within_domain': within_domain
        })

    print("\n" + "=" * 70)
    print("OpenFOAM Sets Configuration for Aligned Terrain:")
    print("=" * 70)
    
    # Generate OpenFOAM sets
    sets_text = generate_openfoam_sets_aligned(
        tower_locations, center_lat, center_lon, rotation_deg
    )
    
    complete_function = f"""functions
{{
    towerProfiles
    {{
        type            sets;
        enabled         true;
        verbose         true;
        interpolationScheme cellPoint;
        functionObjectLibs ("libsampling.so");

        writeControl    writeTime;
        writeInterval   1;

        fields
        (
            U
            p
            k
            epsilon
        );

{sets_text}

        setFormat       csv;
        setPrecision    8;
    }}
}}"""

    print(complete_function)
    
    print("\n" + "=" * 70)
    print("Summary:")
    print("=" * 70)
    
    valid_towers = [t for t in tower_locations if t['within_domain']]
    print(f"Total towers processed: {len(tower_locations)}")
    print(f"Towers within domain: {len(valid_towers)}")
    
    if len(valid_towers) != len(tower_locations):
        outside_towers = [t['name'] for t in tower_locations if not t['within_domain']]
        print(f"Towers outside domain: {outside_towers}")