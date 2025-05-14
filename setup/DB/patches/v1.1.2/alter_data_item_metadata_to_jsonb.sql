-- Convert the 'metadata' column in 'data_item' from JSON to JSONB
-- Safe to re-run: if already JSONB, this is a no-op
-- Assumes the column is currently either JSON or JSONB
ALTER TABLE public.data_item
ALTER COLUMN metadata
SET DATA TYPE jsonb
USING metadata::jsonb;