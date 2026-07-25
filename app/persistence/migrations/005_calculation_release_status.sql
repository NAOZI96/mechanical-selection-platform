ALTER TABLE calculations
ADD COLUMN release_status TEXT
CHECK (
    release_status IS NULL OR
    release_status IN ('internal_testing', 'engineering_review', 'released')
);
