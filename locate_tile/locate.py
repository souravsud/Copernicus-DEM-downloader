import mgrs

m = mgrs.MGRS()
lat, lon = 39.7, -7.8  # Example: Perdigão, Portugal
tile = m.toMGRS(lat, lon, MGRSPrecision=0)
print(tile)  # Output: e.g., 29SNC
