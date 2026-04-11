--liquibase formatted sql

--changeset dlm:v1.1.2-metadata-to-jsonb context:unprivileged
-- Convert the 'metadata' column in 'data_item' from JSON to JSONB

ALTER TABLE data_item
ALTER COLUMN metadata
SET DATA TYPE jsonb
USING metadata::jsonb;
