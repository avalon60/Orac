#!/usr/bin/env python3
"""
Orac connection manager utility.
Author: Clive Bostock
Date: 2025-07-26
Description: Module for managing database connection detail entries in a configuration file.
"""

from controller import __version__
import argparse
from pathlib import Path
from lib.connection_mgr import ConnectMgr
from lib.config_mgr import ConfigManager
from lib.fsutils import project_home
from lib.icons import Icons  # ✅ Import Icons helper

PROG_NAME = Path(__file__).name
APP_HOME = project_home()
CONFIG_FILE_PATH = APP_HOME / 'resources' / 'config' / 'orac.ini'
conf_manager = ConfigManager(config_file_path=CONFIG_FILE_PATH)
project_identifier = conf_manager.config_value(config_section='global', config_key='project_identifier')


def main():
    print(f"{PROG_NAME}: Orac connection manager utility version: {__version__}")

    parser = argparse.ArgumentParser(
        description="Resource connection manager.",
        epilog="Used to create/edit/delete or store named database connections. "
               "Connection details are stored, encrypted, in a local store."
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-c', '--create', metavar="NAME", help="Create a new connection with the given NAME.")
    group.add_argument('-e', '--edit', metavar="NAME", help="Edit an existing connection with the given NAME.")
    group.add_argument('-d', '--delete', metavar="NAME", help="Delete the connection with the given NAME.")
    group.add_argument('-l', '--list', action='store_true', help="List all connections.")

    parser.add_argument('-C', '--print-creds', action='store_true',
                        help="If used with --list, includes decrypted credentials.")

    args = parser.parse_args()

    conn_mgr = ConnectMgr(project_identifier=project_identifier, resource_type="dsn")

    if args.list:
        conn_mgr.list_connections(inc_creds=args.print_creds)

    elif args.print_creds:
        print(f"{Icons.error} Error: --print-creds must be used with --list.")

    elif args.create:
        conn_mgr.create_connection(args.create)

    elif args.edit:
        conn_mgr.edit_connection(args.edit)

    elif args.delete:
        conn_mgr.delete_connection(args.delete)


if __name__ == "__main__":
    main()

