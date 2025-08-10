from stl import mesh
import matplotlib.pyplot as plt
import numpy as np
from scipy.interpolate import griddata

stl_file = "/Users/ssudhakaran/Documents/Simulations/2025/Copernicus-DEM-downloader/data/cropped/rotated_crop_18km_30deg_realigned.stl"
# Load the STL file
your_mesh = mesh.Mesh.from_file(stl_file)  # Replace with your STL file path


# Extract all triangle vertices (flatten to points)
points = your_mesh.vectors.reshape(-1, 3)
x, y, z = points[:, 0], points[:, 1], points[:, 2]

# Create a grid to interpolate the height (z) values onto
xi = np.linspace(x.min(), x.max(), 300)
yi = np.linspace(y.min(), y.max(), 300)
xi, yi = np.meshgrid(xi, yi)

# Interpolate z values on the grid
zi = griddata((x, y), z, (xi, yi), method='linear')

# Plot the contour map
plt.figure(figsize=(10, 7))
cp = plt.contourf(xi, yi, zi, levels=50, cmap='terrain')
plt.colorbar(cp, label='Elevation (Z)')
plt.xlabel('X')
plt.ylabel('Y')
plt.title('Top-View Terrain Contour from STL')
plt.axis('equal')
plt.tight_layout()
plt.show()