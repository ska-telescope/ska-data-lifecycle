-- Convert location_facility column to foreign key via lookup table. Safe to re-run.
BEGIN;

-- Create the location_facility lookup table
CREATE TABLE IF NOT EXISTS location_facility (
    id TEXT PRIMARY KEY
);

-- Insert allowed values into lookup table
INSERT INTO location_facility (id)
SELECT unnest(ARRAY['SRC', 'STFC', 'AWS', 'Google', 'Pawsey Centre', 'external', 'local'])
ON CONFLICT DO NOTHING;

-- Identify and nullify invalid location_facility values in existing data
DO $$
DECLARE
  invalid_values TEXT[];
BEGIN
  SELECT ARRAY_AGG(DISTINCT location_facility)
  INTO invalid_values
  FROM location
  WHERE location_facility IS NOT NULL
    AND location_facility NOT IN (
      SELECT id FROM location_facility
    );

  IF invalid_values IS NOT NULL THEN
    RAISE WARNING 'Invalid location_facility values found and changed to NULL: %', invalid_values;
    UPDATE location
    SET location_facility = NULL
    WHERE location_facility = ANY (invalid_values);
  END IF;
END
$$;

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
END
$$;

COMMIT;
