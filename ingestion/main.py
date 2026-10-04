"""
Point d'entrée de l'ingestion. Appelé en local pour tester, ou par le
DAG Airflow (PythonOperator) en production.

Exemple : python main.py --city Paris --country-code GB
"""
import argparse
import logging

from api_client import QuotaExceededError, TicketmasterAPIError, TicketmasterClient
from bigquery_loader import BigQueryLoader
from config import load_bigquery_config, load_ticketmaster_config
from parsers import parse_event

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


def run(city: str | None, country_code: str | None, max_pages: int | None) -> None:
    tm_config = load_ticketmaster_config()
    bq_config = load_bigquery_config()

    client = TicketmasterClient(tm_config)
    loader = BigQueryLoader(bq_config)
    loader.ensure_objects_exist()

    logger.info("Quota restant avant run : %s", client.quota.remaining)

    parsed_events = []
    try:
        for raw_event in client.search_events(
            city=city, country_code=country_code, max_pages=max_pages
        ):
            parsed_events.append(parse_event(raw_event))
    except QuotaExceededError:
        logger.warning("Quota atteint en cours de run, chargement des events déjà collectés.")
    except TicketmasterAPIError:
        logger.exception("Erreur API non récupérable, arrêt du run.")
        raise

    logger.info("Événements collectés : %s", len(parsed_events))

    if parsed_events:
        loader.load_events(parsed_events)

    logger.info("Quota restant après run : %s", client.quota.remaining)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingestion Ticketmaster -> BigQuery")
    parser.add_argument("--city", default=None)
    parser.add_argument("--country-code", default="GB")
    parser.add_argument("--max-pages", type=int, default=None)
    args = parser.parse_args()

    run(city=args.city, country_code=args.country_code, max_pages=args.max_pages)


if __name__ == "__main__":
    main()