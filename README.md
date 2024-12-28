# Setting up the dev environment

1. Running Python 3.12+, Create a new Python virtual environment: `python -m venv venv`
2. Activate the virtual environment: `venv/scripts/activate` (or `venv\scripts\activate` on windows)
3. Install requirements: `pip install -r requirements.txt`
4. Run the dev setup script: `python dev_setup.py`
5. If no token, follow instructions to setup a bot account [here](https://discordpy.readthedocs.io/en/stable/discord.html) and copy the bot token to the `token` file.
6. Run with `python main.py`!
