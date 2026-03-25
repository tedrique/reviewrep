"""Google Business Profile API — fetch reviews and post replies."""
import requests


GBP_API = "https://mybusinessaccountmanagement.googleapis.com/v1"
GBP_BIZ_API = "https://mybusiness.googleapis.com/v4"


def get_accounts(access_token: str) -> list[dict]:
    """Get all Google Business accounts for the user."""
    resp = requests.get(
        f"{GBP_API}/accounts",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    if not resp.ok:
        print(f"[GBP] accounts error: {resp.status_code} {resp.text[:200]}")
        return []
    data = resp.json()
    return data.get("accounts", [])


def get_locations(access_token: str, account_name: str) -> list[dict]:
    """Get all locations (businesses) for an account."""
    resp = requests.get(
        f"{GBP_BIZ_API}/{account_name}/locations",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    if not resp.ok:
        print(f"[GBP] locations error: {resp.status_code} {resp.text[:200]}")
        return []
    data = resp.json()
    return data.get("locations", [])


def get_reviews(access_token: str, location_name: str, page_size: int = 50) -> list[dict]:
    """Fetch reviews for a specific location."""
    resp = requests.get(
        f"{GBP_BIZ_API}/{location_name}/reviews",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"pageSize": page_size, "orderBy": "updateTime desc"},
        timeout=15,
    )
    if not resp.ok:
        print(f"[GBP] reviews error: {resp.status_code} {resp.text[:200]}")
        return []
    data = resp.json()
    reviews = []
    for r in data.get("reviews", []):
        reviews.append({
            "google_review_id": r.get("reviewId", r.get("name", "")),
            "author": r.get("reviewer", {}).get("displayName", "Customer"),
            "rating": _star_to_int(r.get("starRating", "FIVE")),
            "text": r.get("comment", ""),
            "time": r.get("updateTime", r.get("createTime", "")),
            "has_reply": bool(r.get("reviewReply")),
            "existing_reply": r.get("reviewReply", {}).get("comment", ""),
        })
    return reviews


def post_reply(access_token: str, review_name: str, reply_text: str) -> bool:
    """Post a reply to a specific review."""
    resp = requests.put(
        f"{GBP_BIZ_API}/{review_name}/reply",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        json={"comment": reply_text},
        timeout=10,
    )
    if not resp.ok:
        print(f"[GBP] reply error: {resp.status_code} {resp.text[:200]}")
        return False
    return True


def refresh_access_token(refresh_token: str, client_id: str, client_secret: str) -> str | None:
    """Refresh an expired access token."""
    resp = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "refresh_token",
        },
        timeout=10,
    )
    if resp.ok:
        return resp.json().get("access_token")
    print(f"[GBP] token refresh error: {resp.status_code} {resp.text[:200]}")
    return None


def _star_to_int(star_rating: str) -> int:
    mapping = {"ONE": 1, "TWO": 2, "THREE": 3, "FOUR": 4, "FIVE": 5}
    return mapping.get(star_rating, 5)
