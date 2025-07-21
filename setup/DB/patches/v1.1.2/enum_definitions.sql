-- This patch defines enum types.

DO $$
BEGIN
  CREATE TYPE location_country AS ENUM ('AU', 'ZA', 'UK');
  CREATE TYPE config_type AS ENUM ('rclone', 'ssh', 'aws', 'gcs');
  CREATE TYPE storage_type AS ENUM ('filesystem', 'objectstore', 'tape');
  CREATE TYPE storage_interface AS ENUM ('posix', 's3', 'sftp', 'https');
  CREATE TYPE phase_type AS ENUM ('GAS', 'LIQUID', 'SOLID', 'PLASMA');
  CREATE TYPE item_state AS ENUM ('INITIALISED', 'READY', 'CORRUPTED', 'EXPIRED', 'DELETED');
  CREATE TYPE checksum_method AS ENUM (
    'none', 'adler32', 'blake2b', 'blake2s', 'crc32', 'crc32c', 'fletcher32', 'highwayhash', 'jenkinslookup3', 'md5', 'metrohash128',
    'sha1', 'sha224', 'sha256', 'sha384', 'sha3_224', 'sha3_256', 'sha3_384', 'sha3_512', 'sha512', 'shake_128', 'shake_256',
    'spookyhash', 'xxh3'
  );
  CREATE TYPE mime_type AS ENUM (
    'application/fits', 'application/gzip', 'application/json', 'application/mp4', 'application/msword',
    'application/octet-stream', 'application/pdf', 'application/postscript', 'application/rtf',
    'application/vnd.ms-cab-compressed', 'application/vnd.ms-excel', 'application/vnd.ms-powerpoint',
    'application/vnd.msv2', 'application/vnd.msv3', 'application/vnd.msv4', 'application/vnd.rar',
    'application/vnd.sqlite3', 'application/vnd.zarr', 'application/x-7z-compressed', 'application/x-bzip',
    'application/x-bzip2', 'application/x-cpio', 'application/x-debian-package', 'application/x-gzip',
    'application/x-hdf', 'application/x-iso9660-image', 'application/x-ms-application', 'application/x-msdownload',
    'application/x-rar-compressed', 'application/x-sh', 'application/x-shellscript', 'application/x-tar',
    'application/x-tex', 'application/x-zip-compressed', 'application/xml', 'application/yaml', 'application/zip',
    'application/zip-compressed', 'audio/mp4', 'image/jpeg', 'image/png', 'image/tiff', 'text/csv', 'text/html',
    'text/javascript', 'text/markdown', 'text/plain', 'text/tab-separated-values', 'text/x-c', 'text/x-fortran',
    'text/x-java-source', 'text/x-python', 'video/mp4'
  );
EXCEPTION
  WHEN duplicate_object THEN
    RAISE WARNING 'One or more enum types already exist. Skipping creation.';
END;
$$;

------------------------------------------------------------------------------------------
-- This patch continues by updating columns to use the new enum types.
------------------------------------------------------------------------------------------

------------------------------------------------------------------------------------------
-- Convert data_item.item_state to enum item_state
DO $$
DECLARE
  invalid_values TEXT[];
BEGIN
  -- Drop default before conversion
  ALTER TABLE data_item
    ALTER COLUMN item_state DROP DEFAULT;

  -- Fix legacy enum values
  UPDATE data_item
  SET item_state = 'INITIALISED'
  WHERE item_state::TEXT = 'INITIALIZED';

  -- Identify invalid values
  SELECT ARRAY_AGG(DISTINCT item_state)
  INTO invalid_values
  FROM data_item
  WHERE item_state IS NOT NULL
    AND item_state::TEXT NOT IN (
    -- pg_enum is a PostgreSQL system catalog that stores labels for all enum types
    -- enumlabel is a built-in column in pg_enum containing the enum's string values
      SELECT enumlabel
      FROM pg_enum
      JOIN pg_type ON pg_enum.enumtypid = pg_type.oid
      WHERE pg_type.typname = 'item_state'
    );

  IF invalid_values IS NOT NULL THEN
    RAISE WARNING 'Invalid values found in item_state: %', invalid_values;
    UPDATE data_item
    SET item_state = NULL
    WHERE item_state = ANY(invalid_values);
  END IF;

  -- Convert column to enum
  ALTER TABLE data_item
    ALTER COLUMN item_state TYPE item_state USING item_state::item_state;

  -- Restore default
  ALTER TABLE data_item
    ALTER COLUMN item_state SET DEFAULT 'INITIALISED';

