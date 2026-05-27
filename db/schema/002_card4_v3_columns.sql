-- Additive card_slots columns for Card 4 formula/calculation payloads.
-- Existing DBs created at schema version 1 lack these columns; cold DBs apply
-- 001 first, then this migration.

ALTER TABLE card_slots ADD COLUMN cfa_lens_formula TEXT;
ALTER TABLE card_slots ADD COLUMN cfa_lens_calculation TEXT;
