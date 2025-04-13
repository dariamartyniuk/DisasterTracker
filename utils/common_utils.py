import json
import logging
import math
import redis
import requests
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union, Tuple, Callable
from rx import from_iterable, operators as op
from config import Config

# ===== Redis Operations =====

def get_redis_connection(db: int = Config.REDIS_DB) -> redis.Redis:
    """
    Create and return a Redis connection with the specified database.
    
    Args:
        db: Redis database number to connect to
        
    Returns:
        Redis connection object
    """
    return redis.Redis(
        host=Config.REDIS_HOST, 
        port=Config.REDIS_PORT, 
        db=db, 
        decode_responses=True
    )

def store_data_in_redis(data: List[Dict], key: str, clear_existing: bool = True) -> bool:
    """
    Store a list of dictionaries in Redis under the specified key.
    
    Args:
        data: List of dictionaries to store
        key: Redis key to store data under
        clear_existing: Whether to clear existing data under the key
        
    Returns:
        True if successful, False otherwise
    """
    try:
        r = get_redis_connection()
        if clear_existing:
            r.delete(key)
        
        logging.info(f"Storing {len(data)} items in Redis under key '{key}'...")
        for item in data:
            item_json = json.dumps(item, ensure_ascii=False)
            logging.debug(f"Storing item: {item_json}")
            r.rpush(key, item_json)
        
        logging.info(f"Successfully stored {len(data)} items in Redis.")
        return True
    except Exception as e:
        logging.error(f"Error storing data in Redis: {e}")
        return False

def get_data_from_redis(key: str) -> List[Dict]:
    """
    Retrieve data from Redis under the specified key.
    
    Args:
        key: Redis key to retrieve data from
        
    Returns:
        List of dictionaries retrieved from Redis
    """
    try:
        r = get_redis_connection()
        data = r.lrange(key, 0, -1)
        items = [json.loads(item) for item in data]
        logging.info(f"Retrieved {len(items)} items from Redis under key '{key}'.")
        return items
    except Exception as e:
        logging.error(f"Error retrieving data from Redis: {e}")
        return []

def clear_redis_key(key: str) -> bool:
    """
    Clear data under the specified Redis key.
    
    Args:
        key: Redis key to clear
        
    Returns:
        True if successful, False otherwise
    """
    try:
        r = get_redis_connection()
        r.delete(key)
        logging.info(f"Cleared Redis key '{key}'.")
        return True
    except Exception as e:
        logging.error(f"Error clearing Redis key '{key}': {e}")
        return False

# ===== API Operations =====

def fetch_data_from_api(url: str, params: Dict = None, error_msg: str = "API request failed") -> Dict:
    """
    Fetch data from an API endpoint.
    
    Args:
        url: API endpoint URL
        params: Query parameters for the request
        error_msg: Error message to log if request fails
        
    Returns:
        API response as a dictionary
    """
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        logging.info(f"Successfully fetched data from {url}")
        return data
    except Exception as e:
        logging.error(f"{error_msg}: {e}")
        return {}

# ===== Date Operations =====

def calculate_date_range(events: List[Dict], days_before: int = 10, days_after: int = 10) -> Tuple[str, str]:
    """
    Calculate a date range based on event start times.
    
    Args:
        events: List of events with 'start' field containing dateTime
        days_before: Number of days to extend range before earliest event
        days_after: Number of days to extend range after latest event
        
    Returns:
        Tuple of (start_date, end_date) in ISO format
    """
    try:
        return from_iterable(events) \
            .pipe(
                op.map(lambda event: datetime.fromisoformat(event["start"]["dateTime"].split("+")[0])),
                op.to_iterable(),
                op.map(lambda dates: sorted(dates)),
                op.map(lambda sorted_dates: (
                    (sorted_dates[0] - timedelta(days=days_before)).date().isoformat(),
                    (sorted_dates[-1] + timedelta(days=days_after)).date().isoformat()
                )),
                op.to_list()
            ).run()[0]
    except Exception as e:
        logging.error(f"Error calculating date range: {e}")
        # Return a default range if calculation fails
        today = datetime.now().date()
        return (today.isoformat(), today.isoformat())

def validate_date(date_text: str) -> bool:
    """
    Validate that a date string is in YYYY-MM-DD format.
    
    Args:
        date_text: Date string to validate
        
    Returns:
        True if valid, False otherwise
    """
    try:
        datetime.strptime(date_text, "%Y-%m-%d")
        return True
    except ValueError:
        logging.error(f"Invalid date format: {date_text}. Expected YYYY-MM-DD.")
        return False

# ===== Geospatial Operations =====

def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great circle distance between two points on the earth.
    
    Args:
        lat1, lon1: Latitude and longitude of first point
        lat2, lon2: Latitude and longitude of second point
        
    Returns:
        Distance in kilometers
    """
    # Radius of Earth in kilometers
    R = Config.EARTH_RADIUS_KM
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) \
        * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def calculate_central_coords(location: Dict) -> Dict[str, float]:
    """
    Calculate the central coordinates from a location with bounds.
    
    Args:
        location: Dictionary with 'northeast' and 'southwest' coordinates
        
    Returns:
        Dictionary with 'lat' and 'lng' of the central point
    """
    bounds = location["northeast"], location["southwest"]
    return {
        "lat": (bounds[0]["lat"] + bounds[1]["lat"]) / 2,
        "lng": (bounds[0]["lng"] + bounds[1]["lng"]) / 2,
    }

# ===== Data Processing =====

def group_by_key(items: List[Dict], key_func: Callable, group_name: str = "items") -> List[Dict]:
    """
    Group items by a key function.
    
    Args:
        items: List of items to group
        key_func: Function to extract the key from each item
        group_name: Name of the list field in the result
        
    Returns:
        List of groups with 'key' and group_name fields
    """
    groups = {}
    for item in items:
        key = key_func(item)
        if key is None:
            continue
        if key not in groups:
            groups[key] = {"key": key, group_name: []}
        groups[key][group_name].append(item)
    return sorted(groups.values(), key=lambda x: len(x[group_name]), reverse=True)

def merge_by_id(source: Dict, target: List[Dict], id_field: str = 'id') -> List[Dict]:
    """
    Merge source data into target data by matching on an ID field.
    
    Args:
        source: Dictionary with items to merge from
        target: List of dictionaries to merge into
        id_field: Field name to use for matching
        
    Returns:
        Merged list of dictionaries
    """
    source_items = {item[id_field]: item for item in source.get('items', [])}
    merged = []
    for item in target:
        source_item = source_items.get(item[id_field], {})
        merged_item = {**item}
        for key, value in source_item.items():
            if key not in merged_item:
                merged_item[key] = value
        merged.append(merged_item)
    return merged 