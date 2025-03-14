import os
import sqlite3


def setup():

    first_time_db_setup = not os.path.isfile("sail_credit.db")
    if first_time_db_setup:
        print("Database file not found. Setting it up...")
        open("sail_credit.db", "a").close()

    with open("schema.sql", "r") as f, open("migrations.sql", "r") as m:
        script = f.read()
        migrations = m.read()

    db = sqlite3.connect("sail_credit.db")

    if first_time_db_setup:
        db.cursor().executescript(script)

    print("Running migrations...")
    # Always run migrations
    db.cursor().executescript(migrations)

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
