BEGIN;

-- Add column (safe to re-run)
ALTER TABLE data_item
  ADD COLUMN IF NOT EXISTS oid_phase VARCHAR DEFAULT 'GAS';

-- Rename column if it exists
DO $$
DECLARE
  sch text := current_schema();
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = sch
      AND table_name = 'data_item'
      AND column_name = 'item_phase'
  ) THEN
    ALTER TABLE data_item
      RENAME COLUMN item_phase TO uid_phase;
  END IF;
END
$$;

-- Rename column if it exists
DO $$
DECLARE
  sch text := current_schema();
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = sch
      AND table_name = 'storage'
      AND column_name = 'storage_phase_level'
  ) THEN
    ALTER TABLE storage
      RENAME COLUMN storage_phase_level TO storage_phase;
  END IF;
END
$$;

COMMIT;

