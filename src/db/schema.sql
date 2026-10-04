CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ------------------------------------------------------------
-- Table : events bruts
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS raw_events (
    event_id        TEXT PRIMARY KEY,
    name            TEXT,
    artist_id       TEXT,
    artist_name     TEXT,
    venue_name      TEXT,
    city            TEXT,
    country         TEXT          NOT NULL,
    event_date      DATE          NOT NULL,
    segment         TEXT,                         -- Music, Sports, Arts...
    genre           TEXT,                         -- Rock, Pop, Jazz...
    subgenre        TEXT,
    price_min       NUMERIC(10,2),
    price_max       NUMERIC(10,2),
    currency        TEXT,
    url             TEXT,
    status          TEXT,                         -- onsale, offsale, cancelled...
    last_updated    TIMESTAMP WITH TIME ZONE,
    ingested_at     TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index pour les requêtes analytiques fréquentes
CREATE INDEX IF NOT EXISTS idx_events_artist   ON raw_events (artist_id);
CREATE INDEX IF NOT EXISTS idx_events_genre    ON raw_events (genre);
CREATE INDEX IF NOT EXISTS idx_events_date     ON raw_events (event_date);
CREATE INDEX IF NOT EXISTS idx_events_country  ON raw_events (country);
CREATE INDEX IF NOT EXISTS idx_events_ingested ON raw_events (ingested_at);

-- ------------------------------------------------------------
-- Table : artistes enrichis
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS artists (
    artist_id       TEXT PRIMARY KEY,
    name            TEXT          NOT NULL,
    genre           TEXT,
    subgenre        TEXT,
    image_url       TEXT,
    spotify_url     TEXT,
    updated_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ------------------------------------------------------------
-- Table : log des appels API (suivi quota)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS api_calls_log (
    id              BIGSERIAL PRIMARY KEY,
    endpoint        TEXT          NOT NULL,
    status_code     INTEGER       NOT NULL,
    called_at       TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_api_log_date ON api_calls_log (called_at);

-- ------------------------------------------------------------
-- Vue : quota du jour
-- ------------------------------------------------------------
CREATE OR REPLACE VIEW v_quota_today AS
SELECT
    COUNT(*)                                         AS calls_today,
    5000 - COUNT(*)                                  AS remaining,
    ROUND(COUNT(*) * 100.0 / 5000, 1)               AS pct_used,
    COUNT(*) FILTER (WHERE status_code = 200)        AS success,
    COUNT(*) FILTER (WHERE status_code != 200)       AS errors,
    MAX(called_at)                                   AS last_call_at
FROM api_calls_log
WHERE called_at::date = CURRENT_DATE;

-- ------------------------------------------------------------
-- Vue analytique : prix moyen par genre
-- ------------------------------------------------------------
CREATE OR REPLACE VIEW v_avg_price_by_genre AS
SELECT
    genre,
    COUNT(*)                            AS nb_events,
    ROUND(AVG(price_min), 2)            AS avg_price_min,
    ROUND(AVG(price_max), 2)            AS avg_price_max,
    ROUND(AVG((price_min + price_max) / 2), 2) AS avg_price_mid,
    MIN(price_min)                      AS cheapest,
    MAX(price_max)                      AS most_expensive,
    currency
FROM raw_events
WHERE price_min IS NOT NULL
  AND event_date >= CURRENT_DATE
GROUP BY genre, currency
ORDER BY avg_price_mid DESC;

-- ------------------------------------------------------------
-- Vue analytique : prix moyen par artiste
-- ------------------------------------------------------------
CREATE OR REPLACE VIEW v_avg_price_by_artist AS
SELECT
    artist_name,
    genre,
    COUNT(*)                            AS nb_events,
    ROUND(AVG(price_min), 2)            AS avg_price_min,
    ROUND(AVG(price_max), 2)            AS avg_price_max,
    MIN(price_min)                      AS cheapest_ticket,
    MAX(price_max)                      AS priciest_ticket,
    currency
FROM raw_events
WHERE price_min IS NOT NULL
  AND artist_name IS NOT NULL
  AND event_date >= CURRENT_DATE
GROUP BY artist_name, genre, currency
HAVING COUNT(*) >= 2
ORDER BY avg_price_max DESC;
