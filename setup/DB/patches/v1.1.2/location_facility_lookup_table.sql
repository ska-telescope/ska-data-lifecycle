BEGIN;

-- Convert location_facility column to foreign key via lookup table.

-- Create the location_facility lookup table
CREATE TABLE IF NOT EXISTS location_facility (
    id TEXT PRIMARY KEY
);

INSERT INTO location_facility (id)
SELECT unnest(ARRAY['SRC', 'STFC', 'AWS', 'Google', 'Pawsey Centre', 'external', 'local'])
ON CONFLICT DO NOTHING;

-- Add foreign key constraint
DO $$
BEGIN
  ALTER TABLE location
    ADD CONSTRAINT location_location_facility_fkey
    FOREIGN KEY (location_facility)
    REFERENCES location_facility(id);
EXCEPTION
  WHEN duplicate_object THEN
    RAISE NOTICE 'Constraint location_location_facility_fkey already exists. Skipping.';
END;
$$;

COMMIT;
