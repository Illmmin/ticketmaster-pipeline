import logging
from typing import Optional

logger = logging.getLogger(__name__)


class EventRepository:
    def __init__(self, conn):
        self.conn = conn

    def upsert_event(self, event: dict):
        """Insère ou met à jour un event (idempotent)."""
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO raw_events (
                    event_id, name, artist_id, artist_name,
                    venue_name, city, country, event_date,
                    segment, genre, subgenre,
                    price_min, price_max, currency,
                    url, status, last_updated, ingested_at
                ) VALUES (
                    %(event_id)s, %(name)s, %(artist_id)s, %(artist_name)s,
                    %(venue_name)s, %(city)s, %(country)s, %(event_date)s,
                    %(segment)s, %(genre)s, %(subgenre)s,
                    %(price_min)s, %(price_max)s, %(currency)s,
                    %(url)s, %(status)s, %(last_updated)s, %(ingested_at)s
                )
                ON CONFLICT (event_id) DO UPDATE SET
                    name            = EXCLUDED.name,
                    price_min       = EXCLUDED.price_min,
                    price_max       = EXCLUDED.price_max,
                    status          = EXCLUDED.status,
                    last_updated    = EXCLUDED.last_updated,
                    ingested_at     = EXCLUDED.ingested_at
                WHERE raw_events.last_updated IS DISTINCT FROM EXCLUDED.last_updated
                """,
                event,
            )
        self.conn.commit()

    def upsert_events_batch(self, events: list[dict]):
        inserted = updated = skipped = 0
        for event in events:
            if event is None:
                skipped += 1
                continue
            try:
                self.upsert_event(event)
                inserted += 1
            except Exception as e:
                logger.error(f"Erreur upsert event {event.get('event_id')}: {e}")
                self.conn.rollback()
        logger.info(f"Batch events → {inserted} upserts, {skipped} ignorés")

    def get_events_needing_refresh(self, days_old: int = 1) -> list[str]:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT event_id FROM raw_events
                WHERE event_date >= CURRENT_DATE
                  AND (
                    ingested_at < NOW() - INTERVAL '%s days'
                    OR price_min IS NULL
                  )
                ORDER BY event_date ASC
                LIMIT 500
                """,
                (days_old,),
            )
            return [row[0] for row in cur.fetchall()]


class ArtistRepository:
    def __init__(self, conn):
        self.conn = conn

    def upsert_artist(self, artist: dict):
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO artists (
                    artist_id, name, genre, subgenre,
                    image_url, spotify_url, updated_at
                ) VALUES (
                    %(artist_id)s, %(name)s, %(genre)s, %(subgenre)s,
                    %(image_url)s, %(spotify_url)s, %(updated_at)s
                )
                ON CONFLICT (artist_id) DO UPDATE SET
                    name        = EXCLUDED.name,
                    genre       = EXCLUDED.genre,
                    image_url   = EXCLUDED.image_url,
                    spotify_url = EXCLUDED.spotify_url,
                    updated_at  = EXCLUDED.updated_at
                """,
                artist,
            )
        self.conn.commit()

    def get_unknown_artists(self) -> list[str]:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT e.artist_id
                FROM raw_events e
                LEFT JOIN artists a ON e.artist_id = a.artist_id
                WHERE e.artist_id IS NOT NULL
                  AND a.artist_id IS NULL
                LIMIT 200
                """
            )
            return [row[0] for row in cur.fetchall()]