EXCEPTION
  WHEN undefined_column THEN
    RAISE WARNING 'Column data_item.item_state does not exist';
  WHEN invalid_parameter_value THEN
    RAISE WARNING 'Enum type item_state already applied on data_item.item_state';
END;
$$;

------------------------------------------------------------------------------------------
-- Convert location.location_country to enum location_country
DO $$
DECLARE
  invalid_values TEXT[];
BEGIN
  SELECT ARRAY_AGG(DISTINCT location_country)
  INTO invalid_values
  FROM location
  WHERE location_country IS NOT NULL
    AND location_country::TEXT NOT IN (
      SELECT enumlabel
      FROM pg_enum
      JOIN pg_type ON pg_enum.enumtypid = pg_type.oid
      WHERE pg_type.typname = 'location_country'
    );

  IF invalid_values IS NOT NULL THEN
    RAISE WARNING 'Invalid values found in location_country: %', invalid_values;
    UPDATE location
    SET location_country = NULL
    WHERE location_country = ANY(invalid_values);
  END IF;

  ALTER TABLE location
    ALTER COLUMN location_country TYPE location_country USING location_country::location_country;

EXCEPTION
  WHEN undefined_column THEN
    RAISE WARNING 'Column location.location_country does not exist';
  WHEN invalid_parameter_value THEN
    RAISE WARNING 'Enum type location_country already applied on location.location_country';
END;
$$;

------------------------------------------------------------------------------------------
-- Convert storage_config.config_type to enum config_type
DO $$
DECLARE
  invalid_values TEXT[];
BEGIN
  -- Drop default before conversion
  ALTER TABLE storage_config
    ALTER COLUMN config_type DROP DEFAULT;

  SELECT ARRAY_AGG(DISTINCT config_type)
  INTO invalid_values
  FROM storage_config
  WHERE config_type IS NOT NULL
    AND config_type::TEXT NOT IN (
      SELECT enumlabel
      FROM pg_enum
      JOIN pg_type ON pg_enum.enumtypid = pg_type.oid
      WHERE pg_type.typname = 'config_type'
    );

  IF invalid_values IS NOT NULL THEN
    RAISE WARNING 'Invalid values found in config_type: %', invalid_values;
    UPDATE storage_config
    SET config_type = NULL
    WHERE config_type = ANY(invalid_values);
  END IF;

  ALTER TABLE storage_config
    ALTER COLUMN config_type TYPE config_type USING config_type::config_type;

  -- Restore default
  ALTER TABLE storage_config
    ALTER COLUMN config_type SET DEFAULT 'rclone';

EXCEPTION
  WHEN undefined_column THEN
    RAISE WARNING 'Column storage_config.config_type does not exist';
  WHEN invalid_parameter_value THEN
    RAISE WARNING 'Enum type config_type already applied on storage_config.config_type';
END;
$$;

------------------------------------------------------------------------------------------
-- Convert storage.storage_type to enum storage_type
DO $$
DECLARE
  invalid_values TEXT[];
BEGIN

  SELECT ARRAY_AGG(DISTINCT storage_type)
  INTO invalid_values
  FROM storage
  WHERE storage_type IS NOT NULL
    AND storage_type::TEXT NOT IN (
      SELECT enumlabel
      FROM pg_enum
      JOIN pg_type ON pg_enum.enumtypid = pg_type.oid
      WHERE pg_type.typname = 'storage_type'
    );

  IF invalid_values IS NOT NULL THEN
    RAISE WARNING 'Invalid values found in storage_type: %', invalid_values;
    UPDATE storage
    SET storage_type = NULL
    WHERE storage_type = ANY(invalid_values);
  END IF;

  ALTER TABLE storage
    ALTER COLUMN storage_type TYPE storage_type USING storage_type::storage_type;

EXCEPTION
  WHEN undefined_column THEN
    RAISE WARNING 'Column storage.storage_type does not exist';
  WHEN invalid_parameter_value THEN
    RAISE WARNING 'Enum type storage_type already applied on storage.storage_type';
END;
$$;

------------------------------------------------------------------------------------------
-- Convert storage.storage_interface to enum storage_interface
DO $$
DECLARE
  invalid_values TEXT[];
