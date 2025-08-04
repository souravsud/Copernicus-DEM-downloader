import rasterio
from rasterio.plot import show, plotting_extent  # ✅ Add this import
import matplotlib.pyplot as plt


# Path to your DEM file
dem_path = "/Users/ssudhakaran/Documents/Simulations/2025/Copernicus-DEM-downloader/data/extracted/askervein/clipped_dem_UTM.tif"

with rasterio.open(dem_path) as src:
    dem = src.read(1)  # read the first (and only) band
    extent = plotting_extent(src)

# Plot
plt.figure(figsize=(10, 8))
plt.imshow(dem, cmap="terrain", extent=extent)
plt.colorbar(label="Elevation (m)")
plt.title("DEM Elevation Map")
plt.xlabel("Longitude")
plt.ylabel("Latitude")
plt.grid(True)
plt.show()
