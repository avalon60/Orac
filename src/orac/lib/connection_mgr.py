__author__ = "Clive Bostock"
__date__ = "2025-01-27"
__description__ = ("Module for managing database and application connection entries in a configuration file. Two "
                   "variations of file are maintained. One for DSNs and another for URLs. These are auto-created (if "
                   "required) and maintained based on the resource_type initialisation parameter.")

import configparser
import getpass
import zipfile
import json
from datetime import datetime
from pathlib import Path
from lib.user_security import UserSecurity
import lib.user_security as user_security

MACHINE_ID = user_security.MACHINE_ID
CRITICAL = '❌'
INFO = 'ℹ️'
ERROR = '❗'
WARNING = '⚠️'

class ConnectMgr:
    def __init__(self, project_identifier: str, resource_type: str):
        """
        Initialize the ConnectMgr object. :PROJECT_ID: Unique string identifying the project. Used to
        formulate the .<PROJECT_ID> folder name. :param resource_type: Type of credential (e.g. 'dsn')
        """
        config_pathname = Path.home() / f".{project_identifier}/{resource_type}_credentials.ini"
        self.config_pathname = config_pathname
        self.resource_type = resource_type
        self.config = configparser.ConfigParser()
        self.user_security = UserSecurity.get(project_identifier=project_identifier, resource_type=resource_type)
        self._ensure_config_file()
        self.config.read(self.config_pathname)

    def _ensure_config_file(self):
        """Ensure the configuration file exists."""
        if not self.config_pathname.parent.exists():
            self.config_pathname.parent.mkdir(parents=True)
        if not self.config_pathname.exists():
            self.config_pathname.touch()
            print(f"Created configuration file at {self.config_pathname}")

    def list_connections(self, inc_creds=False):
        """List all connections."""
        sections = self.config.sections()
        if self.resource_type == 'url':
            type_desc = 'website'
        else:
            type_desc = 'database'

        if sections:
            print(f"{type_desc.title()} connections:")
            name = 'Name'

            if self.resource_type == 'url':
                type_desc = 'URL'
            else:
                type_desc = 'DSN/TNS'

            print(f"Pos {name:<20}  {type_desc:<50}  Wallet Pathname")
            under_name = "=" * 20
            under_resource_ = "=" * 50
            under_wallet = "=" * 60
            print(f"=== {under_name:<20}  {under_resource_:<20}  {under_wallet:<20}")
            for id, section in enumerate(sections, start=1):

                name = self.config[section].get('resource_id', f'No {self.resource_type} provided')
                if inc_creds:
                    username = self.user_security.user_credential(connection_name=section, credential_key="username")
                    password = self.user_security.user_credential(connection_name=section, credential_key="password")
                    print(f"  {id} {section:<20}  {name} [{username} / {password}]")
                elif self.resource_type == 'dsn':
                    wallet_zip_path = self.config[section].get('wallet_zip_path', 'No wallet')
                    print(f"  {id} {section:<20}  {name:<50}  {wallet_zip_path}")
                else:
                    print(f"  {id} {section:<20}  {name}")
        else:
            print(f"No {type_desc} connections found.")

    def create_connection(self, name: str):
        """Create a new connection."""
        if self.config.has_section(name):
            print(f"Connection '{name}' already exists.")
            return

        if self.resource_type == 'url':
            type_desc = 'URL'
            prompt_desc = 'website'
        else:
            type_desc = 'DSN'
            prompt_desc = 'database'

        print(f"Creating {prompt_desc} saved connection '{name}'...")
        username = input("Enter username: ")
        while True:
            password = getpass.getpass("Enter password: ")
            confirm_password = getpass.getpass("Re-enter password: ")
            if password == confirm_password:
                break
            print("Passwords do not match. Please try again.")
        resource_id = input(f"Enter {type_desc}: ")

        wallet_zip_path = ""
        if self.resource_type == 'dsn':
            while True:
                raw_wallet_path = input("Enter path to wallet ZIP file (optional, leave blank to skip): ").strip()
                if not raw_wallet_path:
                    wallet_zip_path = ""
                    break
                validated = self._validate_wallet_path(raw_wallet_path)
                if validated:
                    wallet_zip_path = validated
                    break
                else:
                    print("Please enter a valid ZIP file path or press Enter to skip.")

        connection_parameters: dict = {"connection_name": name,
                                       "username": username,
                                       "password": password,
                                       "resource_type": self.resource_type,
                                       "resource_id": resource_id,
                                       "wallet_zip_path": wallet_zip_path}

        confirm = input(f"Save connection '{name}'? (y/n): ").lower()
        if confirm == 'y':
            self.config.add_section(name)
            self.user_security.update_named_connection(connection_dict=connection_parameters)
            print(f"Connection '{name}' created.")
        else:
            print("Creation cancelled.")

    def _save_config(self):
        """Save the configuration to the file."""
        with self.config_pathname.open('w') as config_file:
            self.config.write(config_file)

    def delete_connection(self, connection_name: str):
        """Delete a connection."""

        if self.resource_type == 'url':
            prompt_desc = 'website'
        else:
            prompt_desc = 'database'

        if self.config.has_section(connection_name):
            confirm = input(
                f"Are you sure you want to delete the {prompt_desc} connection '{connection_name}'? (y/n): ").lower()
            if confirm == 'y':
                self.config.remove_section(connection_name)
                self._save_config()
                print(f"Connection '{connection_name}' deleted.")
            else:
                print("Deletion cancelled.")
        else:
            print(f"{WARNING} Connection '{connection_name}' does not exist.")

    def edit_connection(self, name: str):
        """Edit an existing connection."""
        if not self.config.has_section(name):
            print(f"Connection '{name}' does not exist.")
            return

        db_username, db_password, resource_id = self.user_security.named_connection_creds(connection_name=name)

        print(f"Editing connection '{name}'...")
        username = input(f"Enter username [{db_username}]: ") or db_username
        password = getpass.getpass("Enter new password (leave blank to keep current): ") or db_password

        if self.resource_type == 'url':
            type_desc = 'website URL'
        else:
            type_desc = 'database DSN'

        resource_id = input(f"Enter {type_desc} [{self.config[name]['resource_id']}]: ") or resource_id

        wallet_zip_path = ""
        if self.resource_type == 'dsn':
            existing_wallet = self.config[name].get('wallet_zip_path', '')
            while True:
                raw_wallet_path = input(
                    f"Enter wallet ZIP path [{existing_wallet}] (leave blank to keep current): ").strip()
                if not raw_wallet_path:
                    wallet_zip_path = existing_wallet
                    break
                validated = self._validate_wallet_path(raw_wallet_path)
                if validated:
                    wallet_zip_path = validated
                    break
                else:
                    print("Please enter a valid ZIP file path or press Enter to retain existing value.")

        confirm = input(f"Save changes to connection '{name}'? (y/n): ").lower()
        connection_name = name
        username = username
        password = password
        resource_id = resource_id
        connection_parameters: dict = {"connection_name": name,
                                       "username": username,
                                       "password": password,
                                       "resource_type": self.resource_type,
                                       "resource_id": resource_id,
                                       "wallet_zip_path": wallet_zip_path}
        if confirm == 'y':
            self.user_security.update_named_connection(connection_dict=connection_parameters)
            if self.resource_type == 'dsn':
                self.config.set(name, 'wallet_zip_path', wallet_zip_path)
            self._save_config()
            print(f"Connection '{name}' updated.")
        else:
            print("Edit cancelled.")

    def export(self, resource_type: str, project_identifier: str,
               connection_name: str, zip_filepath: Path,
               zip_password: str):
        """
        Export the connection credentials to a password-protected ZIP file.

        :param resource_type: The type of resource (e.g., 'dsn', 'url').
        :param project_identifier: The unique identifier for the project.
        :param connection_name: The connection name to export, or '*' for all connections.
        :param zip_password: The password to protect the ZIP file.
        :param zip_filepath: Pathname to export the zip file to.
        """
        # Fetch the connection credentials
        credentials_list = self.get_connection_credentials(connection_name, encryption_key=MACHINE_ID)
        wallet_zip_path = self.user_security.connection_property(connection_name=connection_name,
                                                                 property_key='wallet_zip_path', default_value='')

        # Construct the JSON structure with a header
        export_data = {
            "header": {
                "resource_type": resource_type,
                "project_id": project_identifier,
                "source_filename": zip_filepath.name,  # Get the basename of the file
                "wallet_zip_path": wallet_zip_path,
                "export_dttm": datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # Export timestamp

            },
            "connections": credentials_list
        }

        # Convert the structured data to JSON
        credentials_json = json.dumps(export_data, indent=4)

        # Write to ZIP file.
        with zipfile.ZipFile(zip_filepath, mode='w', compression=zipfile.ZIP_DEFLATED) as zipf:
            zipf.writestr(f"{zip_filepath.stem}.json", credentials_json)  # Write JSON content to the ZIP file

        print(f"Credentials exported and saved to {zip_filepath}.")

    def get_connection_credentials(self, connection_name: str, encryption_key=MACHINE_ID) -> list:
        """
        Fetch and decrypt credentials for the given connection name or for all connections.

        :param connection_name: The name of the connection, or '*' to get all connections.
        :param encryption_key: The password to encrypt credentials.
        :return: A list of dictionaries with the connection credentials.
        """
        credentials_list = []

        # If '*' is specified, fetch credentials for all connections
        if connection_name == '*':
            sections = self.config.sections()  # Get all sections from the config file
            for section in sections:
                username, password, resource_id = self.user_security.named_connection_creds(connection_name=section)

                username = user_security.encrypted_user_credential(credential=username,
                                                                   encryption_password=encryption_key)
                password = user_security.encrypted_user_credential(credential=password,
                                                                   encryption_password=encryption_key)

                credentials = {
                    "connection_name": section,
                    "username": username,
                    "password": password,
                    "resource_id": resource_id
                }
                credentials_list.append(credentials)
        else:
            # Fetch credentials for the specific connection
            username, password, resource_id = self.user_security.named_connection_creds(connection_name=connection_name)
            username = user_security.encrypted_user_credential(credential=username, encryption_password=encryption_key)
            password = user_security.encrypted_user_credential(credential=password, encryption_password=encryption_key)
            credentials = {
                "connection_name": connection_name,
                "username": username,
                "password": password,
                "resource_id": resource_id
            }
            credentials_list.append(credentials)

        return credentials_list

    @staticmethod
    def _validate_wallet_path(path_str: str) -> str:
        """Validate that the given wallet path exists and is a ZIP file. Returns the cleaned path or empty string."""
        if not path_str:
            return ""

        wallet_path = Path(path_str).expanduser().resolve()
        if not wallet_path.exists():
            print(f"⚠ Wallet path '{wallet_path}' does not exist.")
            return ""
        if wallet_path.suffix.lower() != ".zip":
            print(f"⚠ Wallet path '{wallet_path}' is not a ZIP file.")
            return ""
        return str(wallet_path)
