-- This patch defines enum types. Safe to re-run.

DO $$
BEGIN
  CREATE TYPE location_type AS ENUM ('src', 'aws', 'gcs', 'low-operational', 'low-itf', 'mid-itf', 'dp', 'external');
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
    RAISE NOTICE 'One or more enum types already exist. Skipping creation.';
END;
$$;

-- This patch continues with updates table columns to use new enum types. Safe to re-run.

DO $$
BEGIN
  -- Update public.location
  BEGIN
    ALTER TABLE public.location
      ALTER COLUMN location_type TYPE location_type USING location_type::location_type,
      ALTER COLUMN location_country TYPE location_country USING location_country::location_country;
  EXCEPTION
    WHEN undefined_column THEN
      RAISE NOTICE 'One or more columns in public.location do not exist';
    WHEN invalid_parameter_value THEN
      RAISE NOTICE 'Enum type already applied on public.location';
  END;

  -- Update public.storage
  BEGIN
    ALTER TABLE public.storage
      ALTER COLUMN storage_type TYPE storage_type USING storage_type::storage_type,
      ALTER COLUMN storage_interface TYPE storage_interface USING storage_interface::storage_interface,
      ALTER COLUMN storage_phase TYPE phase_type USING storage_phase::phase_type;
  EXCEPTION
    WHEN undefined_column THEN
      RAISE NOTICE 'One or more columns in public.storage do not exist';
    WHEN invalid_parameter_value THEN
      RAISE NOTICE 'Enum type already applied on public.storage';
  END;

  -- Update public.storage_config
  BEGIN
    ALTER TABLE public.storage_config
      ALTER COLUMN config_type TYPE config_type USING config_type::config_type;
  EXCEPTION
    WHEN undefined_column THEN
      RAISE NOTICE 'Column config_type in public.storage_config does not exist';
    WHEN invalid_parameter_value THEN
      RAISE NOTICE 'Enum type already applied on public.storage_config';
  END;

-- Update public.data_item
  BEGIN
    ALTER TABLE public.data_item
      ALTER COLUMN uid_phase TYPE phase_type USING uid_phase::phase_type,
      ALTER COLUMN oid_phase TYPE phase_type USING oid_phase::phase_type,
      ALTER COLUMN item_state TYPE item_state USING (
        CASE item_state
          WHEN 'INITIALIZED' THEN 'INITIALISED'
          ELSE item_state
        END
      )::item_state,
      ALTER COLUMN item_mime_type TYPE mime_type USING item_mime_type::mime_type;
  EXCEPTION
    WHEN undefined_column THEN
      RAISE NOTICE 'One or more columns in public.data_item do not exist';
    WHEN invalid_parameter_value THEN
      RAISE NOTICE 'Enum type already applied on public.data_item';
  END;
END;
$$;
