CREATE TABLE users (
    discord_id INTEGER PRIMARY KEY,
    sail_credit INTEGER
);

CREATE TABLE parties (
    party_id INTEGER PRIMARY KEY,
    party_name TEXT,
    party_type TEXT,
    party_status TEXT,
    party_leader_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (party_leader_id) REFERENCES users(discord_id)
);

CREATE TABLE party_members (
    party_id INTEGER,
    member_id INTEGER,
    status TEXT,
    PRIMARY KEY (party_id, member_id),
    FOREIGN KEY (party_id) REFERENCES parties(party_id),
    FOREIGN KEY (member_id) REFERENCES users(discord_id)
);