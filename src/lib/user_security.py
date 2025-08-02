"""
__author__: Clive Bostock
__date__: 2024-12-01
__description__: User/Security module. This is responsible for managing developer-specific settings; primarily
                 password encryption/decryption and configuration settings.

                 Passwords are located to the $HOME/<sanitised_project_name>/<typ>_credentials.ini file.

                 Typically, <resource-type> would be a URL or a DNS/TNS.
"""

from base64 import b64encode, b64decode
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from lib.framework_errors import UnsupportedPlatform
from lib.fsutils import sanitise_dir_name
from pathlib import Path
from lib.logutil import log_call

import configparser
import os
import subprocess
import platform


def _system_id():
    """
    Retrieves a unique system identifier based on the operating system.

    This function detects the operating system and then executes appropriate
    commands to fetch a unique identifier for the system. The method of fetching
    the identifier varies based on whether the system is macOS (Darwin), Windows,
    or Linux. If the operating system is not one of these, a default identifier
    is returned.

    Returns:
        str: A unique system identifier or a default string if the OS is unsupported.
    """
    # Determine the operating system
    operating_system = platform.system()

    if operating_system == 'Darwin':
        # macOS: Use ioreg and awk to fetch the IOPlatformUUID
        command = "ioreg -d2 -c IOPlatformExpertDevice"
        # Run ioreg command to get platform details
        ioreg_cmd = subprocess.run(["ioreg", "-d2", "-c", "IOPlatformExpertDevice"],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # Run awk command to extract the IOPlatformUUID
        # Better?: awk_cmd = subprocess.run(["awk", '-F\"', "'/IOPlatformUUID/{print $(NF-1)}'"],
        awk_cmd = subprocess.run(["awk", '-F\"', "'/IOPlatformUUID/{print $(NF-1)}'"],
                                 input=ioreg_cmd.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # Decode the output to get the system UID
        system_uid = awk_cmd.stdout.decode()

    elif operating_system == 'Windows':
        # Windows: Use wmic to get the UUID
        # Run PowerShell command to get the system UUID
        system_uid = subprocess.run(["powershell", "(Get-CimInstance -Class Win32_ComputerSystemProduct).UUID"],
                                    capture_output=True, text=True).stdout.strip()

    elif operating_system == 'Linux':
        # Linux: Read the machine-id file
        # Run cat command to read the /etc/machine-id file
        cat_cmd = subprocess.run(["cat", "/etc/machine-id"],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # Decode the output to get the system UID
        system_uid = cat_cmd.stdout.decode()

    else:
        # Unsupported OS: Return a default identifier
        raise UnsupportedPlatform(operating_system)

    return system_uid


class UserSecurity:
    _instances: dict[tuple[str, str], "UserSecurity"] = {}

    @classmethod
    @log_call
    def get(cls, project_identifier: str, resource_type: str = "url") -> "UserSecurity":
        """
        Singleton accessor for UserSecurity instances, keyed by (project_identifier, resource_type).
        This is provided for performance reasons, helping avoid multiple instances of the class within a run,
        and enforcing the sharing of cached credentials.
        """
        key = (project_identifier, resource_type)
        if not hasattr(cls, "_instances"):
            cls._instances = {}

        if key not in cls._instances:
            cls._instances[key] = cls(project_identifier, resource_type)
        return cls._instances[key]

    def __init__(self, project_identifier: str, resource_type: str = "url"):
        """Initialise a UserSec object.
        :param resource_type: 
        :type resource_type: 
        :param project_identifier: An alphanumeric string which identifies the project. This is used to create a hidden .<PROJECT_ID> directory, in the users home directory.
        :param resource_type: Define the type of credentials we are working with. We store one credential type per config file.
        """

        sanitised_dir_name = sanitise_dir_name(directory_name=project_identifier)
        self.config_file_name = f'{resource_type}_credentials.ini'
        self.config_dir_name = '.' + sanitised_dir_name
        self.resource_type = resource_type
        self.project_identifier = project_identifier
        # Here we call get_user_config_file_path to construct our path to the config file.
        # Note that get_user_config_file_path will create the required directory, based on
        # the sanitised project name, under the user's home directory if required.
        self.user_config_file_path = Path(self._get_user_config_file_path())
        self._create_user_credentials_file()
        self._decryption_cache = {}

    @log_call
    def connection_property(self, connection_name: str, property_key: str, default_value: str = None) -> str:
        """Obtains, in plain text, the requested stored connection property.
           Returns a default value if the property or section does not exist.

        Args:
            connection_name (str): Connection name (section name).
            property_key (str): Connection property (option key).
            default_value (str): The value to return if the section or property is not found.
                                 If None, an error will still be raised if the section
                                 doesn't exist, but not if the option doesn't exist.
                                 If a string, it will be returned for a missing option.
                                 For a missing section, it will raise NoSectionError
                                 unless you explicitly check for section existence first.
        """
        config = configparser.ConfigParser()
        config.read(self.user_config_file_path)

        # The most robust way, checking for section existence first
        if config.has_section(connection_name):
            # If the section exists, try to get the option with a fallback
            return config.get(connection_name, property_key, fallback=default_value)
        else:
            # If the section does not exist, return the default_value directly
            return default_value

    @log_call
    def named_connection_creds(self, connection_name: str) -> tuple[str, str, str]:
        """
        Returns the decrypted username, decrypted password, and the DSN for a given connection name.

        :param connection_name: The name of the stored database connection.
        :return: A tuple containing decrypted username, decrypted password, and DSN.
        :raises FileNotFoundError: If the credential configuration file does not exist.
        :raises KeyError: If the connection name does not exist in the credential configuration file.
        """
        # Check if the configuration file exists
        if not self.user_config_file_path.exists():
            raise FileNotFoundError(f"Configuration file '{self.user_config_file_path}' not found.")

        # Load the configuration file
        config = configparser.ConfigParser()
        config.read(self.user_config_file_path)

        # Get all valid connection names (sections in the config)
        valid_connection_names = config.sections()

        # Check if the connection name exists in the configuration
        if connection_name not in valid_connection_names:
            valid_keys_str = ", ".join(
                valid_connection_names) if valid_connection_names else "No connection names have been saved."
            raise KeyError(
                f"Connection '{connection_name}' does not exist in the credentials store. "
                f"Valid connection names are: {valid_keys_str}."
            )

        # Retrieve and decrypt the username and password
        encrypted_username = config.get(connection_name, "username")
        encrypted_password = config.get(connection_name, "password")
        resource_id = config.get(connection_name, "resource_id")

        username = self.decrypted_user_credential(encrypted_credential=encrypted_username)
        password = self.decrypted_user_credential(encrypted_credential=encrypted_password)

        return username, password, resource_id

    @log_call
    def update_named_connection(self, connection_dict: dict):
        """
        Creates or updates a named connection entry with the provided connection details.

        This method encrypts the username and password, stores them along with the resource ID,
        and optionally stores the wallet ZIP path if the connection type is 'DSN'. If the named
        connection section does not exist in the configuration, it is created.

        Args:
            connection_dict (dict): A dictionary containing the following keys:
                - 'resource_type' (str): Type of the resource (e.g., 'dsn', 'url').
                - 'connection_name' (str): The name of the connection entry.
                - 'username' (str): Plaintext username to be encrypted and stored.
                - 'password' (str): Plaintext password to be encrypted and stored.
                - 'resource_id' (str): The DSN or URL being referenced.
                - 'wallet_zip_path' (str, optional): Path to the wallet ZIP file (only for dsn).

        Raises:
            KeyError: If required keys such as 'connection_name', 'username', 'password', or 'resource_id'
                      are missing from the input dictionary.
        """
        resource_type = connection_dict.get("resource_type")
        connection_name = connection_dict.get("connection_name")
        username = connection_dict.get("username")
        password = connection_dict.get("password")
        resource_id = connection_dict.get("resource_id")
        wallet_zip_path = connection_dict.get("wallet_zip_path", "")
        self._create_new_connection_section(connection_name=connection_name)
        encrypted_username = encrypted_user_credential(credential=username)
        encrypted_password = encrypted_user_credential(credential=password)
        self._update_credential_entry(connection_name=connection_name, credential_key="username",
                                      credential_value=encrypted_username)
        self._update_credential_entry(connection_name=connection_name, credential_key="password",
                                      credential_value=encrypted_password)
        self._update_credential_entry(connection_name=connection_name, credential_key="resource_id",
                                      credential_value=resource_id)

        if resource_type.upper() == "DSN":
            self._update_credential_entry(connection_name=connection_name, credential_key="wallet_zip_path",
                                          credential_value=wallet_zip_path)

    @log_call
    def _create_user_credentials_file(self, new_connection_name: str | None = None) -> None:
        """
        Create a configparser file in the user's .<PROJECT_ID> directory.
        If the file already exists, do nothing. If an initial_section is passed, add it to the file.

        :param new_connection_name: Initial connection name to add to the credentials config file.
        """
        if os.path.exists(self.user_config_file_path):
            return

        config = configparser.ConfigParser()
        if new_connection_name:
            config.add_section(new_connection_name)

        with open(str(self.user_config_file_path), 'w', encoding='utf-8') as config_file:
            config.write(config_file)
            config_file.close()

    @log_call
    def _create_new_connection_section(self, connection_name: str) -> None:
        """
        Create a new section in the configparser file if it does not already exist.

        :param connection_name: Section to add to the config file.
        """
        config = configparser.ConfigParser()

        if not os.path.exists(self.user_config_file_path):
            raise FileNotFoundError(f"The config file {self.user_config_file_path} does not exist.")

        config.read(self.user_config_file_path)
        if not config.has_section(connection_name):
            config.add_section(connection_name)
            with open(self.user_config_file_path, 'w') as config_file:
                config.write(config_file)

    @log_call
    def _get_user_config_file_path(self) -> Path:
        """
        Get the full path of the config file in the directory located in the user's home directory.
        if the config_directory path doesn't exist, then create it.
        """
        home_dir = os.path.expanduser("~")
        config_dir_path = os.path.join(home_dir, self.config_dir_name)
        if not os.path.exists(config_dir_path):
            os.makedirs(config_dir_path)
        return Path(os.path.join(config_dir_path, self.config_file_name))

    @log_call
    def _update_credential_entry(self, connection_name: str, credential_key: str, credential_value: str) -> None:
        """
        Write a key/value pair to the configparser file. If the key already exists, update the value and print a message.

        :param connection_name: Config file section name.
        :param credential_key: Key to add/update in the credential config file.
        :param credential_value: Value to associate with the key.
        """
        config = configparser.ConfigParser()

        # Read the existing configuration (if the file exists)
        if os.path.exists(self.user_config_file_path):
            config.read(self.user_config_file_path)

        if not os.path.exists(self.user_config_file_path):
            raise FileNotFoundError(f"The config file {self.user_config_file_path} does not exist.")

        if not config.has_section(connection_name):
            config.add_section(connection_name)

        if config.has_option(connection_name, credential_key):
            print(f"Updating existing user config value for: {credential_key}")
        else:
            print(f"Creating user config value for: {credential_key}")

        config.set(connection_name, credential_key, credential_value)

        with open(self.user_config_file_path, 'w') as config_file:
            config.write(config_file)

    @log_call
    def _user_credential_value(self, connection_name: str, credential_key: str,
                               default: str = None) -> str:
        """
        Retrieve a value from a user configparser file (this does not decrypt).

        :param connection_name: Section of the config file.
        :param credential_key: Key to retrieve the value for.
        :param default: The default value to be returned if the key/value is not found.
        :return: Value associated with the key.
        """

        config = configparser.ConfigParser()

        if not os.path.exists(self.user_config_file_path):
            raise FileNotFoundError(f"The config file {self.user_config_file_path} does not exist.")

        config.read(self.user_config_file_path)

        if not config.has_option(connection_name, credential_key) and default is not None:
            return default

        if not config.has_section(connection_name) or not config.has_option(connection_name, credential_key):
            raise KeyError(f"The key {credential_key} does not exist in the config file.")

        return config.get(connection_name, credential_key)

    @log_call
    def user_credential(self, connection_name: str, credential_key: str = 'password'):
        """Returns the selected (by credential_key) credential component in plain text.

        :param connection_name: The named connection.
        :param credential_key: Used to specify which password or username we wish to retrieve from the credentials section of the ini file.
        :return: Plain text credential.
        :rtype: str
        """

        encrypted_credential = self._user_credential_value(connection_name=connection_name,
                                                           credential_key=credential_key)
        decrypted_credential = self.decrypted_user_credential(encrypted_credential=encrypted_credential)
        return decrypted_credential

    @log_call
    def decrypted_username(self, connection_name: str):
        """Returns the selected (by username key) username in plain text.
        :param connection_name: The name of the stored database connection.
        :return: Plain text username.
        :rtype: str
        """
        username = self.user_credential(connection_name=connection_name,
                                        credential_key='username')

        return username

    @log_call
    def decrypted_password(self, connection_name: str):
        """Returns the selected (by password key) username in plain text.
        :param connection_name: The name of the stored database connection.
        :return: Plain text username.
        :rtype: str
        """

        password = self.user_credential(connection_name=connection_name,
                                        credential_key='password')

        return password

    @log_call
    def decrypted_user_credential(self, encrypted_credential: str, encryption_password: str = None) -> str:
        """The decrypted_user_credential function, accepts an encrypted username or password, previously encrypted by the
        encrypted_user_password function, and returns the decrypted password. We call the standalone,
        mdecrypted_user_credential function, but also cache the decrypted password.

        Args: encrypted_password (str): The base64-encoded encrypted username/password, including the salt, IV, tag,
        and ciphertext.

        Returns:
            str: The plaintext credential.
            :param encrypted_credential:
            :type encrypted_credential:
            :param encryption_password: If not passed, the machine_id is assumed as the encryption key.
            :type encryption_password: str
            :return:
            :rtype:
        """
        if encrypted_credential in self._decryption_cache:
            return self._decryption_cache[encrypted_credential]

        decrypted_credential = decrypted_user_credential(encrypted_credential=encrypted_credential,
                                                         encryption_password=encryption_password)

        self._decryption_cache[encrypted_credential] = decrypted_credential

        return decrypted_credential


@log_call
def _derive_key(encryption_password: str, salt: bytes) -> bytes:
    """
    Derives a 256-bit key from the given password and salt using PBKDF2HMAC.

    Args:
        encryption_password (str): The password to derive the key from.
        salt (bytes): The salt to use in the key derivation function.

    Returns:
        bytes: The derived 256-bit key.
    """
    # Initialize the key derivation function with the provided parameters
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,  # 256 bits
        salt=salt,
        iterations=100000,
        backend=default_backend()
    )
    # Derive the key from the password and salt
    key = kdf.derive(encryption_password.encode())
    return key


# @log_call
def encrypted_user_credential(credential: str, encryption_password: str = None) -> str:
    """The encrypted_user_password function accepts a username, or password, and returns the encrypted form,
    which is locked in (encrypted) to the user's machine.

    Args:
        credential (str): The plaintext credential component (username, password...).

    Returns:
        str: The base64-encoded encrypted username/password, including the salt, IV, tag, and ciphertext.
        :param credential:
        :type credential:
        :param encryption_password: If not passed, the machine_id is assumed as the encryption key.
        :type encryption_password: str
        :return:
        :rtype:
     """
    if encryption_password is None:
        password = _system_id()
    else:
        password = encryption_password

    encrypted_password = _data_encrypt(data_to_encrypt=credential, encryption_password=password)
    return encrypted_password


@log_call
def decrypted_user_credential(encrypted_credential: str, encryption_password: str = None) -> str:
    """The decrypted_user_credential function, accepts an encrypted username or password, previously encrypted by the
    encrypted_user_password function, and returns the decrypted password.

    Args: encrypted_password (str): The base64-encoded encrypted username/password, including the salt, IV, tag,
    and ciphertext.

    Returns:
        str: The plaintext credential.
        :param encrypted_credential:
        :type encrypted_credential:
        :param encryption_password: If not passed, the machine_id is assumed as the encryption key.
        :type encryption_password: str
        :return:
        :rtype:
    """
    if encryption_password is None:
        password = _system_id()
    else:
        password = encryption_password

    system_identifier = _system_id()
    decrypted_credential = _data_decrypt(encrypted_data=encrypted_credential, encryption_password=password)
    return decrypted_credential


@log_call
def _data_encrypt(data_to_encrypt: str, encryption_password: str) -> str:
    """
    Encrypts the provided data using AES-256-GCM.

    Args:
        data_to_encrypt (str): The plaintext data to encrypt.
        encryption_password (str): The password to derive the encryption key from.

    Returns:
        str: The base64-encoded encrypted data, including the salt, IV, tag, and ciphertext.
    """
    # Generate a random salt and IV
    salt = os.urandom(16)
    iv = os.urandom(12)

    # Derive the encryption key using the password and salt
    key = _derive_key(encryption_password, salt)

    # Initialize the AES-GCM encryptor with the derived key and IV
    encryptor = Cipher(
        algorithms.AES(key),
        modes.GCM(iv),
        backend=default_backend()
    ).encryptor()

    # Encrypt the data
    ciphertext = encryptor.update(data_to_encrypt.encode()) + encryptor.finalize()

    # Concatenate the salt, IV, tag, and ciphertext, and base64-encode the result
    encrypted_result = b64encode(salt + iv + encryptor.tag + ciphertext).decode('utf-8')
    return encrypted_result


@log_call
def _data_decrypt(encrypted_data: str, encryption_password: str) -> str:
    """
    Decrypts the provided encrypted data using AES-256-GCM.

    Args:
        encrypted_data (str): The base64-encoded encrypted data to decrypt.
        encryption_password (str): The password to derive the decryption key from.

    Returns:
        str: The decrypted plaintext data.
    """
    # Base64-decode the encrypted data to extract the salt, IV, tag, and ciphertext
    encrypted_data_bytes = b64decode(encrypted_data.encode('utf-8'))
    salt = encrypted_data_bytes[:16]
    iv = encrypted_data_bytes[16:28]
    tag = encrypted_data_bytes[28:44]
    ciphertext = encrypted_data_bytes[44:]

    # Derive the decryption key using the password and salt
    key = _derive_key(encryption_password, salt)

    # Initialize the AES-GCM decryptor with the derived key, IV, and tag
    decryptor = Cipher(
        algorithms.AES(key),
        modes.GCM(iv, tag),
        backend=default_backend()
    ).decryptor()

    # Decrypt the data
    decrypted_data = decryptor.update(ciphertext) + decryptor.finalize()

    return decrypted_data.decode('utf-8')


MACHINE_ID = _system_id()

if __name__ == "__main__":
    # Example data_encrypt()/data_decrypt() usage:
    original_data = "This is a secret message."
    passwd = "strong-password-123"

    # Encrypt the data
    encrypted = _data_encrypt(original_data, passwd)
    print(f"Encrypted: {encrypted}")

    # Decrypt the data
    decrypted = _data_decrypt(encrypted, passwd)
    print(f"Decrypted: {decrypted}")
    user_security = UserSecurity.get(project_identifier='UserSecurity')
    print("NOTE: A .UserSecurity directory has been created, under your home directory, as part of this test!")
    user_security.update_named_connection(connection_name="bozzy", username='clive', password='Wibble',
                                          resource_id='bozzy_tns')
    db_username = user_security.decrypted_username(connection_name='bozzy')
    db_password = user_security.decrypted_password(connection_name='bozzy')

    print(f'Retrieved Username: {db_username}; password: {db_password}')
