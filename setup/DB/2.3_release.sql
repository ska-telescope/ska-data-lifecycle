
-- SQL script for release 2.3

--changeset dlm:2.3-release context:2.3-release

--
-- Table: outbox
--
CREATE TABLE IF NOT EXISTS dlm.outbox (
    outbox_id    uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    event_type   varchar NOT NULL,
    payload      jsonb NOT NULL,
    destination  varchar DEFAULT NULL,
    routing_key  varchar DEFAULT NULL,
    status       varchar NOT NULL DEFAULT 'PENDING',
    attempts     integer DEFAULT 0,
    created_at   timestamp without time zone DEFAULT now(),
    last_attempt timestamp without time zone DEFAULT NULL,
    sent_at      timestamp without time zone DEFAULT NULL
);

-- Index to help the background worker find unsent messages instantly
CREATE INDEX idx_outbox_pending ON dlm.outbox (status, created_at);
