--
-- SQL DDL for SKA Data Lifecycle Management DB setup
--

--
-- lookup tables
--

CREATE TABLE location_facility (
    id TEXT PRIMARY KEY
);

INSERT INTO location_facility (id)
SELECT unnest(ARRAY['SRC', 'STFC', 'AWS', 'Google', 'Pawsey Centre', 'external', 'local'])
ON CONFLICT DO NOTHING;

--
-- Table location
--

CREATE TABLE IF NOT EXISTS location (
    location_id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    location_name varchar NOT NULL UNIQUE,
    location_type TEXT NOT NULL REFERENCES location_type(id),
    location_country location_country DEFAULT NULL,
    location_city varchar DEFAULT NULL,
    location_facility varchar DEFAULT NULL,
    location_check_url varchar DEFAULT NULL,
    location_last_check TIMESTAMP without time zone DEFAULT NULL,
    location_date timestamp without time zone DEFAULT now()
);

--
-- Table storage
--

CREATE TABLE IF NOT EXISTS storage (
    storage_id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    location_id uuid NOT NULL,
    storage_name varchar NOT NULL UNIQUE,
    root_directory varchar DEFAULT NULL,
    storage_type storage_type NOT NULL,
    storage_interface storage_interface NOT NULL,
    storage_phase phase_type DEFAULT 'GAS',
    storage_capacity BIGINT DEFAULT -1,
    storage_use_pct NUMERIC(3,1) DEFAULT 0.0,
    storage_permissions varchar DEFAULT 'RW',
    storage_checked BOOLEAN DEFAULT FALSE,
    storage_check_url varchar DEFAULT NULL,
    storage_last_checked TIMESTAMP without time zone DEFAULT NULL,
    storage_num_objects BIGINT DEFAULT 0,
    storage_available BOOLEAN DEFAULT True,
    storage_retired BOOLEAN DEFAULT False,
    storage_retire_date TIMESTAMP without time zone DEFAULT NULL,
    storage_date timestamp without time zone DEFAULT now(),
    CONSTRAINT fk_location
      FOREIGN KEY(location_id)
      REFERENCES location(location_id)
      ON DELETE SET NULL
);

--
-- Table storage_config holds a JSON version of the configuration
-- to access the storage using a specific mechanism (default rclone).
-- If the mechanism requires something else than JSON this will be
-- converted by the storage_manager software. Being a separate table
-- this allows for multiple configurations for different mechanisms.
--
CREATE TABLE IF NOT EXISTS storage_config (
    config_id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    storage_id uuid NOT NULL,
    config_type config_type DEFAULT 'rclone',
    config json NOT NULL,
    config_date timestamp without time zone DEFAULT now(),
    CONSTRAINT fk_cfg_storage_id
      FOREIGN KEY(storage_id)
      REFERENCES storage(storage_id)
      ON DELETE SET NULL
);


--
-- Table data_item
--

CREATE TABLE IF NOT EXISTS data_item (
    UID uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    OID uuid DEFAULT NULL,
    item_version integer DEFAULT 1,
    item_name varchar DEFAULT NULL,
    item_tags json DEFAULT NULL,
    storage_id uuid DEFAULT NULL,
    URI varchar DEFAULT 'inline://item_value',
    item_value text DEFAULT '',
    item_type varchar DEFAULT 'file',
    item_format varchar DEFAULT 'unknown',
    item_encoding varchar DEFAULT 'unknown',
    item_mime_type mime_type DEFAULT 'application/octet-stream',
    item_level smallint DEFAULT -1,
    uid_phase phase_type DEFAULT 'GAS',
    oid_phase phase_type DEFAULT 'GAS',
    item_state item_state DEFAULT 'INITIALISED',
    UID_creation timestamp without time zone DEFAULT now(),
    OID_creation timestamp without time zone DEFAULT NULL,
    UID_expiration timestamp without time zone DEFAULT now() + time '24:00',
    OID_expiration timestamp without time zone DEFAULT '2099-12-31 23:59:59',
    UID_deletion timestamp without time zone DEFAULT NULL,
    OID_deletion timestamp without time zone DEFAULT NULL,
    expired boolean DEFAULT false,
    deleted boolean DEFAULT false,
    last_access timestamp without time zone,
    item_checksum varchar,
    checksum_method checksum_method DEFAULT 'none',
    last_check timestamp without time zone,
    item_owner varchar DEFAULT 'SKA',
    item_group varchar DEFAULT 'SKA',
    ACL json DEFAULT NULL,
    activate_method varchar DEFAULT NULL,
    item_size integer DEFAULT NULL,
    decompressed_size integer DEFAULT NULL,
    compression_method varchar DEFAULT NULL,
    parents uuid DEFAULT NULL,
    children uuid DEFAULT NULL,
    metadata jsonb DEFAULT NULL,
    CONSTRAINT fk_storage
      FOREIGN KEY(storage_id)
      REFERENCES storage(storage_id)
      ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_fk_storage_id ON data_item USING btree (storage_id);

CREATE UNIQUE INDEX IF NOT EXISTS idx_unq_OID_UID_item_version ON data_item USING btree (OID, UID, item_version);
CREATE FUNCTION sync_oid_uid() RETURNS trigger AS $$
  DECLARE oidc RECORD;
  DECLARE tnow timestamp DEFAULT now();
  BEGIN
    NEW.UID_creation := tnow;
    IF new.OID is NULL THEN
        NEW.OID := NEW.UID;
        NEW.OID_creation := tnow;
    ELSE
        FOR oidc in SELECT OID, OID_creation from data_item where UID = NEW.OID LOOP
            NEW.OID := oidc.OID;
            NEW.OID_creation := oidc.OID_creation;
        END LOOP;
    END IF;
    RETURN NEW;
  END
$$ LANGUAGE plpgsql;


CREATE TRIGGER
  sync_oid_uid
BEFORE INSERT ON
  data_item
FOR EACH ROW EXECUTE PROCEDURE
  sync_oid_uid();

--
-- Table phase_change
--

CREATE TABLE IF NOT EXISTS phase_change (
    phase_change_ID bigint GENERATED always as IDENTITY PRIMARY KEY,
    OID uuid NOT NULL,
    requested_phase phase_type DEFAULT 'GAS',
    request_creation timestamp without time zone DEFAULT now()
);


--
-- Table migration
--

CREATE TABLE IF NOT EXISTS migration (
    migration_id bigint GENERATED always as IDENTITY PRIMARY KEY,
    job_id bigint NOT NULL,
    OID uuid NOT NULL,
    URL varchar NOT NULL,
    source_storage_id uuid NOT NULL,
    destination_storage_id uuid NOT NULL,
    "user" varchar DEFAULT 'SKA',
    "group" varchar DEFAULT 'SKA',
    job_status jsonb DEFAULT NULL,
    job_stats jsonb DEFAULT NULL,
    complete boolean DEFAULT false,
    "date" timestamp without time zone DEFAULT now(),
    completion_date timestamp without time zone DEFAULT NULL,
    CONSTRAINT fk_source_storage
      FOREIGN KEY(source_storage_id)
      REFERENCES storage(storage_id)
      ON DELETE SET NULL,
    CONSTRAINT fk_destination_storage
      FOREIGN KEY(destination_storage_id)
      REFERENCES storage(storage_id)
      ON DELETE SET NULL
);

