"""
Google Maps review scraper.
Fetches reviews for a business using Google Maps place_id via the public API.
"""
import re
import json
import requests
from dataclasses import dataclass


@dataclass
class Review:
    author: str
    rating: int
    text: str
    time: str
    review_id: str


def get_place_id(business_name: str, location: str) -> str | None:
    """Search Google Maps for a business and return its place_id."""
    query = f"{business_name} {location}"
    url = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json"
    # For MVP we use the free textsearch approach via scraping
    # This is a simplified version
    search_url = f"https://www.google.com/maps/search/{requests.utils.quote(query)}"
    try:
        resp = requests.get(search_url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }, timeout=10, allow_redirects=True)
        # Extract place ID from redirected URL
        match = re.search(r"place/[^/]+/[^/]+/data=.*!1s(0x[a-f0-9]+:[a-f0-9]+)", resp.url)
        if match:
            return match.group(1)
        # Try alternate pattern
        match = re.search(r"!1s(ChIJ[A-Za-z0-9_-]+)", resp.text)
        if match:
            return match.group(1)
    except Exception as e:
        print(f"Place search failed: {e}")
    return None


def fetch_reviews_serpapi(place_id: str, api_key: str = "") -> list[Review]:
    """
    Fetch reviews using SerpAPI (has free tier: 100 searches/month).
    Alternative: we can scrape directly but it's less reliable.
    """
    if not api_key:
        return []

    url = "https://serpapi.com/search.json"
    params = {
        "engine": "google_maps_reviews",
        "place_id": place_id,
        "api_key": api_key,
        "sort_by": "newestFirst",
        "hl": "en",
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        data = resp.json()
        reviews = []
        for r in data.get("reviews", []):
            reviews.append(Review(
                author=r.get("user", {}).get("name", "Customer"),
                rating=r.get("rating", 0),
                text=r.get("snippet", r.get("extracted_snippet", {}).get("original", "")),
                time=r.get("date", ""),
                review_id=r.get("review_id", str(hash(r.get("snippet", "")))),
            ))
        return reviews
    except Exception as e:
        print(f"SerpAPI fetch failed: {e}")
        return []


def fetch_reviews_direct(place_data_id: str) -> list[Review]:
    """
    Fetch reviews by scraping Google Maps directly.
    Uses the public Google Maps data endpoint.
    """
    url = f"https://www.google.com/maps/preview/review/listentitiesreviews"
    # This approach uses Google's internal API - simplified for MVP
    # In production, use Google Business Profile API or SerpAPI

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept-Language": "en-GB,en;q=0.9",
    }

    # Fallback: try Google Maps place page
    try:
        search_url = f"https://www.google.com/maps/place/?q=place_id:{place_data_id}"
        resp = requests.get(search_url, headers=headers, timeout=10)

        # Extract review data from page (simplified parser)
        reviews = []
        # Look for review JSON blocks in the page source
        pattern = r'"([^"]{2,50})",\s*(\d)\s*,\s*"([^"]{10,500})"'
        matches = re.findall(pattern, resp.text)

        for i, (author, rating, text) in enumerate(matches[:10]):
            if int(rating) >= 1 and int(rating) <= 5 and len(text) > 20:
                reviews.append(Review(
                    author=author,
                    rating=int(rating),
                    text=text,
                    time="Recent",
                    review_id=f"direct_{hash(text)}",
                ))
        return reviews
    except Exception as e:
        print(f"Direct fetch failed: {e}")
        return []


# --- Manual input mode (most reliable for MVP) ---
def create_review_from_input(author: str, rating: int, text: str) -> Review:
    """Create a review from manual input — most reliable for MVP."""
    return Review(
        author=author,
        rating=rating,
        text=text,
        time="Now",
        review_id=f"manual_{hash(text)}",
    )
