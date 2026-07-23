CREATE TABLE IF NOT EXISTS calculations (
    id TEXT PRIMARY KEY,
    module_id TEXT NOT NULL,
    module_version TEXT NOT NULL,
    calculation_model_version TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('completed', 'completed_with_warnings')),
    input_original_json TEXT NOT NULL,
    input_si_json TEXT NOT NULL,
    assumptions_json TEXT NOT NULL,
    results_json TEXT NOT NULL,
    steps_json TEXT NOT NULL,
    warnings_json TEXT NOT NULL,
    disclaimer_json TEXT NOT NULL,
    snapshot_schema_version INTEGER NOT NULL CHECK (snapshot_schema_version >= 1),
    input_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    request_id TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_calculations_module_id ON calculations(module_id);
CREATE INDEX IF NOT EXISTS idx_calculations_model_version ON calculations(calculation_model_version);
CREATE INDEX IF NOT EXISTS idx_calculations_created_at ON calculations(created_at);

CREATE TABLE IF NOT EXISTS report_artifacts (
    id TEXT PRIMARY KEY,
    calculation_id TEXT NOT NULL REFERENCES calculations(id) ON DELETE RESTRICT,
    format TEXT NOT NULL CHECK (format = 'pdf'),
    status TEXT NOT NULL CHECK (status IN ('generating', 'ready', 'failed')),
    template_version TEXT NOT NULL,
    relative_path TEXT,
    sha256 TEXT,
    size_bytes INTEGER CHECK (size_bytes IS NULL OR size_bytes >= 0),
    created_at TEXT NOT NULL,
    completed_at TEXT,
    error_code TEXT,
    UNIQUE(calculation_id, format, template_version)
);

CREATE INDEX IF NOT EXISTS idx_report_artifacts_calculation_id ON report_artifacts(calculation_id);
