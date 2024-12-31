# Sail Credit Bureau

The Sail Credit Bureau (SCB) is here to help organize members of the community into parties for state-sanctioned activities and games. Those who do not respect the time of their fellow members will have their standings in the community affected (deduction to total Sail Social Credit (SSC) balance).

# Functionality

### Party System

The party system is intended to allow for members of a server to co-ordinate parties fo various games and activities.

- Server members with the Discord role for the game/activity will receive a ping.
- Parties can have scheduled start times (up to 12h).
- Members are able to search for active parties by Discord role.

### Sail Social Credit (SSC) System

The Sail Social Credit (SSC) System was created to ensure that people's time would be respected when creating a party.

- Members who successfully join a party and gets into game with no issues will receive some SSC.
- A majority of party members can choose to report another party member if after the party has started and they are not present. The reported member will receive a deduction of SSC.

# Setting up the Development Environment

1. Running Python 3.12+, Create a new Python virtual environment: `python -m venv venv`
2. Activate the virtual environment: `venv/scripts/activate` (or `venv\scripts\activate` on windows)
3. Install requirements: `pip install -r requirements.txt`
4. Run the dev setup script: `python dev_setup.py`
5. If no token, follow instructions to setup a bot account [here](https://discordpy.readthedocs.io/en/stable/discord.html) and copy the bot token to the `token` file.
6. Run with `python main.py`!
