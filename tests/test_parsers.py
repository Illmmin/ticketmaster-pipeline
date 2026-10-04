import pytest
from src.api.parsers import parse_event, parse_attraction


MOCK_EVENT = {
    "id": "vvG1zZ9bXqlJ0x",
    "name": "Imagine Dragons - LOOM World Tour",
    "url": "https://www.ticketmaster.fr/event/imagine-dragons",
    "lastUpdated": "2024-03-01T10:00:00Z",
    "dates": {
        "start": {"localDate": "2024-07-15"},
        "status": {"code": "onsale"},
    },
    "priceRanges": [
        {"type": "standard", "currency": "EUR", "min": 45.0, "max": 120.0}
    ],
    "classifications": [
        {
            "segment": {"name": "Music"},
            "genre": {"name": "Rock"},
            "subGenre": {"name": "Alternative Rock"},
        }
    ],
    "_embedded": {
        "venues": [
            {
                "name": "Stade de France",
                "city": {"name": "Paris"},
                "country": {"countryCode": "FR"},
            }
        ],
        "attractions": [
            {"id": "K8vZ917Gku7", "name": "Imagine Dragons"}
        ],
    },
}

MOCK_EVENT_NO_DATE = {
    "id": "abc123",
    "dates": {"start": {}},
}


class TestParseEvent:
    def test_parse_full_event(self):
        result = parse_event(MOCK_EVENT)
        assert result is not None
        assert result["event_id"] == "vvG1zZ9bXqlJ0x"
        assert result["artist_name"] == "Imagine Dragons"
        assert result["genre"] == "Rock"
        assert result["price_min"] == 45.0
        assert result["price_max"] == 120.0
        assert result["currency"] == "EUR"
        assert result["city"] == "Paris"
        assert result["country"] == "FR"
        assert result["event_date"] == "2024-07-15"
        assert result["status"] == "onsale"

    def test_parse_event_without_date_returns_none(self):
        result = parse_event(MOCK_EVENT_NO_DATE)
        assert result is None

    def test_parse_event_without_price(self):
        event = {**MOCK_EVENT, "priceRanges": []}
        result = parse_event(event)
        assert result["price_min"] is None
        assert result["price_max"] is None

    def test_parse_event_without_attraction(self):
        event = dict(MOCK_EVENT)
        event["_embedded"] = {**MOCK_EVENT["_embedded"], "attractions": []}
        result = parse_event(event)
        assert result["artist_id"] is None
        assert result["artist_name"] is None


MOCK_ATTRACTION = {
    "id": "K8vZ917Gku7",
    "name": "Imagine Dragons",
    "classifications": [
        {
            "genre": {"name": "Rock"},
            "subGenre": {"name": "Alternative Rock"},
        }
    ],
    "images": [{"url": "https://cdn.ticketmaster.com/imagine-dragons.jpg"}],
    "externalLinks": {
        "spotify": [{"url": "https://open.spotify.com/artist/53XhwfbYqKCa1cC15pYq2q"}]
    },
}


class TestParseAttraction:
    def test_parse_full_attraction(self):
        result = parse_attraction(MOCK_ATTRACTION)
        assert result["artist_id"] == "K8vZ917Gku7"
        assert result["name"] == "Imagine Dragons"
        assert result["genre"] == "Rock"
        assert "spotify" in result["spotify_url"]
        assert result["image_url"] is not None

    def test_parse_attraction_no_links(self):
        attraction = {**MOCK_ATTRACTION, "externalLinks": {}, "images": []}
        result = parse_attraction(attraction)
        assert result["spotify_url"] is None
        assert result["image_url"] is None
