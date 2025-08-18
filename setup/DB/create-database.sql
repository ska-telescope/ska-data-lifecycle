CREATE DATABASE ska_dlm_meta WITH TEMPLATE = template0 ENCODING = 'UTF8' LOCALE = 'en_US.utf8';
-- Ensure schema + required extension exist
CREATE SCHEMA IF NOT EXISTS dlm;
CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public;