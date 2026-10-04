"""
Client pour l'API Ticketmaster Discovery.
"""
import logging
import time
from datetime import date
from typing import Any, Iterator

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config import TicketmasterConfig

logger = logging.getLogger(__name__)


class QuotaExceededError(Exception):
    """Levée quand le quota journalier d'appels API est atteint."""


class TicketmasterAPIError(Exception):
    """Erreur générique renvoyée par l'API (hors erreurs réseau/HTTP transitoires)."""


class QuotaTracker:
    """Suivi simple du nombre d'appels effectués dans la journée en cours."""

    def __init__(self, daily_quota: int):
        self.daily_quota = daily_quota
        self._count = 0
        self._day = date.today()

    def _reset_if_new_day(self) -> None:
        today = date.today()
        if today != self._day:
            self._day = today
            self._count = 0

    def register_call(self) -> None:
        self._reset_if_new_day()
        if self._count >= self.daily_quota:
            raise QuotaExceededError(
                f"Quota journalier atteint ({self.daily_quota} appels)."
            )
        self._count += 1

    @property
    def remaining(self) -> int:
        self._reset_if_new_day()
        return max(0, self.daily_quota - self._count)


class TicketmasterClient:
    def __init__(self, config: TicketmasterConfig):
        self.config = config
        self.session = requests.Session()
        self.quota = QuotaTracker(config.daily_quota)
        self._min_interval = 1.0 / config.requests_per_second
        self._last_call_ts: float = 0.0

    def _throttle(self) -> None:
        """Impose un espacement minimal entre deux appels (rate limiting)."""
        elapsed = time.monotonic() - self._last_call_ts
        wait_time = self._min_interval - elapsed
        if wait_time > 0:
            time.sleep(wait_time)
        self._last_call_ts = time.monotonic()

    @retry(
        retry=retry_if_exception_type(
            (requests.exceptions.ConnectionError, requests.exceptions.Timeout)
        ),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(5),
        reraise=True,
    )
    def _get(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        self.quota.register_call()
        self._throttle()

        url = f"{self.config.base_url}/{endpoint}"
        params = {**params, "apikey": self.config.api_key}

        response = self.session.get(url, params=params, timeout=10)

        if response.status_code == 429:
            # Quota/rate limit côté serveur : on attend puis on laisse tenacity retenter
            retry_after = int(response.headers.get("Retry-After", 5))
            logger.warning("429 reçu, pause de %ss avant retry", retry_after)
            time.sleep(retry_after)
            response.raise_for_status()

        if response.status_code >= 500:
            # Erreur serveur transitoire : on la traite comme retryable
            response.raise_for_status()

        if not response.ok:
            raise TicketmasterAPIError(
                f"Erreur API {response.status_code} sur {endpoint} : {response.text[:300]}"
            )

        return response.json()

    def search_events(
        self,
        *,
        city: str | None = None,
        country_code: str | None = None,
        classification_name: str | None = None,
        start_date_time: str | None = None,
        end_date_time: str | None = None,
        page_size: int = 200,
        max_pages: int | None = None,
    ) -> Iterator[dict[str, Any]]:
        """
        Génère les événements page par page pour ne pas tout charger en mémoire.
        Un seul appel API par page consommée.
        """
        params: dict[str, Any] = {"size": page_size}
        if city:
            params["city"] = city
        if country_code:
            params["countryCode"] = country_code
        if classification_name:
            params["classificationName"] = classification_name
        if start_date_time:
            params["startDateTime"] = start_date_time
        if end_date_time:
            params["endDateTime"] = end_date_time

        page = 0
        while True:
            if max_pages is not None and page >= max_pages:
                return

            data = self._get("events.json", {**params, "page": page})
            embedded = data.get("_embedded", {})
            events = embedded.get("events", [])

            if not events:
                return

            for event in events:
                yield event

            page_info = data.get("page", {})
            total_pages = page_info.get("totalPages", 1)
            page += 1
            if page >= total_pages:
                return