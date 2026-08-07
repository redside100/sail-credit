# Sail Credit Bureau (SCB) Project Guide

## 1. Project Overview

The Sail Credit Bureau (SCB) is a community-driven management system designed for organizing gaming/activity parties and maintaining a "Sail Social Credit" (SSC) system to encourage respectful behavior among community members.

- **Purpose:** Automate party coordination via Discord and penalize/reward users based on their attendance and reliability.
- **Technologies:** Python 3.12+, `discord.py`, `aiosqlite`, `pydantic`, `APScheduler`.
- **Architecture:** Discord Bot application using an asynchronous event-driven model.

## 2. Getting Started

### Prerequisites

- Python 3.12+
- A Discord Bot Token (from [Discord Developer Portal](https://discordpy.readthedocs.io/en/stable/discord.html))

### Installation

1. Create virtual environment: `python -m venv venv`
2. Activate it: `source venv/bin/activate` (or `venv\scripts\activate` on Windows)
3. Install dependencies: `pip install -r requirements.txt`
4. Initialize the database: `python dev_setup.py`
5. Place your Discord bot token in a file named `token` in the root directory.

### Running

- Start the bot: `python main.py`

## 3. Project Structure

- `casino/`: Logic related to potential gamification or betting components.
- `main.py`: Entry point for the Discord bot.
- `models.py`: Pydantic models for data structures.
- `party.py`: Core logic for the Party System.
- `db.py`: Database interaction layer using `aiosqlite`.
- `views.py`: Discord UI views/components.
- `schema.sql`: SQL database schema definitions.

## 4. Development Workflow

- **Coding Standards:** PEP 8 compliance. Use `black` for formatting.
- **Testing:** Add tests to the `tests/` directory.
- **Git:** Pre-commit hooks are configured (`.pre-commit-config.yaml`). Ensure they pass before pushing.

## 5. Key Concepts

- **Party System:** Allows users to create/join game sessions.
- **SSC (Sail Social Credit):** A balance system tracking user reliability.

## 6. Common Tasks

- **Adding a new command:** Implement in the relevant module (e.g., `party.py`) using `discord.py` decorators.
- **Database updates:** Modify `schema.sql` and run `migrations.sql` if necessary.

## 7. Troubleshooting

- **Bot not connecting:** Ensure `token` file is present and valid.
- **Database errors:** Ensure `dev_setup.py` has been run successfully.

## 8. References

- [discord.py Documentation](https://discordpy.readthedocs.io/en/stable/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
