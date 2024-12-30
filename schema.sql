CREATE TABLE users (
    discord_id INTEGER PRIMARY KEY,
    sail_credit INTEGER
);

CREATE TABLE sail_credit_log (
    discord_id INTEGER,
    party_size INTEGER,
    party_created_at INTEGER,
    party_finished_at INTEGER,
    prev_sail_credit INTEGER,
    new_sail_credit INTEGER,
    'timestamp' INTEGER
);