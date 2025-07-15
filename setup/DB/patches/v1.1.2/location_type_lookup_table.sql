BEGIN;

-- Convert location_type column to foreign key via lookup table.

-- Create the location_type lookup table
CREATE TABLE IF NOT EXISTS location_type (
    id TEXT PRIMARY KEY
);

INSERT INTO location_type (id)
SELECT unnest(ARRAY[
    'src', 'aws', 'gcs', 'low-operational', 'low-itf', 'mid-itf', 'dp', 'external'
])
ON CONFLICT DO NOTHING;

DO $$
BEGIN
  ALTER TABLE location
    ADD CONSTRAINT location_location_type_fkey
    FOREIGN KEY (location_type)
    REFERENCES location_type(id);
EXCEPTION
  WHEN duplicate_object THEN
    RAISE NOTICE 'Constraint location_location_type_fkey already exists. Skipping.';
END;
$$;

COMMIT;
