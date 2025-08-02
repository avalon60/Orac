#!/usr/bin/env python3
"""
Retrieve a specific credential property from a stored connection entry.
"""

import argparse
from pathlib import Path
from lib.connection_mgr import ConnectMgr
from lib.config_mgr import ConfigManager
from lib.fsutils import project_home
from lib.icons import Icons

APP_HOME = project_home()
CONFIG_FILE_PATH = APP_HOME / 'resources' / 'config' / 'orac.ini'
conf_manager = ConfigManager(config_file_path=CONFIG_FILE_PATH)
project_identifier = conf_manager.config_value(config_section='global', config_key='project_identifier')


def main():
    parser = argparse.ArgumentParser(
        description="Get a specific credential property for a named connection."
    )
    parser.add_argument('-n', '--name', required=True, help="Name of the connection")
    parser.add_argument('-p', '--property', required=True, choices=['username', 'password', 'dsn'],
                        help="Credential property to retrieve")

    args = parser.parse_args()

    conn_mgr = ConnectMgr(project_identifier=project_identifier, resource_type="dsn")

    try:
        username, password, resource_id = conn_mgr.user_security.named_connection_creds(args.name)
    except Exception:
        print(f"{Icons.error} Connection '{args.name}' not found or could not be decrypted.")
        return

    prop_value = {
        'username': username,
        'password': password,
        'dsn': resource_id,
    }.get(args.property)

    if prop_value is None:
        print(f"{Icons.error} Unknown property '{args.property}'.")
    else:
        print(prop_value)


if __name__ == "__main__":
    main()
