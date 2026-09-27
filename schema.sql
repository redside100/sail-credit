CREATE TABLE
    users (
        discord_id INTEGER PRIMARY KEY,
        sail_credit INTEGER
    );

CREATE TABLE
    sail_credit_log (
        discord_id INTEGER,
        season_id INTEGER,
        party_size INTEGER,
        party_created_at INTEGER,
        party_finished_at INTEGER,
        prev_sail_credit INTEGER,
        new_sail_credit INTEGER,
        source TEXT CHECK (source IN ('PARTY', 'ADMIN')),
        'timestamp' INTEGER
    );

CREATE TABLE
    seasons (
        season_id INTEGER PRIMARY KEY,
        start_timestamp INTEGER NOT NULL,
        end_timestamp INTEGER,
        status TEXT NOT NULL CHECK (status IN ('ACTIVE', 'COMPLETED'))
    );

CREATE TABLE
    user_season_stats (
        discord_id INTEGER NOT NULL,
        season_id INTEGER NOT NULL,
        highest_sail_credit INTEGER NOT NULL,
        highest_rank INTEGER,
        PRIMARY KEY (discord_id, season_id),
        FOREIGN KEY (discord_id) REFERENCES users (discord_id),
        FOREIGN KEY (season_id) REFERENCES seasons (season_id)
    );

CREATE TABLE
    `casino_lobby_log` (
        `uuid` TEXT PRIMARY KEY,
        `start_time` INTEGER,
        `end_time` INTEGER,
        `metadata` BLOB,
        `game` TEXT
    )
