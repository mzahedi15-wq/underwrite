"""Address normalization and distance calculation utilities."""

from __future__ import annotations

import math
from typing import Optional

from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut


_geocoder = None


def get_geocoder() -> Nominatim:
    """Get or create a Nominatim geocoder instance."""
    global _geocoder
    if _geocoder is None:
        _geocoder = Nominatim(user_agent="str-researcher/0.1")
    return _geocoder


def geocode_address(address: str) -> Optional[tuple[float, float]]:
    """Geocode an address to (lat, lng). Returns None if geocoding fails."""
    try:
        location = get_geocoder().geocode(address, timeout=10)
        if location:
            return (location.latitude, location.longitude)
    except (GeocoderTimedOut, Exception):
        pass
    return None


def haversine_distance(
    lat1: float, lng1: float, lat2: float, lng2: float
) -> float:
    """Calculate distance in miles between two lat/lng points using Haversine formula."""
    R = 3959.0  # Earth's radius in miles

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlng / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def normalize_address(address: str) -> str:
    """Basic address normalization for deduplication."""
    addr = address.upper().strip()
    replacements = {
        " STREET": " ST",
        " AVENUE": " AVE",
        " BOULEVARD": " BLVD",
        " DRIVE": " DR",
        " LANE": " LN",
        " ROAD": " RD",
        " COURT": " CT",
        " CIRCLE": " CIR",
        " PLACE": " PL",
        " TRAIL": " TRL",
        " WAY": " WAY",
        " NORTH": " N",
        " SOUTH": " S",
        " EAST": " E",
        " WEST": " W",
        " NORTHEAST": " NE",
        " NORTHWEST": " NW",
        " SOUTHEAST": " SE",
        " SOUTHWEST": " SW",
        " APARTMENT": " APT",
        " SUITE": " STE",
        " UNIT": " UNIT",
        "#": "APT ",
    }
    for old, new in replacements.items():
        addr = addr.replace(old, new)

    # Remove extra whitespace
    addr = " ".join(addr.split())
    return addr


def are_same_property(
    addr1: str,
    lat1: Optional[float],
    lng1: Optional[float],
    addr2: str,
    lat2: Optional[float],
    lng2: Optional[float],
    beds1: int,
    beds2: int,
) -> bool:
    """Check if two listings refer to the same property."""
    # Normalized address match
    if normalize_address(addr1) == normalize_address(addr2):
        return True

    # Proximity check (within ~150 feet) + same bed count
    if lat1 and lng1 and lat2 and lng2 and beds1 == beds2:
        distance = haversine_distance(lat1, lng1, lat2, lng2)
        if distance < 0.03:  # ~150 feet
            return True

    return False
