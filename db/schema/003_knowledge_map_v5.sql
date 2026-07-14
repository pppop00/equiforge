-- Schema-v5 company-to-country knowledge-map persistence.

CREATE TABLE IF NOT EXISTS claim_evidence (
    run_id             TEXT NOT NULL REFERENCES runs(run_id),
    ticker             TEXT NOT NULL,
    claim_id           TEXT NOT NULL,
    slot_path          TEXT NOT NULL,
    epistemic_type     TEXT NOT NULL,
    source_refs_json   TEXT NOT NULL,
    as_of_date         TEXT NOT NULL,
    basis_id           TEXT,
    falsifier          TEXT,
    PRIMARY KEY (run_id, claim_id)
);

CREATE TABLE IF NOT EXISTS metric_basis_period (
    ticker                 TEXT NOT NULL,
    fiscal_period          TEXT NOT NULL,
    basis_id               TEXT NOT NULL,
    metric_key             TEXT NOT NULL,
    company_label          TEXT,
    company_definition     TEXT NOT NULL,
    standardized_formula   TEXT NOT NULL,
    currency               TEXT,
    unit                   TEXT,
    comparability          TEXT NOT NULL,
    adjustment_note        TEXT,
    source_refs_json       TEXT NOT NULL,
    as_of_date             TEXT,
    source_run_id          TEXT NOT NULL REFERENCES runs(run_id),
    PRIMARY KEY (ticker, fiscal_period, basis_id)
);

CREATE TABLE IF NOT EXISTS company_quality_observations (
    run_id             TEXT NOT NULL REFERENCES runs(run_id),
    ticker             TEXT NOT NULL,
    observation_type   TEXT NOT NULL,
    finding            TEXT,
    evidence           TEXT,
    watch_item         TEXT,
    status             TEXT,
    metrics_json       TEXT,
    source_refs_json   TEXT,
    as_of_date         TEXT,
    PRIMARY KEY (run_id, observation_type)
);

CREATE TABLE IF NOT EXISTS country_lens_observations (
    run_id                 TEXT NOT NULL REFERENCES runs(run_id),
    ticker                 TEXT NOT NULL,
    dimension_key          TEXT NOT NULL,
    country_fact           TEXT,
    company_transmission   TEXT,
    watch_metric           TEXT,
    status                 TEXT,
    source_refs_json       TEXT,
    as_of_date             TEXT,
    PRIMARY KEY (run_id, dimension_key)
);
