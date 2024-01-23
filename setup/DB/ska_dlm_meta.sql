--
-- ska_dlm_adminQL DDL for SKA Data Life Cycle management DB setup
--

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: ska_dlm_meta; Type: DATABASE; Schema: -; Owner: ska_dlm_admin
-- TODO: create user for DLM
CREATE GROUP ska_dlm;
CREATE USER ska_dlm_admin WITH CREATEDB CREATEROLE IN GROUP ska_dlm PASSWORD 'mysecretpassword';


CREATE DATABASE ska_dlm_meta WITH TEMPLATE = template0 ENCODING = 'UTF8' LOCALE = 'en_US.utf8';
ALTER DATABASE ska_dlm_meta OWNER TO ska_dlm_admin;
\c ska_dlm_meta
SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;
SET default_tablespace = '';
SET default_table_access_method = heap;

DROP TABLE IF EXISTS public.location;
CREATE TABLE public.location (
    location_id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    location_name varchar NOT NULL,
    location_type varchar NOT NULL,
    location_country varchar DEFAULT NULL,
    location_place varchar DEFAULT NULL,
    location_date timestamp without time zone DEFAULT now()
);
ALTER TABLE public.location OWNER TO ska_dlm_admin;



DROP TABLE IF EXISTS public.storage;
CREATE TABLE public.storage (
    storage_id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    location_id uuid NOT NULL,
    storage_type varchar NOT NULL,
    storage_interface varchar NOT NULL,
    storage_capacity BIGINT DEFAULT -1,
    storage_used NUMERIC(3,1) DEFAULT 0.0,
    storage_checked BOOLEAN DEFAULT FALSE,
    storage_checksum varchar DEFAULT NULL,
    storage_last_checked TIMESTAMP without time zone DEFAULT NULL,
    storage_num_objects BIGINT DEFAULT 0,
    storage_available BOOLEAN DEFAULT True,
    storage_retired BOOLEAN DEFAULT False,
    storage_retire_date TIMESTAMP without time zone DEFAULT NULL,
    storage_date timestamp without time zone DEFAULT now(),
    CONSTRAINT fk_location
      FOREIGN KEY(location_id) 
      REFERENCES public.location(location_id)
      ON DELETE SET NULL
);
ALTER TABLE public.storage OWNER TO ska_dlm_admin;
DROP TABLE IF EXISTS public.data_item;
CREATE TABLE public.data_item (
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
    item_phase varchar DEFAULT 'gas',
    item_state varchar DEFAULT 'initialized',
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
    CONSTRAINT fk_storage
      FOREIGN KEY(storage_id)
      REFERENCES public.storage(storage_id)
      ON DELETE SET NULL
);
ALTER TABLE public.data_item OWNER TO ska_dlm_admin;
CREATE INDEX idx_fk_storage_id ON public.data_item USING btree (storage_id);

CREATE UNIQUE INDEX idx_unq_OID_UID_item_version ON public.data_item USING btree (OID, UID, item_version);
CREATE FUNCTION public.sync_oid_uid() RETURNS trigger AS $$
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
  public.data_item
FOR EACH ROW EXECUTE PROCEDURE
  public.sync_oid_uid();

--
-- Table phase_change
--
DROP TABLE IF EXISTS public.phase_change;
DROP TABLE IF EXISTS public.phase_change;

CREATE TABLE public.phase_change (
    phase_change_ID bigint GENERATED always as IDENTITY PRIMARY KEY,
    OID uuid NOT NULL,
    requested_phase varchar DEFAULT 'gas',
    request_creation timestamp without time zone DEFAULT now()
);
ALTER TABLE public.phase_change OWNER TO ska_dlm_admin;
ALTER TABLE public.phase_change OWNER TO ska_dlm_admin;
