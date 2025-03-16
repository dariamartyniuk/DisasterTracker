from geopy.distance import geodesic

# Calculate distance between two coordinates (lat, lon)
def calculate_distance(coord1, coord2):
    return geodesic(coord1, coord2).km
