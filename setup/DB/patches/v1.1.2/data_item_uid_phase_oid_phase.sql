BEGIN;

-- Add column (safe to re-run)
ALTER TABLE data_item
  ADD COLUMN IF NOT EXISTS oid_phase VARCHAR DEFAULT 'GAS';

-- Rename column. Will error (and roll back) if table exists but column doesn't
ALTER TABLE data_item
  RENAME COLUMN item_phase TO uid_phase;

-- Rename column. Will error (and roll back) if table exists but column doesn't
ALTER TABLE storage
  RENAME COLUMN storage_phase_level TO storage_phase;

COMMIT;

