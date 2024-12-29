import os
import sqlite3


def setup():
    if not os.path.isfile("sail_credit.db"):
        print("Database file not found. Setting it up...")
        open("sail_credit.db", "a").close()

        with open("schema.sql", "r") as f:
            script = f.read()

        db = sqlite3.connect("sail_credit.db")
        db.cursor().executescript(script)
        db.commit()
        db.close()

    if not os.path.isfile("token"):
        print("Token file not found. Setting it up...")
        open("token", "a").close()

        print(
            "Create an app at: https://discord.com/developers/applications and add a bot token to the file!"
        )

    print("Done setup!")


if __name__ == "__main__":
    setup()
