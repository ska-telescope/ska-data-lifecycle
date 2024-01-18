--
-- PostgreSQL DDL for SKA Data Life Cycle management DB setup
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
-- Name: ska_dlm_meta; Type: DATABASE; Schema: -; Owner: postgres
-- TODO: create user for DLM

CREATE DATABASE ska_dlm_meta WITH TEMPLATE = template0 ENCODING = 'UTF8' LOCALE = 'en_US.utf8';
ALTER DATABASE ska_dlm_meta OWNER TO postgres;
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
--
-- Name: data_item; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.data_item (
    UID uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    OID uuid DEFAULT NULL,
    item_version integer DEFAULT 1,
    item_name varchar DEFAULT NULL,
    item_tags json DEFAULT NULL,
    location_id uuid DEFAULT NULL,
    URI varchar DEFAULT 'inline://item_value',
    item_value text DEFAULT '',
    item_type varchar DEFAULT 'unknown',
    item_format varchar DEFAULT 'unknown',
    item_encoding varchar DEFAULT 'unknown',
    item_mime_type varchar DEFAULT 'application/octet-stream',
    item_level smallint DEFAULT -1,
    item_phase varchar DEFAULT 'gas',
    requested_phase varchar DEFAULT 'gas',
    item_state varchar DEFAULT 'initialized',
    UID_creation timestamp without time zone DEFAULT now(),
    OID_creation timestamp without time zone DEFAULT NULL,
    OID_expiration timestamp without time zone DEFAULT '2099-12-31 23:59:59',
    UID_expiration timestamp without time zone DEFAULT now() + time '12:00',
    expired boolean DEFAULT false,
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
    children uuid DEFAULT NULL
);
ALTER TABLE public.data_item OWNER TO postgres;
--
-- Name: idx_fk_location_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_fk_location_id ON public.data_item USING btree (location_id);
--
-- Name: idx_unq_rental_rental_date_inventory_id_customer_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX idx_unq_OID_UID_item_version ON public.data_item USING btree (OID, UID, item_version);
--
-- Name: sync_oid_uid; Type: TRIGGER; Schema: public; Owner: postgres
--    Trigger 
--
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

-- CREATE TABLE public.phase_change (
--     phase_change_ID bigint GENERATED always as IDENTITY PRIMARY KEY,
--     UID uuid NOT NULL,
--     requested_phase varchar DEFAULT 'gas',
--     request_creation timestamp without time zone DEFAULT now(),
-- );
-- ALTER TABLE public.data_item OWNER TO postgres;
-- --
-- -- Name: idx_fk_location_id; Type: INDEX; Schema: public; Owner: postgres
-- --

-- CREATE INDEX idx_fk_uid ON public.phase_change USING btree (uid);
-- --
-- -- Name: idx_unq_rental_rental_date_inventory_id_customer_id; Type: INDEX; Schema: public; Owner: postgres
-- --

-- CREATE UNIQUE INDEX idx_unq_OID_UID_item_version ON public.data_item USING btree (OID, UID, item_version);
-- --