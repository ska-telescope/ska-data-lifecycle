-- This patch is safe to re-run.

DO $$
BEGIN
  -- Rename 'item_phase' to 'uid_phase' if 'item_phase' exists
  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'data_item'
      AND column_name = 'item_phase'
  ) AND NOT EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'data_item'
      AND column_name = 'uid_phase'
  ) THEN
    RAISE NOTICE 'Renaming item_phase to uid_phase';
    ALTER TABLE public.data_item
      RENAME COLUMN item_phase TO uid_phase;
  ELSE
    RAISE NOTICE 'item_phase does not exist, or uid_phase already exists. Skipping rename.';
  END IF;

  -- Add 'oid_phase' column if it doesn't already exist
  IF NOT EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'data_item'
      AND column_name = 'oid_phase'
  ) THEN
    RAISE NOTICE 'Adding oid_phase column';
    ALTER TABLE public.data_item
      ADD COLUMN oid_phase VARCHAR DEFAULT 'GAS';
  ELSE
    RAISE NOTICE 'oid_phase column already exists';
  END IF;

  -- Rename 'storage_phase_level' to 'storage_phase' if applicable
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'storage' AND column_name = 'storage_phase_level'
  ) AND NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'storage' AND column_name = 'storage_phase'
  ) THEN
    RAISE NOTICE 'Renaming storage_phase_level to storage_phase';
    ALTER TABLE public.storage
      RENAME COLUMN storage_phase_level TO storage_phase;
  ELSE
    RAISE NOTICE 'storage_phase_level rename not needed';
  END IF;
END
$$;