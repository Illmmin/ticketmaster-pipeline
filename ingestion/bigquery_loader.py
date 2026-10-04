"""
Chargement des événements vers BigQuery.
"""
import json
import logging
import tempfile
import uuid
from pathlib import Path
from typing import Any, Iterable

from google.cloud import bigquery
from google.oauth2 import service_account

from config import BigQueryConfig

logger = logging.getLogger(__name__)

RAW_TABLE_SCHEMA = [
    bigquery.SchemaField("ingested_at", "TIMESTAMP", mode="REQUIRED"),
    bigquery.SchemaField("file_name", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("payload", "JSON", mode="REQUIRED"),
]


class BigQueryLoader:
    def __init__(self, config: BigQueryConfig):
        self.config = config
        credentials = service_account.Credentials.from_service_account_file(
            config.credentials_path
        )
        self.client = bigquery.Client(
            project=config.project_id,
            credentials=credentials,
            location=config.location,
        )

    @property
    def _dataset_ref(self) -> str:
        return f"{self.config.project_id}.{self.config.dataset}"

    @property
    def _table_ref(self) -> str:
        return f"{self._dataset_ref}.{self.config.raw_table}"

    def ensure_objects_exist(self) -> None:
        """Crée le dataset et la table RAW s'ils n'existent pas."""
        dataset = bigquery.Dataset(self._dataset_ref)
        dataset.location = self.config.location
        self.client.create_dataset(dataset, exists_ok=True)

        table = bigquery.Table(self._table_ref, schema=RAW_TABLE_SCHEMA)
        self.client.create_table(table, exists_ok=True)

    def load_events(self, events: Iterable[dict[str, Any]]) -> int:
        """
        Écrit les events en NDJSON localement puis les charge dans la table
        RAW via un load job (WRITE_APPEND). Retourne le nombre de lignes chargées.
        """
        events = list(events)
        if not events:
            logger.info("Aucun événement à charger.")
            return 0

        run_id = uuid.uuid4().hex[:8]
        file_name = f"ticketmaster_events_{run_id}.json"

        with tempfile.TemporaryDirectory() as tmp_dir:
            local_path = Path(tmp_dir) / "load.ndjson"
            with local_path.open("w", encoding="utf-8") as f:
                for event in events:
                    record = {
                        "ingested_at": event.get("ingested_at"),
                        "file_name": file_name,
                        "payload": event,
                    }
                    f.write(json.dumps(record, default=str) + "\n")

            job_config = bigquery.LoadJobConfig(
                source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
                schema=RAW_TABLE_SCHEMA,
                write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
            )

            with local_path.open("rb") as f:
                load_job = self.client.load_table_from_file(
                    f, self._table_ref, job_config=job_config
                )

            load_job.result()  # bloque jusqu'à la fin du job, lève si erreur

        rows_loaded = load_job.output_rows
        logger.info("Load job terminé : %s lignes chargées.", rows_loaded)
        return rows_loaded