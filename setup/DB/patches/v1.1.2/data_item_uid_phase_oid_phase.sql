-- Rename 'item_phase' column in 'data_item' table to 'uid_phase'
-- Add new 'oid_phase' column to 'data_item' table
ALTER TABLE public.data_item
    RENAME COLUMN item_phase TO uid_phase,
    ADD COLUMN oid_phase VARCHAR DEFAULT 'GAS';

-- Rename 'storage_phase_level' column in 'storage' table to 'storage_phase'
ALTER TABLE public.storage
    RENAME COLUMN storage_phase_level TO storage_phase;