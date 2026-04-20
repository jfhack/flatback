import argparse
import sys
from .core import Backup, Restore


def parse_args():
    parser = argparse.ArgumentParser(
        prog="flatback",
        description="Backup and restore Flatpak applications for offline transfer",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    backup = sub.add_parser("backup", help="Backup a Flatpak application")
    backup.add_argument("app_id", help="Flatpak application ID (e.g. org.yuzu_emu.yuzu)")
    backup.add_argument("-o", "--output", help="Output path (default: <app_id>.tar.gz)")
    backup.add_argument("--no-tar", action="store_true", help="Save as directory instead of tar.gz")
    backup.add_argument("--data", action="store_true", help="Include user data (~/.var/app/<app_id>) in backup")
    backup.add_argument("--system", action="store_true", help="Use system installation instead of user")

    restore = sub.add_parser("restore", help="Restore a Flatpak application from backup")
    restore.add_argument("source", help="Path to backup tar.gz or directory")
    restore.add_argument("--data", action="store_true", default=None, help="Restore user data without prompting")
    restore.add_argument("--no-data", action="store_true", help="Skip user data restore without prompting")
    restore.add_argument("--system", action="store_true", help="Install to system instead of user")

    return parser.parse_args()


def main():
    args = parse_args()
    installation = "system" if args.system else "user"

    if args.command == "backup":
        bk = Backup(args.app_id, installation)
        bk.create(output_path=args.output, as_tar=not args.no_tar, include_data=args.data)

    elif args.command == "restore":
        restore_data = None
        if args.data:
            restore_data = True
        elif args.no_data:
            restore_data = False
        rs = Restore(installation, restore_data=restore_data)
        rs.load(args.source)


if __name__ == "__main__":
    main()
