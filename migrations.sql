-- This is the migration SQL file.
-- Each query here is ALWAYS ran in the dev setup script - make sure they are compatible!
-- Add conviction log table
CREATE TABLE
    IF NOT EXISTS conviction_log (
        discord_id INTEGER,
        reason TEXT,
        'timestamp' INTEGER
    );

CREATE TABLE
    IF NOT EXISTS role_images (role_id INTEGER PRIMARY KEY, image_url TEXT);

BEGIN;

CREATE TABLE
    `sail_credit_log_tmp` (
        discord_id INTEGER,
        party_size INTEGER,
        party_created_at INTEGER,
        party_finished_at INTEGER,
        prev_sail_credit INTEGER,
        new_sail_credit INTEGER,
        source TEXT,
        'timestamp' INTEGER
    );

INSERT INTO
    `sail_credit_log_tmp` (
        `discord_id`,
        `party_size`,
        `party_created_at`,
        `party_finished_at`,
        `prev_sail_credit`,
        `new_sail_credit`,
        `source`,
        `timestamp`
    )
SELECT
    `discord_id`,
    `party_size`,
    `party_created_at`,
    `party_finished_at`,
    `prev_sail_credit`,
    `new_sail_credit`,
    `source`,
    `timestamp`
FROM
    `sail_credit_log`;

DROP TABLE `sail_credit_log`;

ALTER TABLE `sail_credit_log_tmp`
RENAME TO `sail_credit_log`;

COMMIT;