BEGIN
  SELECT ARRAY_AGG(DISTINCT storage_interface)
  INTO invalid_values
  FROM storage
  WHERE storage_interface IS NOT NULL
    AND storage_interface::TEXT NOT IN (
      SELECT enumlabel
      FROM pg_enum
      JOIN pg_type ON pg_enum.enumtypid = pg_type.oid
      WHERE pg_type.typname = 'storage_interface'
    );

  IF invalid_values IS NOT NULL THEN
    RAISE WARNING 'Invalid values found in storage_interface: %', invalid_values;
    UPDATE storage
    SET storage_interface = NULL
    WHERE storage_interface = ANY(invalid_values);
  END IF;

  ALTER TABLE storage
    ALTER COLUMN storage_interface TYPE storage_interface USING storage_interface::storage_interface;

EXCEPTION
  WHEN undefined_column THEN
    RAISE WARNING 'Column storage.storage_interface does not exist';
  WHEN invalid_parameter_value THEN
    RAISE WARNING 'Enum type storage_interface already applied on storage.storage_interface';
END;
$$;

------------------------------------------------------------------------------------------
-- Convert storage.storage_phase to enum phase_type
DO $$
DECLARE
  invalid_values TEXT[];
BEGIN
  -- Drop default before conversion
  ALTER TABLE storage
    ALTER COLUMN storage_phase DROP DEFAULT;

  SELECT ARRAY_AGG(DISTINCT storage_phase)
  INTO invalid_values
  FROM storage
  WHERE storage_phase IS NOT NULL
    AND storage_phase::TEXT NOT IN (
      SELECT enumlabel
      FROM pg_enum
      JOIN pg_type ON pg_enum.enumtypid = pg_type.oid
      WHERE pg_type.typname = 'phase_type'
    );

  IF invalid_values IS NOT NULL THEN
    RAISE WARNING 'Invalid values found in storage_phase: %', invalid_values;
    UPDATE storage
    SET storage_phase = NULL
    WHERE storage_phase = ANY(invalid_values);
  END IF;

  ALTER TABLE storage
    ALTER COLUMN storage_phase TYPE phase_type USING storage_phase::phase_type;

  -- Restore default
  ALTER TABLE storage
    ALTER COLUMN storage_phase SET DEFAULT 'GAS';

EXCEPTION
  WHEN undefined_column THEN
    RAISE WARNING 'Column storage.storage_phase does not exist';
  WHEN invalid_parameter_value THEN
    RAISE WARNING 'Enum type phase_type already applied on storage.storage_phase';
END;
$$;

------------------------------------------------------------------------------------------
-- Convert data_item.uid_phase to enum phase_type
DO $$
DECLARE
  invalid_values TEXT[];
BEGIN
  -- Drop default before conversion
  ALTER TABLE data_item
    ALTER COLUMN uid_phase DROP DEFAULT;

  SELECT ARRAY_AGG(DISTINCT uid_phase)
  INTO invalid_values
  FROM data_item
  WHERE uid_phase IS NOT NULL
    AND uid_phase::TEXT NOT IN (
      SELECT enumlabel
      FROM pg_enum
      JOIN pg_type ON pg_enum.enumtypid = pg_type.oid
      WHERE pg_type.typname = 'phase_type'
    );

  IF invalid_values IS NOT NULL THEN
    RAISE WARNING 'Invalid values found in uid_phase: %', invalid_values;
    UPDATE data_item
    SET uid_phase = NULL
    WHERE uid_phase = ANY(invalid_values);
  END IF;

  ALTER TABLE data_item
    ALTER COLUMN uid_phase TYPE phase_type USING uid_phase::phase_type;

  -- Restore default
  ALTER TABLE data_item
    ALTER COLUMN uid_phase SET DEFAULT 'GAS';

EXCEPTION
  WHEN undefined_column THEN
    RAISE WARNING 'Column data_item.uid_phase does not exist';
  WHEN invalid_parameter_value THEN
    RAISE WARNING 'Enum type phase_type already applied on data_item.uid_phase';
END;
$$;

------------------------------------------------------------------------------------------
-- Convert data_item.oid_phase to enum phase_type
DO $$
DECLARE
  invalid_values TEXT[];
