--
-- SQL DDL for SKA Data Lifecycle Management DB setup
--

-- Use dlm first for unqualified names in this session
SET search_path = dlm, public;

--
-- Lookup tables
--
CREATE TABLE IF NOT EXISTS location_facility (
    id TEXT PRIMARY KEY
);

INSERT INTO location_facility (id)
SELECT unnest(ARRAY['SRC', 'STFC', 'AWS', 'Google', 'Pawsey Centre', 'external', 'local'])
ON CONFLICT DO NOTHING;

--
-- Table: location
--
CREATE TABLE IF NOT EXISTS location (
    location_id         uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    location_name       varchar NOT NULL UNIQUE,
    location_type       location_type NOT NULL,
    location_country    location_country DEFAULT NULL,
    location_city       varchar DEFAULT NULL,
    location_facility   TEXT DEFAULT NULL REFERENCES dlm.location_facility(id),
    location_check_url  varchar DEFAULT NULL,
    location_last_check timestamp without time zone DEFAULT NULL,
    location_date       timestamp without time zone DEFAULT now()
);

--
-- Table: storage
--
CREATE TABLE IF NOT EXISTS storage (
    storage_id           uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    location_id          uuid NOT NULL,
    storage_name         varchar NOT NULL UNIQUE,
    root_directory       varchar DEFAULT NULL,
    storage_type         storage_type NOT NULL,
    storage_interface    storage_interface NOT NULL,
    storage_phase        phase_type DEFAULT 'GAS',
    storage_capacity     BIGINT DEFAULT -1,
    storage_use_pct      NUMERIC(3,1) DEFAULT 0.0,
    storage_permissions  varchar DEFAULT 'RW',
    storage_checked      BOOLEAN DEFAULT FALSE,
    storage_check_url    varchar DEFAULT NULL,
    storage_last_checked timestamp without time zone DEFAULT NULL,
    storage_num_objects  BIGINT DEFAULT 0,
    storage_available    BOOLEAN DEFAULT TRUE,
    storage_retired      BOOLEAN DEFAULT FALSE,
    storage_retire_date  timestamp without time zone DEFAULT NULL,
    storage_date         timestamp without time zone DEFAULT now(),
    CONSTRAINT fk_location
      FOREIGN KEY (location_id)
      REFERENCES dlm.location(location_id)
      ON DELETE SET NULL
);

--
-- Table: storage_config
-- Holds a JSON config for accessing a storage via a given mechanism (default rclone).
-- If the mechanism requires something else than JSON this will be
-- converted by the storage_manager software. Being a separate table
-- this allows for multiple configurations for different mechanisms.
--
CREATE TABLE IF NOT EXISTS storage_config (
    config_id   uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    storage_id  uuid NOT NULL,
    config_type config_type DEFAULT 'rclone',
    config      json NOT NULL,
    config_date timestamp without time zone DEFAULT now(),
    CONSTRAINT fk_cfg_storage_id
      FOREIGN KEY (storage_id)
      REFERENCES dlm.storage(storage_id)
      ON DELETE SET NULL
);

