"""
Demographics Tool
Fetches population density and demographic data via the World Bank API and
falls back to curated data for common Indian cities.
"""

import requests


INDIA_CITY_DEMOGRAPHICS = {
    "mumbai": {
        "city": "Mumbai",
        "country": "India",
        "population": 20667656,
        "area_sq_km": 603,
        "population_density_per_sq_km": 34258,
        "density_label": "Extremely High",
        "age_median": 28,
        "urban_percentage": 100,
        "literacy_rate": 89.7,
        "source": "Census of India 2011 (projected 2024)",
    },
    "delhi": {
        "city": "Delhi",
        "country": "India",
        "population": 32941000,
        "area_sq_km": 1484,
        "population_density_per_sq_km": 11320,
        "density_label": "Very High",
        "age_median": 26,
        "urban_percentage": 97.5,
        "literacy_rate": 86.2,
        "source": "Census of India 2011 (projected 2024)",
    },
    "bangalore": {
        "city": "Bangalore",
        "country": "India",
        "population": 13608582,
        "area_sq_km": 709,
        "population_density_per_sq_km": 19191,
        "density_label": "Very High",
        "age_median": 27,
        "urban_percentage": 99,
        "literacy_rate": 88.5,
        "source": "Census of India 2011 (projected 2024)",
    },
    "hyderabad": {
        "city": "Hyderabad",
        "country": "India",
        "population": 10534418,
        "area_sq_km": 625,
        "population_density_per_sq_km": 18600,
        "density_label": "Very High",
        "age_median": 27,
        "urban_percentage": 98,
        "literacy_rate": 83.2,
        "source": "Census of India 2011 (projected 2024)",
    },
    "pune": {
        "city": "Pune",
        "country": "India",
        "population": 7276000,
        "area_sq_km": 331,
        "population_density_per_sq_km": 22000,
        "density_label": "High",
        "age_median": 28,
        "urban_percentage": 97,
        "literacy_rate": 86.2,
        "source": "Census of India 2011 (projected 2024)",
    },
}

BANDRA_SPECIFIC = {
    "neighbourhood": "Bandra West",
    "parent_city": "Mumbai",
    "estimated_population": 125000,
    "area_sq_km": 3.5,
    "population_density_per_sq_km": 35714,
    "density_label": "Extremely High",
    "profile": "Upscale residential and commercial neighbourhood; known as the 'Queen of Suburbs'",
    "foot_traffic": "Very High — major retail, dining and nightlife hub",
    "demographics_notes": [
        "Mix of upper-middle and affluent residents",
        "Large expat and NRI population",
        "Young professional demographic (25–40 dominant)",
        "Home to Bollywood celebrities and media professionals",
        "Significant tourist and visitor footfall"
    ],
    "source": "BMC ward data and local surveys 2023",
}


def fetch_demographics(location: str, country_code: str = "IN") -> dict:
    """
    Fetches demographic data for a given location.
    Uses curated data for Indian cities, World Bank API for others.
    """
    location_lower = location.lower()

    if "bandra" in location_lower:
        city_data = INDIA_CITY_DEMOGRAPHICS.get("mumbai", {}).copy()
        city_data["neighbourhood_data"] = BANDRA_SPECIFIC
        city_data["location_queried"] = location
        return city_data

    for city_key, city_data in INDIA_CITY_DEMOGRAPHICS.items():
        if city_key in location_lower:
            return {**city_data, "location_queried": location}

    if country_code == "IN":
        return _worldbank_demographics(location, "IND") or _generic_india_fallback(location)

    return _worldbank_demographics(location, country_code) or {
        "location_queried": location,
        "note": "Demographic data not available for this location",
    }


def _worldbank_demographics(location: str, wb_country_code: str) -> dict | None:
    """Fetches population data from World Bank API."""
    try:
        url = f"https://api.worldbank.org/v2/country/{wb_country_code}/indicator/SP.POP.TOTL"
        resp = requests.get(url, params={"format": "json", "mrv": 1}, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if len(data) > 1 and data[1]:
                latest = data[1][0]
                return {
                    "location_queried": location,
                    "country_code": wb_country_code,
                    "total_population": latest.get("value"),
                    "year": latest.get("date"),
                    "source": "World Bank API",
                }
    except Exception:
        pass
    return None


def _generic_india_fallback(location: str) -> dict:
    return {
        "location_queried": location,
        "country": "India",
        "note": "Specific city data unavailable; using India national averages",
        "total_population": 1428627663,
        "urban_percentage": 36.4,
        "median_age": 28.2,
        "source": "World Bank / Census of India",
    }
