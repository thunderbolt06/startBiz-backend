"""
Google Places Tool
Searches for nearby businesses of a specific type and returns structured data.
"""

import googlemaps
from django.conf import settings


def search_places(query: str, location: str, radius: int = 5000) -> dict:
    """
    Searches Google Places for businesses matching `query` near `location`.
    Returns counts, ratings, reviews and a list of top results.
    """
    api_key = settings.GOOGLE_PLACES_API_KEY

    if not api_key:
        return _mock_places_response(query, location)

    try:
        gmaps = googlemaps.Client(key=api_key)

        geocode = gmaps.geocode(location)
        if not geocode:
            return {"error": f"Could not geocode location: {location}", "query": query}

        lat_lng = geocode[0]["geometry"]["location"]

        places_result = gmaps.places_nearby(
            location=lat_lng,
            radius=radius,
            keyword=query,
        )

        results = places_result.get("results", [])

        businesses = []
        for place in results[:20]:
            businesses.append({
                "name": place.get("name"),
                "rating": place.get("rating"),
                "user_ratings_total": place.get("user_ratings_total", 0),
                "price_level": place.get("price_level"),
                "vicinity": place.get("vicinity"),
                "business_status": place.get("business_status"),
                "types": place.get("types", []),
            })

        ratings = [b["rating"] for b in businesses if b.get("rating")]
        avg_rating = round(sum(ratings) / len(ratings), 2) if ratings else None

        return {
            "query": query,
            "location": location,
            "radius_meters": radius,
            "total_found": len(results),
            "avg_rating": avg_rating,
            "businesses": businesses,
            "market_saturation": _saturation_label(len(results)),
        }

    except Exception as e:
        return {"error": str(e), "query": query, "location": location}


def _saturation_label(count: int) -> str:
    if count == 0:
        return "none — no direct competitors found"
    elif count <= 3:
        return "low — very few competitors"
    elif count <= 8:
        return "moderate — some competition"
    elif count <= 15:
        return "high — competitive market"
    else:
        return "very high — saturated market"


def _mock_places_response(query: str, location: str) -> dict:
    """Returns mock data when no API key is configured (for development)."""
    return {
        "query": query,
        "location": location,
        "radius_meters": 5000,
        "total_found": 4,
        "avg_rating": 4.1,
        "market_saturation": "low — very few competitors",
        "businesses": [
            {"name": f"Sample {query} Store 1", "rating": 4.2, "user_ratings_total": 87, "vicinity": f"Near {location}"},
            {"name": f"Sample {query} Store 2", "rating": 3.9, "user_ratings_total": 42, "vicinity": f"Near {location}"},
            {"name": f"Sample {query} Boutique", "rating": 4.5, "user_ratings_total": 203, "vicinity": f"Near {location}"},
            {"name": f"Another {query} Shop", "rating": 3.8, "user_ratings_total": 31, "vicinity": f"Near {location}"},
        ],
        "_mock": True,
        "_note": "Mock data — set GOOGLE_PLACES_API_KEY for real results",
    }
