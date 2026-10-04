import argparse
import logging
import os
import sys
from datetime import datetime, timedelta

import psycopg2
from dotenv import load_dotenv

from src.api.client import TicketmasterClient, QuotaExhaustedError
from src.api.parsers import parse_event, parse_attraction
from src.db.repository import EventRepository, ArtistRepository
from src.db.quota import QuotaManager

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/pipeline.log"),
    ],
)
logger = logging.getLogger(__name__)

DEFAULT_GENRES = [
    "Rock", "Pop", "Hip-Hop", "Jazz", "Electronic",
    "R&B", "Metal", "Classical", "Country", "Reggae",
]

DEFAULT_COUNTRIES = ["FR", "BE", "CH"]


def get_db_connection():
    return psycopg2.connect(
        host=os.environ["DB_HOST"],
        port=os.environ.get("DB_PORT", 5432),
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
    )


def step_fetch_events(client: TicketmasterClient, event_repo: EventRepository, args):
    """Étape 1 : fetch et stockage des events par genre et pays."""
    genres = args.genres or DEFAULT_GENRES
    countries = args.countries or DEFAULT_COUNTRIES
    total = 0

    start = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    end = (datetime.utcnow() + timedelta(days=180)).strftime("%Y-%m-%dT%H:%M:%SZ")

    for country in countries:
        for genre in genres:
            logger.info(f"Fetch events → {genre} / {country}")
            try:
                raw_events = client.paginate_events(
                    country_code=country,
                    classification_name=genre,
                    start_date_time=start,
                    end_date_time=end,
                )
                parsed = [parse_event(e) for e in raw_events]
                event_repo.upsert_events_batch(parsed)
                total += len(parsed)
                logger.info(f"  → {len(parsed)} events ingérés ({genre}/{country})")

            except QuotaExhaustedError:
                logger.error("Quota épuisé ! Arrêt du step fetch_events.")
                return total

    logger.info(f"Step fetch_events terminé : {total} events au total.")
    return total


def step_refresh_prices(client: TicketmasterClient, event_repo: EventRepository):
    """
    Étape 2 : refresh des prix pour les events dont les données sont vieilles
    ou dont on n'avait pas le prix lors de la première ingestion.
    """
    event_ids = event_repo.get_events_needing_refresh(days_old=1)
    logger.info(f"Step refresh_prices : {len(event_ids)} events à rafraîchir.")
    refreshed = 0

    for eid in event_ids:
        try:
            raw = client.get_event_detail(eid)
            parsed = parse_event(raw)
            if parsed:
                event_repo.upsert_event(parsed)
                refreshed += 1
        except QuotaExhaustedError:
            logger.warning("Quota épuisé pendant refresh_prices.")
            break
        except Exception as e:
            logger.warning(f"Erreur refresh event {eid}: {e}")

    logger.info(f"Step refresh_prices terminé : {refreshed}/{len(event_ids)} refreshés.")
    return refreshed


def step_enrich_artists(client: TicketmasterClient, artist_repo: ArtistRepository):
    """Étape 3 : enrichissement des artistes non encore connus."""
    artist_ids = artist_repo.get_unknown_artists()
    logger.info(f"Step enrich_artists : {len(artist_ids)} artistes à enrichir.")
    enriched = 0

    for aid in artist_ids:
        try:
            raw = client.get_attraction(aid)
            parsed = parse_attraction(raw)
            artist_repo.upsert_artist(parsed)
            enriched += 1
        except QuotaExhaustedError:
            logger.warning("Quota épuisé pendant enrich_artists.")
            break
        except Exception as e:
            logger.warning(f"Erreur enrichissement artiste {aid}: {e}")

    logger.info(f"Step enrich_artists terminé : {enriched}/{len(artist_ids)} enrichis.")
    return enriched


def main():
    parser = argparse.ArgumentParser(description="Ticketmaster ingestion pipeline")
    parser.add_argument("--genres", nargs="+", help="Genres à fetcher")
    parser.add_argument("--countries", nargs="+", help="Pays à fetcher (codes ISO)")
    parser.add_argument("--refresh-prices", action="store_true")
    parser.add_argument("--enrich-artists", action="store_true")
    parser.add_argument("--full", action="store_true", help="Run complet (tous les steps)")
    args = parser.parse_args()

    run_all = args.full or not any([args.refresh_prices, args.enrich_artists])

    logger.info("=" * 60)
    logger.info("Démarrage du pipeline Ticketmaster")
    logger.info("=" * 60)

    conn = get_db_connection()
    api_key = os.environ["TICKETMASTER_API_KEY"]

    client = TicketmasterClient(api_key=api_key, db_conn=conn)
    event_repo = EventRepository(conn)
    artist_repo = ArtistRepository(conn)
    quota = QuotaManager(conn)

    logger.info(f"Quota disponible : {quota.get_remaining_quota()}/5000 appels restants aujourd'hui.")

    try:
        if run_all or not args.refresh_prices:
            step_fetch_events(client, event_repo, args)

        if run_all or args.refresh_prices:
            step_refresh_prices(client, event_repo)

        if run_all or args.enrich_artists:
            step_enrich_artists(client, artist_repo)

    finally:
        conn.close()
        logger.info(f"Pipeline terminé. Appels utilisés aujourd'hui : {5000 - quota.get_remaining_quota()}")


if __name__ == "__main__":
    main()
