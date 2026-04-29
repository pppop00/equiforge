-- equity-fusion DB schema 001 — initial
-- After applying this file, PRAGMA user_version is set to 1.

PRAGMA foreign_keys = ON;

-- ─────────────────────────────────────────────────────────────────────
-- Bookkeeping
-- ─────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS schema_meta (
    schema_version INTEGER PRIMARY KEY,
    applied_at     TEXT NOT NULL,
    notes          TEXT
);

-- ─────────────────────────────────────────────────────────────────────
-- Entity registry
-- ─────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS companies (
    ticker             TEXT PRIMARY KEY,
    exchange           TEXT,
    name_en            TEXT,
    name_cn            TEXT,
    sector             TEXT,
    sub_industry       TEXT,
    primary_geography  TEXT,
    first_seen_date    TEXT,
    last_run_date      TEXT,
    metadata_json      TEXT
);

CREATE INDEX IF NOT EXISTS idx_companies_sector ON companies(sector);
CREATE INDEX IF NOT EXISTS idx_companies_geo    ON companies(primary_geography);

-- ─────────────────────────────────────────────────────────────────────
-- Runs
-- ─────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS runs (
    run_id            TEXT PRIMARY KEY,
    ticker            TEXT NOT NULL REFERENCES companies(ticker),
    run_date          TEXT NOT NULL,
    language          TEXT CHECK(language IN ('en','zh')),
    mode              TEXT,
    packaging_profile TEXT,
    output_folder     TEXT,
    run_status        TEXT NOT NULL DEFAULT 'in_progress',
    schema_version    INTEGER,
    started_at        TEXT,
    finished_at       TEXT,
    qc_full           INTEGER DEFAULT 0,
    sec_api_used      INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_runs_ticker_date ON runs(ticker, run_date DESC);
CREATE INDEX IF NOT EXISTS idx_runs_status      ON runs(run_status);

-- ─────────────────────────────────────────────────────────────────────
-- Financials per period (the priors table)
-- PK keyed on (ticker, fiscal_period, period_type) — re-running same period upserts
-- ─────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS financials_period (
    ticker                    TEXT NOT NULL,
    fiscal_period             TEXT NOT NULL,
    period_type               TEXT NOT NULL CHECK(period_type IN ('annual','interim','quarterly')),
    period_end_date           TEXT,

    revenue                   REAL,
    cogs                      REAL,
    gross_profit              REAL,
    rd_expense                REAL,
    sm_expense                REAL,
    ga_expense                REAL,
    total_opex                REAL,
    operating_income          REAL,
    net_income                REAL,
    diluted_eps               REAL,
    diluted_shares            REAL,

    gross_margin              REAL,
    operating_margin          REAL,
    net_margin                REAL,
    yoy_revenue_pct           REAL,
    yoy_net_income_pct        REAL,

    cash_and_equivalents      REAL,
    total_assets              REAL,
    total_debt                REAL,
    total_equity              REAL,
    shares_outstanding        REAL,

    operating_cash_flow       REAL,
    capex                     REAL,
    free_cash_flow            REAL,

    roic_pct                  REAL,
    fcf_margin_pct            REAL,
    debt_to_ebitda            REAL,
    ev_to_ebitda              REAL,
    eps_growth_pct            REAL,

    currency                  TEXT,
    unit                      TEXT,
    data_source               TEXT,
    data_confidence           TEXT,
    source_filing_url         TEXT,

    source_run_id             TEXT NOT NULL REFERENCES runs(run_id),
    superseded_by_run_id      TEXT REFERENCES runs(run_id),

    PRIMARY KEY (ticker, fiscal_period, period_type),
    FOREIGN KEY (ticker) REFERENCES companies(ticker)
);

CREATE INDEX IF NOT EXISTS idx_fp_period       ON financials_period(period_end_date);
CREATE INDEX IF NOT EXISTS idx_fp_ticker       ON financials_period(ticker);

CREATE TABLE IF NOT EXISTS financials_period_history (
    history_id                INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker                    TEXT NOT NULL,
    fiscal_period             TEXT NOT NULL,
    period_type               TEXT NOT NULL,
    superseded_at             TEXT NOT NULL,
    snapshot_json             TEXT NOT NULL,
    source_run_id             TEXT NOT NULL
);

-- ─────────────────────────────────────────────────────────────────────
-- Segments (per period)
-- ─────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS segments_period (
    ticker         TEXT NOT NULL,
    fiscal_period  TEXT NOT NULL,
    segment_name   TEXT NOT NULL,
    revenue        REAL,
    pct_of_total   REAL,
    source_run_id  TEXT NOT NULL,
    PRIMARY KEY (ticker, fiscal_period, segment_name)
);

-- ─────────────────────────────────────────────────────────────────────
-- Macro factors per (geography, period) — keyed on geography to enable cross-company reuse
-- ─────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS macro_factors_period (
    geography           TEXT NOT NULL,
    period              TEXT NOT NULL,
    factor_slot         TEXT NOT NULL CHECK(factor_slot IN ('rate','gdp','inflation','fx','oil','consumer_confidence')),
    factor_name_raw     TEXT,
    current_value       REAL,
    forecast_value      REAL,
    factor_change_pct   REAL,
    beta                REAL,
    phi                 REAL,
    adjustment_pct      REAL,
    unit                TEXT,
    source              TEXT,
    collected_at        TEXT,
    source_run_id       TEXT NOT NULL,
    PRIMARY KEY (geography, period, factor_slot)
);

CREATE INDEX IF NOT EXISTS idx_mfp_geo_period ON macro_factors_period(geography, period);

-- ─────────────────────────────────────────────────────────────────────
-- Porter scores (15 rows per run: 3 perspectives × 5 forces)
-- ─────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS porter_scores_period (
    ticker             TEXT NOT NULL,
    fiscal_period      TEXT NOT NULL,
    perspective        TEXT NOT NULL CHECK(perspective IN ('company','industry','forward')),
    force              TEXT NOT NULL CHECK(force IN ('supplier','buyer','entrant','substitute','rivalry')),
    score              INTEGER NOT NULL CHECK(score BETWEEN 1 AND 5),
    rationale_excerpt  TEXT,
    qc_score_changed   INTEGER DEFAULT 0,
    score_before       INTEGER,
    score_after        INTEGER,
    source_run_id      TEXT NOT NULL,
    PRIMARY KEY (ticker, fiscal_period, perspective, force)
);

CREATE INDEX IF NOT EXISTS idx_porter_force_perspective ON porter_scores_period(force, perspective);

-- ─────────────────────────────────────────────────────────────────────
-- Prediction waterfall
-- ─────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS prediction_waterfall_period (
    ticker                          TEXT NOT NULL,
    fiscal_period                   TEXT NOT NULL,
    baseline_growth_pct             REAL,
    macro_adjustment_total_pct      REAL,
    company_specific_adjustment_pct REAL,
    predicted_revenue_growth_pct    REAL,
    predicted_revenue               REAL,
    phi                             REAL,
    confidence                      TEXT,
    formula_note                    TEXT,
    macro_adjustments_json          TEXT,
    company_events_detail_json      TEXT,
    qc_deliberation_json            TEXT,
    source_run_id                   TEXT NOT NULL,
    PRIMARY KEY (ticker, fiscal_period)
);

-- ─────────────────────────────────────────────────────────────────────
-- Intelligence signals (append-only library)
-- ─────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS intelligence_signals (
    sig_id              TEXT PRIMARY KEY,
    ticker              TEXT,
    sector              TEXT,
    signal_type         TEXT,
    fact                TEXT,
    affected_metric     TEXT,
    watch_metric        TEXT,
    thesis_implication  TEXT,
    observation_date    TEXT,
    source_run_id       TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_signals_sector_type ON intelligence_signals(sector, signal_type);
CREATE INDEX IF NOT EXISTS idx_signals_ticker      ON intelligence_signals(ticker);

-- ─────────────────────────────────────────────────────────────────────
-- Edge insights
-- ─────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS edge_insights (
    insight_id              TEXT PRIMARY KEY,
    ticker                  TEXT NOT NULL,
    run_id                  TEXT NOT NULL REFERENCES runs(run_id),
    headline                TEXT,
    insight_type            TEXT,
    surface_read            TEXT,
    hidden_rule             TEXT,
    investment_implication  TEXT,
    confidence              TEXT,
    evidence_json           TEXT
);

CREATE INDEX IF NOT EXISTS idx_edge_ticker ON edge_insights(ticker);

-- ─────────────────────────────────────────────────────────────────────
-- Disclosure quirks (sector accounting precedent library)
-- ─────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS disclosure_quirks (
    quirk_id        TEXT PRIMARY KEY,
    ticker          TEXT,
    sector          TEXT,
    fiscal_period   TEXT,
    description     TEXT,
    basis_change    TEXT,
    run_id          TEXT NOT NULL REFERENCES runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_quirks_sector ON disclosure_quirks(sector);

-- ─────────────────────────────────────────────────────────────────────
-- QC events (calibration data over time)
-- ─────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS qc_events (
    run_id              TEXT NOT NULL REFERENCES runs(run_id),
    item_id             TEXT NOT NULL,
    phase               TEXT NOT NULL CHECK(phase IN ('macro','porter')),
    perspective         TEXT,
    force               TEXT,
    verdict             TEXT,
    score_before        REAL,
    score_after         REAL,
    weighted_score      REAL,
    delta_vs_draft      REAL,
    rationale           TEXT,
    fields_changed_json TEXT,
    PRIMARY KEY (run_id, item_id)
);

-- ─────────────────────────────────────────────────────────────────────
-- Validation findings
-- ─────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS validation_findings (
    finding_id        TEXT PRIMARY KEY,
    run_id            TEXT NOT NULL REFERENCES runs(run_id),
    severity          TEXT CHECK(severity IN ('CRITICAL','WARNING','INFO')),
    category          TEXT,
    description       TEXT,
    root_cause        TEXT,
    recomputed_value  TEXT
);

CREATE INDEX IF NOT EXISTS idx_findings_run ON validation_findings(run_id);

-- ─────────────────────────────────────────────────────────────────────
-- Card slots (per run)
-- ─────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS card_slots (
    ticker             TEXT NOT NULL,
    run_id             TEXT NOT NULL REFERENCES runs(run_id),
    card_slots_json    TEXT NOT NULL,
    cover_focus        TEXT,
    brand_statement    TEXT,
    social_post        TEXT,
    card1_png_path     TEXT,
    card2_png_path     TEXT,
    card3_png_path     TEXT,
    card4_png_path     TEXT,
    card5_png_path     TEXT,
    card6_png_path     TEXT,
    PRIMARY KEY (ticker, run_id)
);

-- ─────────────────────────────────────────────────────────────────────
-- FTS5 narratives — over thesis / edge / signal facts / Porter / news / macro commentary
-- ─────────────────────────────────────────────────────────────────────

CREATE VIRTUAL TABLE IF NOT EXISTS fts_narratives USING fts5(
    doc_id           UNINDEXED,
    ticker           UNINDEXED,
    sector           UNINDEXED,
    section,
    content,
    tokenize='unicode61 remove_diacritics 2'
);
