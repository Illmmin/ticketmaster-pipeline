from datetime import datetime
from typing import Optional


def parse_event(raw: dict) -> dict:
    # --- Date ---
    dates = raw.get("dates", {}).get("start", {})
    event_date = dates.get("localDate")  # format YYYY-MM-DD
    if not event_date:
        return None

    # --- Prix ---
    price_ranges = raw.get("priceRanges", [])
    price_min = price_max = currency = None
    if price_ranges:
        pr = price_ranges[0]
        price_min = pr.get("min")
        price_max = pr.get("max")
        currency = pr.get("currency")

    # --- Lieu ---
    venues = raw.get("_embedded", {}).get("venues", [{}])
    venue = venues[0] if venues else {}
    venue_name = venue.get("name")
    city = venue.get("city", {}).get("name")
    country = venue.get("country", {}).get("countryCode")

    # --- Artiste principal ---
    attractions = raw.get("_embedded", {}).get("attractions", [])
    artist_id = artist_name = None
    if attractions:
        artist_id = attractions[0].get("id")
        artist_name = attractions[0].get("name")

    # --- Genre ---
    classifications = raw.get("classifications", [{}])
    classif = classifications[0] if classifications else {}
    genre = classif.get("genre", {}).get("name")
    subgenre = classif.get("subGenre", {}).get("name")
    segment = classif.get("segment", {}).get("name") 
    return {
        "event_id": raw["id"],
        "name": raw.get("name"),
        "artist_id": artist_id,
        "artist_name": artist_name,
        "venue_name": venue_name,
        "city": city,
        "country": country,
        "event_date": event_date,
        "segment": segment,
        "genre": genre,
        "subgenre": subgenre,
        "price_min": price_min,
        "price_max": price_max,
        "currency": currency,
        "url": raw.get("url"),
        "status": raw.get("dates", {}).get("status", {}).get("code"),
        "last_updated": raw.get("lastUpdated"),
        "ingested_at": datetime.utcnow().isoformat(),
    }


def parse_attraction(raw: dict) -> dict:
    """Extrait les infos d'un artiste / attraction."""
    classifications = raw.get("classifications", [{}])
    classif = classifications[0] if classifications else {}

    images = raw.get("images", [])
    image_url = images[0].get("url") if images else None

    external_links = raw.get("externalLinks", {})
    spotify_url = None
    if "spotify" in external_links:
        spotify_url = external_links["spotify"][0].get("url")

    return {
        "artist_id": raw["id"],
        "name": raw.get("name"),
        "genre": classif.get("genre", {}).get("name"),
        "subgenre": classif.get("subGenre", {}).get("name"),
        "image_url": image_url,
        "spotify_url": spotify_url,
        "updated_at": datetime.utcnow().isoformat(),
    }
