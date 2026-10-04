import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise EnvironmentError(
            f"Variable d'environnement manquante : {name}. "
            f"Vérifie ton fichier .env (voir .env.example)."
        )
    return value


@dataclass(frozen=True)
class TicketmasterConfig:
    api_key: str
    base_url: str = "https://app.ticketmaster.com/discovery/v2"
    daily_quota: int = 5000          # quota gratuit officiel
    requests_per_second: float = 5.0  # limite du tier gratuit (rate limiting)


@dataclass(frozen=True)
class BigQueryConfig:
    project_id: str
    dataset: str
    credentials_path: str    
    raw_table: str = "raw_events"
    location: str = "EU"     


def load_ticketmaster_config() -> TicketmasterConfig:
    return TicketmasterConfig(api_key=_require("TICKETMASTER_API_KEY"))


def load_bigquery_config() -> BigQueryConfig:
    return BigQueryConfig(
        project_id=_require("GCP_PROJECT_ID"),
        dataset=_require("BIGQUERY_DATASET"),
        credentials_path=_require("GOOGLE_APPLICATION_CREDENTIALS"),
        location=os.getenv("BIGQUERY_LOCATION", "EU"),
    )