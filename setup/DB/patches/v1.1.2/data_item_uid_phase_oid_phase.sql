DO
$$
BEGIN
  -- Add 'oid_phase' column if it doesn't already exist
  BEGIN
    ALTER TABLE public.data_item
      ADD COLUMN IF NOT EXISTS oid_phase VARCHAR DEFAULT 'GAS';
  EXCEPTION
    WHEN duplicate_column THEN
      RAISE NOTICE 'oid_phase already exists';
  END;

  -- Rename 'item_phase' to 'uid_phase' if it exists
  BEGIN
    ALTER TABLE public.data_item
      RENAME COLUMN item_phase TO uid_phase;
  EXCEPTION
    WHEN undefined_column THEN
      RAISE NOTICE 'column item_phase does not exist or has already been renamed';
  END;

  -- Rename 'storage_phase_level' to 'storage_phase' if it exists
  BEGIN
    ALTER TABLE public.storage
      RENAME COLUMN storage_phase_level TO storage_phase;
  EXCEPTION
    WHEN undefined_column THEN
      RAISE NOTICE 'column storage_phase_level does not exist or has already been renamed';
  END;
END
$$;