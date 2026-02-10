#!/usr/bin/env python3
import argparse
import asyncio
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from app.cli.roster import fix_roster_command

async def main():
    parser = argparse.ArgumentParser(description="Football Manager CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Roster Command
    roster_parser = subparsers.add_parser("roster", help="Manage roster")
    roster_parser.add_argument("action", choices=["fix"], help="Action to perform")
    roster_parser.add_argument("--game-id", type=int, required=True, help="Game ID")

    args = parser.parse_args()

    if args.command == "roster":
        if args.action == "fix":
            await fix_roster_command(args.game_id)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nAborted.")
