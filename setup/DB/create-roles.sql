-- TODO: create user for DLM
CREATE GROUP ska_dlm;
CREATE USER ska_dlm_admin WITH CREATEDB CREATEROLE IN GROUP ska_dlm PASSWORD 'mysecretpassword';
