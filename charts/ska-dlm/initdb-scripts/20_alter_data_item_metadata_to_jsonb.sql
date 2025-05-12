-- This script checks the current data type of the 'metadata' column in the 'data_item' table.
-- If the column is of type 'json', it will convert it to 'jsonb' using a safe ALTER TABLE statement.
-- If the column is already 'jsonb' or another type, no change will be made.
-- The use of DO $$ ... $$ ensures this is safe and idempotent across different environments.

DO $$
DECLARE
    current_type text;
BEGIN
    SELECT data_type INTO current_type
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'data_item'
      AND column_name = 'metadata';

    IF current_type = 'json' THEN
        RAISE NOTICE 'Changing column data_item.metadata from json to jsonb...';
        ALTER TABLE public.data_item
        ALTER COLUMN metadata
        SET DATA TYPE jsonb
        USING metadata::jsonb;
    ELSE
        RAISE NOTICE 'No change needed. data_item.metadata is already %', current_type;
    END IF;
END$$;
