-- create trigger function for execution_blocks eb_id container data items

--changeset dlm:create-external-triggers context:create-external-triggers runInTransaction:false

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables 
        WHERE table_schema = 'execution' AND table_name = 'execution_blocks'
    ) THEN
        RAISE WARNING 'WARN: Table execution.execution_blocks does not exist. Skipping trigger installation.';
        RETURN;
    END IF;
END $$;


CREATE OR REPLACE FUNCTION fn_insert_eb_data_item() 
RETURNS TRIGGER AS $$
DECLARE
  eb_id text;
BEGIN
  IF NEW.data IS NULL OR NOT (NEW.data ? 'eb_id') THEN
    RETURN NEW;
  END IF;

  eb_id := NEW.data ->> 'eb_id';
  IF eb_id IS NULL OR trim(eb_id) = '' THEN
    RETURN NEW;
  END IF;

  IF NOT EXISTS (
      SELECT 1
      FROM dlm.data_item
      WHERE item_name = eb_id
  ) THEN
    INSERT INTO dlm.data_item (item_name, item_type, uri, uid_phase, oid_phase)
    VALUES (eb_id, 'container', eb_id, 'SOLID', 'SOLID');
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;


-- Only create trigger if table exists
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables 
        WHERE table_schema = 'execution' AND table_name = 'execution_blocks'
    ) THEN
        EXECUTE 'CREATE OR REPLACE TRIGGER trg_insert_eb_data_item AFTER INSERT ON execution.execution_blocks FOR EACH ROW EXECUTE FUNCTION fn_insert_eb_data_item()';
        EXECUTE 'GRANT EXECUTE ON FUNCTION fn_insert_eb_data_item() TO ' || quote_ident(current_user);
    END IF;
END $$;