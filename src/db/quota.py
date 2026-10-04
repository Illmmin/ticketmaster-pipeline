"""
QuotaManager : persiste et consulte le nombre d'appels API effectués.
Stocke les logs dans PostgreSQL
"""

import logging
from datetime import date

logger = logging.getLogger(__name__)

class QuotaManager:

    def __init__(self, conn):
        self.conn = conn
    
    def get_calls_today(self):
        """Retourne le nombre d'appels effectués aujourd'hui."""
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) FROM api_calls_log
                WHERE called_at::date = CURRENT_DATE
                """
            )
            return cur.fetchone()[0]
    
    def log_call(self, endpoint: str, status_code: int):
        """Enregistre un appel API en base."""
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO api_calls_log (endpoint, status_code)
                VALUES (%s, %s)
                """,
                (endpoint, status_code)
            )
        self.conn.commit()

    def get_remaining_quota(self) -> int :
        """Quota restant pour aujourd'hui."""
        return 5000 - self.get_calls_today()

    def get_daily_stats(self) -> list[dict] :
        """statistiques d'usage par jour (7 derniers jours)."""
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    called_at::date AS day,
                    COUNT(*) AS total_calls,
                    COUNT(*) FILTER (WHERE status_code = 200) AS success,
                    COUNT(*) FILTER (WHERE status_code != 200) AS errors
                FROM api_calls_log
                WHERE called_at >= CURRENT_DATE - INTERVAL '7 days'
                GROUP BY 1
                ORDER BY 1 DESC
                """
            )
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]