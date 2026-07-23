ALTER TABLE calculations
ADD COLUMN report_template_version TEXT NOT NULL DEFAULT 'legacy.report.0.0.0';
