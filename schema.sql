CREATE TABLE users (
    discord_id INTEGER PRIMARY KEY,
    sail_credit INTEGER
);

CREATE TABLE parties (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    type TEXT,
    size INTEGER,
    status TEXT,
    description TEXT,
    leader_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (leader_id) REFERENCES users(discord_id)
);

CREATE TABLE party_members (
    party_id INTEGER,
    member_id INTEGER,
    status TEXT,
    PRIMARY KEY (party_id, member_id),
    FOREIGN KEY (party_id) REFERENCES parties(id),
    FOREIGN KEY (member_id) REFERENCES users(discord_id)
);