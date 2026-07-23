CREATE TRIGGER IF NOT EXISTS trg_report_artifacts_ready_insert
BEFORE INSERT ON report_artifacts
WHEN NEW.status = 'ready' AND (
    NEW.relative_path IS NULL OR
    NEW.sha256 IS NULL OR
    NEW.size_bytes IS NULL OR
    NEW.completed_at IS NULL
)
BEGIN
    SELECT RAISE(ABORT, 'ready report artifact requires path, hash, size, and completed_at');
END;

CREATE TRIGGER IF NOT EXISTS trg_report_artifacts_ready_update
BEFORE UPDATE ON report_artifacts
WHEN NEW.status = 'ready' AND (
    NEW.relative_path IS NULL OR
    NEW.sha256 IS NULL OR
    NEW.size_bytes IS NULL OR
    NEW.completed_at IS NULL
)
BEGIN
    SELECT RAISE(ABORT, 'ready report artifact requires path, hash, size, and completed_at');
END;
