
-- SQL script for release 2.5

--changeset dlm:2.5-release

--- Migration changes

--- NOTE: 
--- Using uid and oid which assumes its all on the same storage system. 
--- Migration does not currently support cross storage system references using oids.

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
