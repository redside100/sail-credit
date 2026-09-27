-- This is the migration SQL file.
-- Each query here is ALWAYS ran in the dev setup script - make sure they are compatible!
-- Add conviction log table
CREATE TABLE IF NOT EXISTS conviction_log (
    discord_id INTEGER,
    reason TEXT,
    'timestamp' INTEGER
);

CREATE TABLE IF NOT EXISTS role_images (role_id INTEGER PRIMARY KEY, image_url TEXT);

-- Season history starts when the first season is explicitly created.
CREATE TABLE IF NOT EXISTS seasons (
    season_id INTEGER PRIMARY KEY,
    start_timestamp INTEGER NOT NULL,
    end_timestamp INTEGER,
    status TEXT NOT NULL CHECK (status IN ('ACTIVE', 'COMPLETED'))
);

CREATE TABLE IF NOT EXISTS user_season_stats (
    discord_id INTEGER NOT NULL,
    season_id INTEGER NOT NULL,
    highest_sail_credit INTEGER NOT NULL,
    highest_rank INTEGER,
    PRIMARY KEY (discord_id, season_id),
    FOREIGN KEY (discord_id) REFERENCES users (discord_id),
    FOREIGN KEY (season_id) REFERENCES seasons (season_id)
);

BEGIN;

CREATE TABLE `sail_credit_log_tmp` (
    discord_id INTEGER,
    season_id INTEGER,
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
        `season_id`,
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
    `season_id`,
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

ALTER TABLE
    `sail_credit_log_tmp` RENAME TO `sail_credit_log`;

COMMIT;

CREATE TABLE IF NOT EXISTS `casino_lobby_log` (
    `uuid` TEXT PRIMARY KEY,
    `start_time` INTEGER,
    `end_time` INTEGER,
    `metadata` BLOB,
    `game` TEXT
)