BEGIN
  -- Drop default before conversion
  ALTER TABLE data_item
    ALTER COLUMN oid_phase DROP DEFAULT;

  SELECT ARRAY_AGG(DISTINCT oid_phase)
  INTO invalid_values
  FROM data_item
  WHERE oid_phase IS NOT NULL
    AND oid_phase::TEXT NOT IN (
      SELECT enumlabel
      FROM pg_enum
      JOIN pg_type ON pg_enum.enumtypid = pg_type.oid
      WHERE pg_type.typname = 'phase_type'
    );

  IF invalid_values IS NOT NULL THEN
    RAISE WARNING 'Invalid values found in oid_phase: %', invalid_values;
    UPDATE data_item
    SET oid_phase = NULL
    WHERE oid_phase = ANY(invalid_values);
  END IF;

  ALTER TABLE data_item
    ALTER COLUMN oid_phase TYPE phase_type USING oid_phase::phase_type;

  -- Restore default
  ALTER TABLE data_item
    ALTER COLUMN oid_phase SET DEFAULT 'GAS';

EXCEPTION
  WHEN undefined_column THEN
    RAISE WARNING 'Column data_item.oid_phase does not exist';
  WHEN invalid_parameter_value THEN
    RAISE WARNING 'Enum type phase_type already applied on data_item.oid_phase';
END;
$$;

------------------------------------------------------------------------------------------
-- Convert data_item.checksum_method to enum checksum_method
DO $$
DECLARE
  invalid_values TEXT[];
BEGIN
  -- Drop default before conversion
  ALTER TABLE data_item
    ALTER COLUMN checksum_method DROP DEFAULT;

  SELECT ARRAY_AGG(DISTINCT checksum_method)
  INTO invalid_values
  FROM data_item
  WHERE checksum_method IS NOT NULL
    AND checksum_method::TEXT NOT IN (
      SELECT enumlabel
      FROM pg_enum
      JOIN pg_type ON pg_enum.enumtypid = pg_type.oid
      WHERE pg_type.typname = 'checksum_method'
    );

  IF invalid_values IS NOT NULL THEN
    RAISE WARNING 'Invalid values found in checksum_method: %', invalid_values;
    UPDATE data_item
    SET checksum_method = NULL
    WHERE checksum_method = ANY(invalid_values);
  END IF;

  ALTER TABLE data_item
    ALTER COLUMN checksum_method TYPE checksum_method USING checksum_method::checksum_method;

  -- Restore default
  ALTER TABLE data_item
    ALTER COLUMN checksum_method SET DEFAULT 'none';

EXCEPTION
  WHEN undefined_column THEN
    RAISE WARNING 'Column data_item.checksum_method does not exist';
  WHEN invalid_parameter_value THEN
    RAISE WARNING 'Enum type checksum_method already applied on data_item.checksum_method';
END;
$$;

------------------------------------------------------------------------------------------
-- Convert data_item.item_mime_type to enum mime_type
DO $$
DECLARE
  invalid_values TEXT[];
BEGIN
  -- Drop default before conversion
  ALTER TABLE data_item
    ALTER COLUMN item_mime_type DROP DEFAULT;

  SELECT ARRAY_AGG(DISTINCT item_mime_type)
  INTO invalid_values
  FROM data_item
  WHERE item_mime_type IS NOT NULL
    AND item_mime_type::TEXT NOT IN (
      SELECT enumlabel
      FROM pg_enum
      JOIN pg_type ON pg_enum.enumtypid = pg_type.oid
      WHERE pg_type.typname = 'mime_type'
    );

  IF invalid_values IS NOT NULL THEN
    RAISE WARNING 'Invalid values found in item_mime_type: %', invalid_values;
    UPDATE data_item
    SET item_mime_type = NULL
    WHERE item_mime_type = ANY(invalid_values);
  END IF;

  ALTER TABLE data_item
    ALTER COLUMN item_mime_type TYPE mime_type USING item_mime_type::mime_type;

  -- Restore default
  ALTER TABLE data_item
    ALTER COLUMN item_mime_type SET DEFAULT 'application/octet-stream';

EXCEPTION
  WHEN undefined_column THEN
    RAISE WARNING 'Column data_item.item_mime_type does not exist';
  WHEN invalid_parameter_value THEN
    RAISE WARNING 'Enum type mime_type already applied on data_item.item_mime_type';
END;
$$;
