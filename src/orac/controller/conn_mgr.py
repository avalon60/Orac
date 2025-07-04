__author__ = "Clive Bostock"
__date__ = "2024-12-10"
__description__ = "Module for managing database and website resource connection detail entries in a configuration file."

from controller import __version__
import argparse
from pathlib import Path
from lib.connection_mgr import ConnectMgr
from lib.config_mgr import ConfigManager
from lib.fsutils import project_home

PROG_NAME = Path(__file__).name
APP_HOME = project_home()
CONFIG_FILE_PATH = APP_HOME / 'resources' / 'config' / 'bdds.ini'
conf_manager = ConfigManager(config_file_path=CONFIG_FILE_PATH)

project_identifier = conf_manager.config_value(config_section='global', config_key='project_identifier')


def main():
    print(f"{PROG_NAME}: BDDS connection manager utility version: {__version__}")

    parser = argparse.ArgumentParser(
        description="Resource connection manager.",
        epilog="Used to create/edit/delete or store named database/website connections. "
               "Resource connections are stored, encrypted, in a local store."
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-c', '--create', action='store_true', help="Create a new connection.")
    group.add_argument('-e', '--edit', action='store_true', help="Edit an existing connection.")
    group.add_argument('-d', '--delete', action='store_true', help="Delete an existing connection.")
    group.add_argument('-l', '--list', action='store_true', help="List all connections.")

    # Modifier flag for --list
    parser.add_argument('-C', '--print-creds', action='store_true',
                        help="If used with --list, includes decrypted credentials.")

    parser.add_argument('-n', '--name', type=str, help="Name of the connection.")
    parser.add_argument('-t', '--resource-type', type=str, choices=['dsn', 'url'], default='url',
                        help="Type of credential to use (default: dsn).")

    args = parser.parse_args()

    if args.list:
        conn_mgr = ConnectMgr(project_identifier=project_identifier, resource_type=args.resource_type)
        conn_mgr.list_connections(inc_creds=args.print_creds)

    elif args.print_creds:
        print("❌ Error: --print-creds must be used with --list.")

    elif args.create:
        if not args.name:
            print("❌ Error: --name is required for creating a connection.")
        else:
            conn_mgr = ConnectMgr(project_identifier=project_identifier, resource_type=args.resource_type)
            conn_mgr.create_connection(args.name)

    elif args.edit:
        if not args.name:
            print("❌ Error: --name is required for editing a connection.")
        else:
            conn_mgr = ConnectMgr(project_identifier=project_identifier, resource_type=args.resource_type)
            conn_mgr.edit_connection(args.name)

    elif args.delete:
        if not args.name:
            print("❌ Error: --name is required for deleting a connection.")
        else:
            conn_mgr = ConnectMgr(project_identifier=project_identifier, resource_type=args.resource_type)
            conn_mgr.delete_connection(args.name)


if __name__ == "__main__":
    main()
