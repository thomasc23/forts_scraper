"""Geocoding module for converting fort locations to coordinates."""

import os
import re
import time
import requests
from datetime import datetime
from typing import Optional, Tuple
from dataclasses import dataclass


@dataclass
class GeocodingResult:
    """Result from a geocoding attempt."""
    lat: Optional[float] = None
    lon: Optional[float] = None
    confidence: str = "failed"  # exact, locality, approximate, county, state, failed
    source: str = "google"
    query: str = ""
    raw_response: Optional[dict] = None


# Google result types mapped to confidence levels
GOOGLE_TYPE_CONFIDENCE = {
    # High confidence - specific location
    "premise": "exact",
    "subpremise": "exact",
    "street_address": "exact",
    "route": "exact",
    "intersection": "exact",
    "point_of_interest": "exact",
    "park": "exact",
    "airport": "exact",
    "establishment": "exact",

    # Medium confidence - locality level
    "locality": "locality",
    "sublocality": "locality",
    "sublocality_level_1": "locality",
    "neighborhood": "locality",
    "postal_code": "locality",

    # Lower confidence - administrative areas
    "administrative_area_level_2": "county",
    "administrative_area_level_1": "state",
    "country": "state",
}


def preprocess_location(location_text: str) -> Tuple[str, bool, bool]:
    """
    Clean and preprocess location text for geocoding.

    Returns:
        Tuple of (cleaned_text, is_approximate, is_uncertain)
    """
    if not location_text:
        return "", False, False

    text = location_text.strip()
    is_approximate = False
    is_uncertain = False

    # Check for uncertainty marker
    if "?" in text:
        is_uncertain = True
        text = text.replace("?", "").strip()

    # Check for "near X" pattern
    near_match = re.match(r"^near\s+(.+)$", text, re.IGNORECASE)
    if near_match:
        is_approximate = True
        text = near_match.group(1).strip()

    # Clean up any double spaces
    text = re.sub(r"\s+", " ", text)

    return text, is_approximate, is_uncertain


def get_confidence_from_google_types(types: list, is_approximate: bool) -> str:
    """
    Determine confidence level from Google's result types.

    Args:
        types: List of result types from Google API
        is_approximate: Whether the original location had "near" prefix
    """
    confidence = "state"  # default to lowest

    for result_type in types:
        if result_type in GOOGLE_TYPE_CONFIDENCE:
            type_confidence = GOOGLE_TYPE_CONFIDENCE[result_type]
            # Upgrade confidence if this type is more specific
            if type_confidence == "exact":
                confidence = "approximate" if is_approximate else "exact"
                break
            elif type_confidence == "locality" and confidence in ("county", "state"):
                confidence = "approximate" if is_approximate else "locality"
            elif type_confidence == "county" and confidence == "state":
                confidence = "county"

    return confidence


def geocode_google(query: str, api_key: str, is_approximate: bool = False) -> GeocodingResult:
    """
    Geocode a location using Google Geocoding API.

    Args:
        query: The location query string
        api_key: Google API key
        is_approximate: Whether this was a "near X" location

    Returns:
        GeocodingResult with coordinates and confidence
    """
    result = GeocodingResult(query=query, source="google")

    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {
        "address": query,
        "key": api_key,
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        result.raw_response = data

        if data["status"] == "OK" and data.get("results"):
            first_result = data["results"][0]
            location = first_result["geometry"]["location"]

            result.lat = location["lat"]
            result.lon = location["lng"]
            result.confidence = get_confidence_from_google_types(
                first_result.get("types", []),
                is_approximate
            )
        elif data["status"] == "ZERO_RESULTS":
            result.confidence = "failed"
        else:
            # Other error statuses
            result.confidence = "failed"

    except requests.RequestException as e:
        result.confidence = "failed"
        result.raw_response = {"error": str(e)}

    return result


def geocode_fort(
    location_text: str,
    state_full_name: str,
    api_key: str,
    delay: float = 0.05
) -> GeocodingResult:
    """
    Geocode a fort location with fallback strategies.

    Args:
        location_text: The location_text field from the database
        state_full_name: Full state name (e.g., "California")
        api_key: Google API key
        delay: Delay in seconds after API call (rate limiting)

    Returns:
        GeocodingResult with best available coordinates
    """
    if not location_text or not location_text.strip():
        return GeocodingResult(confidence="failed", query="(no location)")

    # Preprocess the location
    cleaned, is_approximate, is_uncertain = preprocess_location(location_text)

    if not cleaned:
        return GeocodingResult(confidence="failed", query="(empty after cleaning)")

    # Build primary query
    primary_query = f"{cleaned}, {state_full_name}, USA"

    # Try primary query
    result = geocode_google(primary_query, api_key, is_approximate)

    if delay > 0:
        time.sleep(delay)

    # If failed and location contains "County", try county + state
    if result.confidence == "failed" and "county" not in cleaned.lower():
        # Try adding "County" if it looks like a county name
        pass  # Could add fallback logic here

    # If still failed and we have just a town name, we could try broader search
    # But for now, return what we have

    return result


def batch_geocode(
    forts: list,
    api_key: str,
    delay: float = 0.05,
    progress_callback=None
) -> list:
    """
    Geocode a batch of forts.

    Args:
        forts: List of dicts with fort_id, location_text, state_full_name
        api_key: Google API key
        delay: Delay between requests
        progress_callback: Optional function(current, total) for progress updates

    Returns:
        List of (fort_id, GeocodingResult) tuples
    """
    results = []
    total = len(forts)

    for i, fort in enumerate(forts):
        result = geocode_fort(
            fort["location_text"],
            fort["state_full_name"],
            api_key,
            delay=delay
        )
        results.append((fort["fort_id"], result))

        if progress_callback:
            progress_callback(i + 1, total)

    return results
