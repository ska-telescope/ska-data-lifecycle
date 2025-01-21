--
-- ska_dlm_adminQL DDL for SKA Data Lifecycle Management DB setup
--

--
-- Table location
--

CREATE TABLE location (
    location_id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    location_name varchar NOT NULL UNIQUE,
    location_type varchar NOT NULL,
    location_country varchar DEFAULT NULL,
    location_city varchar DEFAULT NULL,
    location_facility varchar DEFAULT NULL,
    location_check_url varchar DEFAULT NULL,
    location_last_check TIMESTAMP without time zone DEFAULT NULL,
    location_date timestamp without time zone DEFAULT now()
);
ALTER TABLE location OWNER TO ska_dlm_admin;

--
-- Table storage
--

CREATE TABLE storage (
    storage_id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    location_id uuid NOT NULL,
    storage_name varchar NOT NULL UNIQUE,
    storage_type varchar NOT NULL,
    storage_interface varchar NOT NULL,
    storage_phase_level varchar DEFAULT 'GAS',
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
    root_directory varchar DEFAULT NULL,
    CONSTRAINT fk_location
      FOREIGN KEY(location_id)
      REFERENCES location(location_id)
      ON DELETE SET NULL
);
ALTER TABLE storage OWNER TO ska_dlm_admin;

--
-- Table storage_config holds a JSON version of the configuration
-- to access the storage using a specific mechanism (default rclone).
-- If the mechanism requires something else than JSON this will be
-- converted by the storage_manager software. Being a separate table
-- this allows for multiple configurations for different mechanisms.
--
CREATE TABLE storage_config (
    config_id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    storage_id uuid NOT NULL,
    config_type varchar DEFAULT 'rclone',
    config json NOT NULL,
    config_date timestamp without time zone DEFAULT now(),
    CONSTRAINT fk_cfg_storage_id
      FOREIGN KEY(storage_id)
      REFERENCES storage(storage_id)
      ON DELETE SET NULL
);
ALTER TABLE storage_config OWNER TO ska_dlm_admin;


--
-- Table data_item
--

CREATE TABLE data_item (
    UID uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    OID uuid DEFAULT NULL,
    item_version integer DEFAULT 1,
    item_name varchar DEFAULT NULL,
    item_tags json DEFAULT NULL,
    storage_id uuid DEFAULT NULL,
    URI varchar DEFAULT 'inline://item_value',
    item_value text DEFAULT '',
    item_type varchar DEFAULT 'unknown',
    item_format varchar DEFAULT 'unknown',
    item_encoding varchar DEFAULT 'unknown',
    item_mime_type varchar DEFAULT 'application/octet-stream',
    item_level smallint DEFAULT -1,
    item_phase varchar DEFAULT 'GAS',
    item_state varchar DEFAULT 'INITIALIZED',
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
    checksum_method varchar DEFAULT 'none',
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
    metadata json DEFAULT NULL,
    CONSTRAINT fk_storage
      FOREIGN KEY(storage_id)
      REFERENCES storage(storage_id)
      ON DELETE SET NULL
);
ALTER TABLE data_item OWNER TO ska_dlm_admin;
CREATE INDEX idx_fk_storage_id ON data_item USING btree (storage_id);

CREATE UNIQUE INDEX idx_unq_OID_UID_item_version ON data_item USING btree (OID, UID, item_version);
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

CREATE TABLE phase_change (
    phase_change_ID bigint GENERATED always as IDENTITY PRIMARY KEY,
    OID uuid NOT NULL,
    requested_phase varchar DEFAULT 'GAS',
    request_creation timestamp without time zone DEFAULT now()
);
ALTER TABLE phase_change OWNER TO ska_dlm_admin;


--
-- Table migration
--

CREATE TABLE migration (
    migration_id bigint GENERATED always as IDENTITY PRIMARY KEY,
    job_id bigint NOT NULL,
    OID uuid NOT NULL,
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
ALTER TABLE migration OWNER TO ska_dlm_admin;