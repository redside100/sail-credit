import os
import sqlite3
import json
from state import SerializedState


def setup():

    first_time_db_setup = not os.path.isfile("sail_credit.db")
    if first_time_db_setup:
        print("Database file not found. Setting it up...")
        open("sail_credit.db", "a").close()

    first_time_state_setup = not os.path.isfile("state.json")
    if first_time_state_setup:
        print("State file not found. Setting it up...")
        with open("state.json", "w+") as f:
            f.write(SerializedState().model_dump_json(indent=4, ensure_ascii=True))

    with open("schema.sql", "r") as f, open("migrations.sql", "r") as m:
        script = f.read()
        migrations = m.read()

    db = sqlite3.connect("sail_credit.db")

    if first_time_db_setup:
        db.cursor().executescript(script)

    print("Running migrations...")
    # Always run migrations
    cursor = db.cursor()
    log_columns = {
        row[1] for row in cursor.execute("PRAGMA table_info(sail_credit_log)")
    }
    if "season_id" not in log_columns:
        print("Migration: adding season_id to sail_credit_log...")
        cursor.execute("ALTER TABLE sail_credit_log ADD COLUMN season_id INTEGER")
    cursor.executescript(migrations)
    log_columns = {
        row[1] for row in cursor.execute("PRAGMA table_info(sail_credit_log)")
    }
    if "season_id" not in log_columns:
        raise RuntimeError(
            "Database migration failed: sail_credit_log has no season_id column"
        )

    db.commit()
    db.close()

    if not os.path.isfile("token"):
        print("Token file not found. Setting it up...")
        open("token", "a").close()

        print(
            "Create an app at: https://discord.com/developers/applications and add a bot token to the file!"
        )

    os.system("pre-commit install")

    print("Done setup!")


if __name__ == "__main__":
    setup()
