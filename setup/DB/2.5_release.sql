-- SQL script for release 2.5

--changeset dlm:2.5-release

--- Migration changes

ALTER TABLE dlm.migration
    ADD COLUMN IF NOT EXISTS uid uuid,
    ADD COLUMN IF NOT EXISTS destination_uid uuid,
    ADD COLUMN IF NOT EXISTS destination_path varchar,
    ADD COLUMN IF NOT EXISTS execution_id uuid,
    ADD COLUMN IF NOT EXISTS host_id varchar;

UPDATE dlm.migration AS migration
SET uid = (
    SELECT data_item.uid
    FROM dlm.data_item AS data_item
    WHERE data_item.oid = migration.oid
      AND data_item.storage_id = migration.source_storage_id
    ORDER BY data_item.uid_creation, data_item.uid
    LIMIT 1
)
WHERE migration.uid IS NULL;

UPDATE dlm.migration AS migration
SET destination_uid = (
    SELECT data_item.uid
    FROM dlm.data_item AS data_item
    WHERE data_item.oid = migration.oid
      AND data_item.storage_id = migration.destination_storage_id
    ORDER BY data_item.uid_creation, data_item.uid
    LIMIT 1
)
WHERE migration.destination_uid IS NULL;

ALTER TABLE dlm.migration
    ALTER COLUMN job_id DROP NOT NULL,
    ALTER COLUMN url DROP NOT NULL,
    DROP COLUMN oid;

CREATE TABLE IF NOT EXISTS dlm.data_item_children (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    parent_data_item_uid  uuid NOT NULL,
    data_item_uid         uuid NOT NULL,
    CONSTRAINT fk_data_item_children_parent
      FOREIGN KEY (parent_data_item_uid)
      REFERENCES dlm.data_item(UID),
    CONSTRAINT fk_data_item_children_data_item
      FOREIGN KEY (data_item_uid)
      REFERENCES dlm.data_item(UID),
    CONSTRAINT uq_data_item_children_parent_child
      UNIQUE (parent_data_item_uid, data_item_uid)
);

CREATE INDEX IF NOT EXISTS idx_data_item_children_data_item_uid
    ON dlm.data_item_children USING btree (data_item_uid);
