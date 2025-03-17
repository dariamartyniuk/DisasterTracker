import logging

from geopy import Nominatim

geolocator = Nominatim(user_agent="disaster_tracker")

from geopy.geocoders import Nominatim
import logging

geolocator = Nominatim(user_agent="disaster_tracker")

def get_coordinates_from_location(location):
    """
    Use geopy to get coordinates (latitude, longitude) from a location string.
    """
    try:
        location_obj = geolocator.geocode(location)
        if location_obj:
            logging.debug(f"Geocoded {location} to {location_obj.latitude}, {location_obj.longitude}")
            return location_obj.latitude, location_obj.longitude
        else:
            logging.warning(f"Could not geocode location: {location}")
            return None
    except Exception as e:
        logging.error(f"Error geocoding location {location}: {str(e)}")
        return None
