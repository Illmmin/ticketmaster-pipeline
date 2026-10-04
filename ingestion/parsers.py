"""
Normalisation des événements bruts de l'API Ticketmaster vers des dicts plats,
prêts à être chargés dans la table RAW de BigQuery
"""
from datetime import datetime, timezone
from typing import Any


def parse_event(raw_event: dict[str, Any]) -> dict[str, Any]:
    """
    Extrait les champs utiles d'un événement brut.
    Conserve aussi le JSON brut complet (utile pour le type JSON natif de BigQuery
    et le flattening côté dbt).
    """
    dates = raw_event.get("dates", {}).get("start", {})
    classifications = raw_event.get("classifications", [{}])[0]
    price_ranges = raw_event.get("priceRanges", [{}])
    venues = raw_event.get("_embedded", {}).get("venues", [{}])
    attractions = raw_event.get("_embedded", {}).get("attractions", [])

    venue = venues[0] if venues else {}
    price = price_ranges[0] if price_ranges else {}

    return {
        "event_id": raw_event.get("id"),
        "name": raw_event.get("name"),
        "url": raw_event.get("url"),
        "start_date": dates.get("localDate"),
        "start_time": dates.get("localTime"),
        "status": raw_event.get("dates", {}).get("status", {}).get("code"),
        "genre": classifications.get("genre", {}).get("name"),
        "segment": classifications.get("segment", {}).get("name"),
        "sub_genre": classifications.get("subGenre", {}).get("name"),
        "price_min": price.get("min"),
        "price_max": price.get("max"),
        "currency": price.get("currency"),
        "venue_id": venue.get("id"),
        "venue_name": venue.get("name"),
        "artist_ids": [a.get("id") for a in attractions if a.get("id")],
        "artist_names": [a.get("name") for a in attractions if a.get("name")],
        "ingested_at": datetime.now(timezone.utc).isoformat(),
        "raw_payload": raw_event,  # gardé tel quel pour le type JSON BigQuery
    }


def parse_venue(raw_event: dict[str, Any]) -> dict[str, Any] | None:
    venues = raw_event.get("_embedded", {}).get("venues", [])
    if not venues:
        return None
    venue = venues[0]
    city = venue.get("city", {})
    country = venue.get("country", {})
    return {
        "venue_id": venue.get("id"),
        "name": venue.get("name"),
        "city": city.get("name"),
        "country_code": country.get("countryCode"),
        "postal_code": venue.get("postalCode"),
        "timezone": venue.get("timezone"),
    }


def parse_artists(raw_event: dict[str, Any]) -> list[dict[str, Any]]:
    attractions = raw_event.get("_embedded", {}).get("attractions", [])
    artists = []
    for a in attractions:
        classifications = a.get("classifications", [{}])[0]
        artists.append(
            {
                "artist_id": a.get("id"),
                "name": a.get("name"),
                "genre": classifications.get("genre", {}).get("name"),
                "segment": classifications.get("segment", {}).get("name"),
            }
        )
    return artists