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

    # Stats commands
    stats_parser = subparsers.add_parser('stats', help='Statistics and ratings')
    stats_sub = stats_parser.add_subparsers(dest='stats_cmd')
    
    gen_stats = stats_sub.add_parser('generate', help='Generate Excel stats')
    gen_stats.add_argument('--game-id', type=int, required=True)
    gen_stats.add_argument('--output', type=str, default='FM_Player_Stats.xlsx')
    
    recalc = stats_sub.add_parser('recalculate', help='Recalculate all ratings')
    recalc.add_argument('--go', action='store_true', help='Actually apply changes')

    export_csv = stats_sub.add_parser('export-csv', help='Export stats to CSV')
    export_csv.add_argument('--output', type=str, default='FM_Player_Stats.csv')

    # DB commands
    db_parser = subparsers.add_parser('db', help='Database operations')
    db_sub = db_parser.add_subparsers(dest='db_cmd')
    db_sub.add_parser('seed-history', help='Seed historical Games 1-7')
    db_sub.add_parser('reset-stats', help='Reset all user ratings')

    # Admin commands
    admin_parser = subparsers.add_parser('admin', help='Admin tools')
    admin_sub = admin_parser.add_subparsers(dest='admin_cmd')
    
    renumber = admin_sub.add_parser('renumber-game', help='Renumber a game ID')
    renumber.add_argument('--old-id', type=int, required=True)
    renumber.add_argument('--new-id', type=int, required=True)

    # Draft commands
    draft_parser = subparsers.add_parser('draft', help='Draft operations')
    draft_sub = draft_parser.add_subparsers(dest='draft_cmd')
    gen_draft = draft_sub.add_parser('generate', help='Generate draft report')
    gen_draft.add_argument('--output', type=str, default='Draft_Stats.md')

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
    elif args.command == "stats":
        from app.cli.stats import generate_stats_command, recalculate_stats_command, export_stats_csv_command
        if args.stats_cmd == "generate":
            await generate_stats_command(args.game_id, args.output)
        elif args.stats_cmd == "recalculate":
            await recalculate_stats_command(dry_run=not args.go)
        elif args.stats_cmd == "export-csv":
            await export_stats_csv_command(args.output)
    elif args.command == "db":
        from app.cli.db import seed_history_command, reset_db_command
        if args.db_cmd == "seed-history":
            await seed_history_command(args)
        elif args.db_cmd == "reset-stats":
            await reset_db_command(args)
    elif args.command == "admin":
        if args.admin_cmd == "renumber-game":
            from app.cli.admin import renumber_game_command
            await renumber_game_command(args.old_id, args.new_id)
    elif args.command == "draft":
        from app.cli.draft import generate_draft_report_command
        await generate_draft_report_command(args)
    elif args.command == "remote-logs":
        from app.cli.monitor import monitor_remote_logs
        monitor_remote_logs()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nAborted.")
