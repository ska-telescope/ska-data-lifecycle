-- Convert the 'metadata' column in 'data_item' from JSON to JSONB
-- Safe to re-run: if already JSONB, this is a no-op
-- Assumes the column is currently either JSON or JSONB

-- As this is the first script to run in the patch, its must set the schema its working on
SET search_path TO dlm;

ALTER TABLE data_item
ALTER COLUMN metadata
SET DATA TYPE jsonb
USING metadata::jsonb;
