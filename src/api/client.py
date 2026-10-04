import time
import logging
from datetime import date
from typing import Optional

import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.db.quota import QuotaManager

logger = logging.getLogger(__name__)

BASE_URL = "https://app.ticketmaster.com/discovery/v2"
DAILY_LIMIT = 5000 #limite d'appels par jour autorisé par l'API
BUFFER = 100  # appels réservés pour les urgences


class RateLimitError(Exception):
    pass


class QuotaExhaustedError(Exception):
    pass


class TicketmasterClient:
    """
    Client API Ticketmaster avec :
    - Suivi du quota journalier
    - Retry automatique sur erreurs transitoires
    - Rate limiting (5 appels/seconde max selon leur doc)
    - Logging de chaque appel
    """

    def __init__(self, api_key: str, db_conn):
        self.api_key = api_key
        self.session = requests.Session()
        self.quota = QuotaManager(db_conn)
        self._last_call_time = 0.0

    def _throttle(self):
        """Assure un délai minimum entre les appels."""
        elapsed = time.time() - self._last_call_time
        min_interval = 0.2  # 200ms = max 5 req/sec
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        self._last_call_time = time.time()

    @retry(
        retry=retry_if_exception_type(RateLimitError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=60, max=300),
        before_sleep=lambda retry_state: logger.warning(
            f"Rate limit atteint, attente avant retry #{retry_state.attempt_number}"
        ),
    )
    def _get(self, endpoint: str, params: dict) -> dict:
        """Effectue un GET et gère les cas d'erreur."""
        calls_today = self.quota.get_calls_today()
        if calls_today >= DAILY_LIMIT - BUFFER:
            raise QuotaExhaustedError(
                f"Quota quasi-épuisé : {calls_today}/{DAILY_LIMIT} appels effectués aujourd'hui."
            )

        self._throttle()

        params["apikey"] = self.api_key
        url = f"{BASE_URL}/{endpoint}"

        try:
            response = self.session.get(url, params=params, timeout=10)
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Erreur réseau sur {url}: {e}")
            raise

        self.quota.log_call(endpoint, response.status_code)
        logger.debug(f"GET {endpoint} → {response.status_code} (quota: {calls_today + 1}/{DAILY_LIMIT})")

        if response.status_code == 429:
            raise RateLimitError("HTTP 429 : rate limit Ticketmaster atteint.")

        if response.status_code == 401:
            raise ValueError("Clé API invalide ou expirée.")

        response.raise_for_status()
        return response.json()

    def get_events(
        self,
        country_code: str = "FR",
        classification_name: Optional[str] = None,
        keyword: Optional[str] = None,
        start_date_time: Optional[str] = None,
        end_date_time: Optional[str] = None,
        size: int = 200,
        page: int = 0,
    ) -> dict:
        """Récupère une page d'événements selon les filtres."""
        params = {
            "countryCode": country_code,
            "size": size,
            "page": page,
            "sort": "date,asc",
        }
        if classification_name:
            params["classificationName"] = classification_name
        if keyword:
            params["keyword"] = keyword
        if start_date_time:
            params["startDateTime"] = start_date_time
        if end_date_time:
            params["endDateTime"] = end_date_time

        return self._get("events.json", params)

    def get_event_detail(self, event_id: str) -> dict:
        """Récupère le détail complet d'un event (incluant price ranges)."""
        return self._get(f"events/{event_id}.json", {})

    def get_attraction(self, attraction_id: str) -> dict:
        """Récupère les infos d'un artiste / attraction."""
        return self._get(f"attractions/{attraction_id}.json", {})

    def paginate_events(self, **kwargs) -> list[dict]:
        """
        Itère automatiquement sur toutes les pages d'un appel /events.
        Retourne la liste complète des événements.
        Arrête si le quota est sur le point d'être épuisé.
        """
        all_events = []
        page = 0

        while True:
            try:
                data = self.get_events(page=page, **kwargs)
            except QuotaExhaustedError:
                logger.warning("Quota épuisé, pagination interrompue.")
                break

            embedded = data.get("_embedded", {})
            events = embedded.get("events", [])

            if not events:
                break

            all_events.extend(events)
            logger.info(f"Page {page} → {len(events)} events (total: {len(all_events)})")

            page_info = data.get("page", {})
            total_pages = page_info.get("totalPages", 1)
            if page >= total_pages - 1:
                break

            page += 1

        return all_events