--
-- Table: data_item
--
CREATE TABLE IF NOT EXISTS data_item (
    UID               uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    OID               uuid DEFAULT NULL,
    item_version      integer DEFAULT 1,
    item_name         varchar DEFAULT NULL,
    item_tags         json DEFAULT NULL,
    storage_id        uuid DEFAULT NULL,
    URI               varchar DEFAULT 'inline://item_value',
    item_value        text DEFAULT '',
    item_type         varchar DEFAULT 'file',
    item_format       varchar DEFAULT 'unknown',
    item_encoding     varchar DEFAULT 'unknown',
    item_mime_type    mime_type DEFAULT 'application/octet-stream',
    item_level        smallint DEFAULT -1,
    uid_phase         phase_type DEFAULT 'GAS',
    oid_phase         phase_type DEFAULT 'GAS',
    item_state        item_state DEFAULT 'INITIALISED',
    UID_creation      timestamp without time zone DEFAULT now(),
    OID_creation      timestamp without time zone DEFAULT NULL,
    UID_expiration    timestamp without time zone DEFAULT now() + time '24:00',
    OID_expiration    timestamp without time zone DEFAULT '2099-12-31 23:59:59',
    UID_deletion      timestamp without time zone DEFAULT NULL,
    OID_deletion      timestamp without time zone DEFAULT NULL,
    expired           boolean DEFAULT FALSE,
    deleted           boolean DEFAULT FALSE,
    last_access       timestamp without time zone,
    item_checksum     varchar,
    checksum_method   checksum_method DEFAULT 'none',
    last_check        timestamp without time zone,
    item_owner        varchar DEFAULT 'SKA',
    item_group        varchar DEFAULT 'SKA',
    ACL               json DEFAULT NULL,
    activate_method   varchar DEFAULT NULL,
    item_size         integer DEFAULT NULL,
    decompressed_size integer DEFAULT NULL,
    compression_method varchar DEFAULT NULL,
    parents           uuid DEFAULT NULL,
    children          uuid DEFAULT NULL,
    metadata          jsonb DEFAULT NULL,
    CONSTRAINT fk_storage
      FOREIGN KEY (storage_id)
      REFERENCES dlm.storage(storage_id)
      ON DELETE SET NULL
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_fk_storage_id ON dlm.data_item USING btree (storage_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_unq_OID_UID_item_version
    ON dlm.data_item USING btree (OID, UID, item_version);

-- Trigger function to sync OID/UID fields
CREATE OR REPLACE FUNCTION dlm.sync_oid_uid() RETURNS trigger AS $$
  DECLARE oidc RECORD;
  DECLARE tnow timestamp DEFAULT now();
  BEGIN
    NEW.UID_creation := tnow;
    IF NEW.OID IS NULL THEN
        NEW.OID := NEW.UID;
        NEW.OID_creation := tnow;
    ELSE
        FOR oidc IN SELECT OID, OID_creation FROM data_item WHERE UID = NEW.OID LOOP
            NEW.OID := oidc.OID;
            NEW.OID_creation := oidc.OID_creation;
        END LOOP;
    END IF;
    RETURN NEW;
  END
$$ LANGUAGE plpgsql;

-- Trigger (note: trigger names are not schema-qualified)
DROP TRIGGER IF EXISTS sync_oid_uid ON dlm.data_item;
CREATE TRIGGER sync_oid_uid
BEFORE INSERT ON dlm.data_item
FOR EACH ROW EXECUTE FUNCTION dlm.sync_oid_uid();

--
-- Table: phase_change
--
CREATE TABLE IF NOT EXISTS phase_change (
    phase_change_ID  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    OID              uuid NOT NULL,
    requested_phase  phase_type DEFAULT 'GAS',
    request_creation timestamp without time zone DEFAULT now()
);

--
-- Table: migration
--
CREATE TABLE IF NOT EXISTS migration (
    migration_id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    job_id                  bigint NOT NULL,
    OID                     uuid NOT NULL,
    URL                     varchar NOT NULL,
    source_storage_id       uuid NOT NULL,
    destination_storage_id  uuid NOT NULL,
    "user"                  varchar DEFAULT 'SKA',
    "group"                 varchar DEFAULT 'SKA',
    job_status              jsonb DEFAULT NULL,
    job_stats               jsonb DEFAULT NULL,
    complete                boolean DEFAULT FALSE,
    "date"                  timestamp without time zone DEFAULT now(),
    completion_date         timestamp without time zone DEFAULT NULL,
    CONSTRAINT fk_source_storage
      FOREIGN KEY (source_storage_id)
      REFERENCES dlm.storage(storage_id)
      ON DELETE SET NULL,
    CONSTRAINT fk_destination_storage
      FOREIGN KEY (destination_storage_id)
      REFERENCES dlm.storage(storage_id)
      ON DELETE SET NULL
);

