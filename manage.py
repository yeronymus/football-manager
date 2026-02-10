#!/usr/bin/env python3
import argparse
import asyncio
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from app.cli.roster import fix_roster_command
from app.cli.admin import add_player_command, kick_player_command

async def main():
    parser = argparse.ArgumentParser(description="Football Manager CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Roster Command
    roster_parser = subparsers.add_parser("roster", help="Manage roster")
    roster_parser.add_argument("action", choices=["fix"], help="Action to perform")
    roster_parser.add_argument("--game-id", type=int, required=True, help="Game ID")

    # App Player Command
    add_parser = subparsers.add_parser("add_player", help="Add player to game")
    add_parser.add_argument("--game-id", type=int, required=True, help="Game ID")
    add_parser.add_argument("--user-id", type=int, required=True, help="User ID")
    add_parser.add_argument("--force", action="store_true", help="Ignore limits")

    # Kick Player Command
    kick_parser = subparsers.add_parser("kick_player", help="Kick player from game")
    kick_parser.add_argument("--game-id", type=int, required=True, help="Game ID")
    kick_parser.add_argument("--user-id", type=int, required=True, help="User ID")

    # Restore Command
    subparsers.add_parser("restore", help="Restore January 2026 Data")

    # Monitor Command
    subparsers.add_parser("remote-logs", help="Monitor Remote Logs")

    args = parser.parse_args()

    if args.command == "roster":
        if args.action == "fix":
            await fix_roster_command(args.game_id)
    elif args.command == "add_player":
        await add_player_command(args.game_id, args.user_id, args.force)
    elif args.command == "kick_player":
        await kick_player_command(args.game_id, args.user_id)
    elif args.command == "restore":
        from app.cli.restore import restore_january_2026
        await restore_january_2026()
    elif args.command == "remote-logs":
        from app.cli.monitor import monitor_remote_logs
        # Interactive, monitoring need to be sync or handled carefully if nested in async main
        # But run_interactive uses os.read/write blocking.
        # Since it's a CLI tool, we can just call it.
        monitor_remote_logs()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nAborted.")
