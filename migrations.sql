-- This is the migration SQL file.
-- Each query here is ALWAYS ran in the dev setup script - make sure they are compatible!
-- Add conviction log table
CREATE TABLE IF NOT EXISTS conviction_log (
    discord_id INTEGER,
    reason TEXT,
    'timestamp' INTEGER
);

CREATE TABLE IF NOT EXISTS role_images (
    role_id INTEGER PRIMARY KEY,
    image_url TEXT
);