--liquibase formatted sql

--changeset dlm:create-database context:create-db runInTransaction:false
CREATE DATABASE ska_dlm WITH TEMPLATE = template0 ENCODING = 'UTF8' LOCALE = 'en_US.utf8';