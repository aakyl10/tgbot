-- =========================
-- TwinEnergyAIHome KPI SQL
-- File: kpi_queries.sql
-- =========================

-- (A) One-time setup: create events table + indexes (run once)
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  event_type TEXT NOT NULL,
  ts TEXT NOT NULL DEFAULT (datetime('now')),
  meta TEXT
);

CREATE INDEX IF NOT EXISTS idx_events_user_ts ON events(user_id, ts);
CREATE INDEX IF NOT EXISTS idx_events_type_ts ON events(event_type, ts);

-- (B) Sanity check: events distribution
SELECT event_type, COUNT(*) AS n
FROM events
GROUP BY event_type
ORDER BY n DESC;

-- (C) Alpha KPI: Completion rate (started -> diagnosis_shown)
SELECT
  s.started,
  c.completed,
  ROUND(100.0 * c.completed / NULLIF(s.started, 0), 2) AS completion_rate_percent
FROM
  (SELECT COUNT(DISTINCT user_id) AS started
   FROM events
   WHERE event_type = 'start') s,
  (SELECT COUNT(DISTINCT user_id) AS completed
   FROM events
   WHERE event_type = 'diagnosis_shown') c;

-- (D) Alpha KPI: Usefulness (1–5)
SELECT
  ROUND(AVG(CAST(meta AS REAL)), 2) AS avg_usefulness,
  COUNT(*) AS n_feedback
FROM events
WHERE event_type='feedback_submitted'
  AND meta IS NOT NULL
  AND CAST(meta AS REAL) BETWEEN 1 AND 5;

-- (E) Beta KPI: Return to verified savings
SELECT
  c.completed,
  r.returned,
  ROUND(100.0 * r.returned / NULLIF(c.completed, 0), 2) AS return_rate_percent
FROM
  (SELECT COUNT(DISTINCT user_id) AS completed
   FROM events
   WHERE event_type='diagnosis_shown') c,
  (SELECT COUNT(DISTINCT user_id) AS returned
   FROM events
   WHERE event_type='savings_report_generated') r;
