"""
Earnings / Income Tool
Fetches average household income and spending data for a location.
Uses curated data for Indian cities + World Bank GDP per capita fallback.
"""

import requests


INDIA_INCOME_DATA = {
    "mumbai": {
        "city": "Mumbai",
        "avg_monthly_household_income_inr": 58000,
        "avg_annual_household_income_inr": 696000,
        "median_monthly_income_inr": 38000,
        "per_capita_monthly_income_inr": 14500,
        "income_tier": "High",
        "consumer_spending_index": 142,
        "retail_spending_propensity": "High",
        "gifting_spend_per_occasion_inr": 2500,
        "annual_gifting_market_estimate_cr": 3200,
        "source": "NSSO, CMIE, BCG India Consumer Report 2024",
    },
    "bandra": {
        "neighbourhood": "Bandra West, Mumbai",
        "avg_monthly_household_income_inr": 120000,
        "avg_annual_household_income_inr": 1440000,
        "income_tier": "Upper-Middle to Affluent",
        "consumer_spending_index": 210,
        "retail_spending_propensity": "Very High",
        "gifting_spend_per_occasion_inr": 5000,
        "discretionary_spend_pct": 45,
        "notes": [
            "Premium retail corridor with high disposable income",
            "High propensity for experiential and gifting purchases",
            "Significant NRI remittance income inflates purchasing power",
            "Major festivals (Diwali, Christmas) drive 35–40% of annual gifting spend"
        ],
        "annual_gifting_market_estimate_bandra_cr": 180,
        "source": "CMIE, local market surveys, Redseer Retail Report 2024",
    },
    "delhi": {
        "city": "Delhi",
        "avg_monthly_household_income_inr": 52000,
        "avg_annual_household_income_inr": 624000,
        "income_tier": "High",
        "consumer_spending_index": 130,
        "retail_spending_propensity": "High",
        "gifting_spend_per_occasion_inr": 2200,
        "source": "NSSO, CMIE 2024",
    },
    "bangalore": {
        "city": "Bangalore",
        "avg_monthly_household_income_inr": 65000,
        "avg_annual_household_income_inr": 780000,
        "income_tier": "High",
        "consumer_spending_index": 148,
        "retail_spending_propensity": "High",
        "gifting_spend_per_occasion_inr": 2800,
        "source": "NSSO, CMIE 2024",
    },
    "hyderabad": {
        "city": "Hyderabad",
        "avg_monthly_household_income_inr": 48000,
        "avg_annual_household_income_inr": 576000,
        "income_tier": "Upper-Middle",
        "consumer_spending_index": 118,
        "retail_spending_propensity": "Moderate-High",
        "gifting_spend_per_occasion_inr": 1800,
        "source": "NSSO, CMIE 2024",
    },
    "pune": {
        "city": "Pune",
        "avg_monthly_household_income_inr": 55000,
        "avg_annual_household_income_inr": 660000,
        "income_tier": "High",
        "consumer_spending_index": 135,
        "retail_spending_propensity": "High",
        "gifting_spend_per_occasion_inr": 2300,
        "source": "NSSO, CMIE 2024",
    },
}

INDIA_GIFTING_MARKET = {
    "india_gifting_market_size_2024_usd_bn": 93,
    "india_gifting_market_size_2024_inr_cr": 772000,
    "cagr_2024_2029_pct": 12.5,
    "organised_segment_pct": 22,
    "online_gifting_pct": 38,
    "key_occasions": ["Diwali", "Raksha Bandhan", "Weddings", "Birthdays", "Christmas/New Year"],
    "premium_gifting_growth_pct": 18,
    "source": "IMARC Group India Gifting Market Report 2024",
}


def fetch_earnings(location: str, country_code: str = "IN") -> dict:
    """
    Fetches income and spending data for a given location.
    """
    location_lower = location.lower()

    result = {}

    if "bandra" in location_lower:
        result = INDIA_INCOME_DATA.get("bandra", {}).copy()
        result["parent_city_data"] = INDIA_INCOME_DATA.get("mumbai", {})
        result["india_gifting_market"] = INDIA_GIFTING_MARKET
        result["location_queried"] = location
        return result

    for city_key, city_data in INDIA_INCOME_DATA.items():
        if city_key in location_lower:
            result = city_data.copy()
            result["india_gifting_market"] = INDIA_GIFTING_MARKET
            result["location_queried"] = location
            return result

    if country_code == "IN":
        wb_data = _worldbank_gdp_per_capita(location, "IND")
        if wb_data:
            wb_data["india_gifting_market"] = INDIA_GIFTING_MARKET
            return wb_data

    return _worldbank_gdp_per_capita(location, country_code) or {
        "location_queried": location,
        "note": "Income data not available for this location",
    }


def _worldbank_gdp_per_capita(location: str, wb_country_code: str) -> dict | None:
    """Fetches GDP per capita from World Bank as a proxy for earnings."""
    try:
        url = f"https://api.worldbank.org/v2/country/{wb_country_code}/indicator/NY.GDP.PCAP.CD"
        resp = requests.get(url, params={"format": "json", "mrv": 1}, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if len(data) > 1 and data[1]:
                latest = data[1][0]
                return {
                    "location_queried": location,
                    "country_code": wb_country_code,
                    "gdp_per_capita_usd": latest.get("value"),
                    "year": latest.get("date"),
                    "source": "World Bank API",
                }
    except Exception:
        pass
    return None
