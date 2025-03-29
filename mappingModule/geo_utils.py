# mappingModule/geo_utils.py
import logging
from geopy.geocoders import Nominatim

geolocator = Nominatim(user_agent="disaster_tracker")

def get_coordinates_from_location(location):
    try:
        loc = geolocator.geocode(location)
        if loc:
            logging.info(f"Geocoded '{location}' to ({loc.latitude}, {loc.longitude})")
            return (loc.latitude, loc.longitude)
        else:
            logging.warning(f"Could not geocode location: {location}")
            return None
    except Exception as e:
        logging.error(f"Error geocoding location {location}: {e}")
        return None
