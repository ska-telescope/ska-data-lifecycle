--liquibase formatted sql

--changeset dlm:create-roles context:create-roles
CREATE GROUP ska_dlm;
CREATE USER ska_dlm_admin WITH CREATEDB CREATEROLE IN GROUP ska_dlm PASSWORD 'mysecretpassword';
