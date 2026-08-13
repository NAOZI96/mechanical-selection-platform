ALTER TABLE calculations
ADD COLUMN idempotency_key TEXT
CHECK (
    idempotency_key IS NULL OR (
        length(idempotency_key) BETWEEN 1 AND 128 AND
        idempotency_key NOT GLOB '*[^A-Za-z0-9._~-]*'
    )
);

ALTER TABLE calculations
ADD COLUMN request_fingerprint TEXT
CHECK (
    (idempotency_key IS NULL AND request_fingerprint IS NULL) OR (
        idempotency_key IS NOT NULL AND
        request_fingerprint IS NOT NULL AND
        length(request_fingerprint) = 64 AND
        request_fingerprint NOT GLOB '*[^0-9a-f]*'
    )
);

CREATE UNIQUE INDEX idx_calculations_module_idempotency_key
ON calculations(module_id, idempotency_key)
WHERE idempotency_key IS NOT NULL;
