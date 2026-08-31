
-- SQL script for release 2.4

--changeset dlm:2.4-release context:2.4-release

--- Migration changes
ALTER TABLE dlm.migration ADD COLUMN IF NOT EXISTS dependency varchar;
