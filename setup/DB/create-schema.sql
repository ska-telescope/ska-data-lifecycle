--liquibase formatted sql

--changeset dlm:create-schema context:create-schema splitStatements:false
-- verify that the user has CREATE permission within the DB before checking existence or creating a schema
DO $$
BEGIN
   IF has_database_privilege(current_user, current_database(), 'CREATE') THEN
   CREATE SCHEMA IF NOT EXISTS dlm;
   END IF;
END $$ LANGUAGE plpgsql;