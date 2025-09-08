from __future__ import annotations

import logging
import os
from configparser import ConfigParser, SectionProxy
from importlib import import_module
from inspect import isabstract, isclass
from pathlib import Path
from pkgutil import iter_modules
from typing import Optional

from dotenv import load_dotenv

from .services import ServiceBase


class SparcClient:
    """
    The main class of the sparc.client library.

    This class is used to connect existing modules located in <projectbase>/services folder


    Parameters:
    -----------
    config_file : str
        The location of the file in INI format that is used to extract configuration variables.
        The config file needs to define a [global] section with the name of the default profile
        (in square brackets as well) which holds environmental variables used by the modules.
        Refer to configparser for further details.
    connect : bool (True)
        Calls connect() method of each of the modules.
        By default during initialization all modules are initialized and ready to be used,
        unless connect is set to False.


    Attributes:
    -----------
    module_names : list
        Stores the list of modules that are automatically loaded from the
        <projectbase>/services directory.
    config : ConfigParser
        Config used for sparc.client


    Methods:
    --------
    add_module(path, config, connect):
        Adds and optionally connects to a module in a given path with
        configuration variables defined in config.
    connect():
        Connects all the modules by calling their connect() functions.
    get_config():
        Returns config used by sparc.client
    from_file(config_file, connect):
        Creates a SparcClient instance from a configuration file.
    from_dict(config_dict, connect):
        Creates a SparcClient instance from a configuration dictionary.
    from_env(dotenv_path, connect):
        Creates a SparcClient instance from environment variables and .env files.

    """

    def __init__(self, config_file: str = "config.ini", connect: bool = True) -> None:

        # Try to find config file, if not available, provide default
        self.config = ConfigParser()
        self.config["global"] = {"default_profile": "default"}
        self.config["default"] = {"pennsieve_profile_name": "pennsieve"}

        try:
            self.config.read(config_file)
        except Exception:
            logging.warning(
                "Configuration file not provided or incorrect, using default settings."
            )

        self._initialize_modules(connect)

    def _initialize_modules(self, connect: bool = True) -> None:
        """Initialize and load service modules.

        Parameters:
        -----------
        connect : bool
            Whether to connect to the modules after loading them.
        """
        logging.debug(self.config.sections())
        current_config = self.config["global"]["default_profile"]

        logging.debug("Using the following config:" + current_config)
        self.module_names = []

        # iterate through the modules in the current package
        package_dir = os.path.join(Path(__file__).resolve().parent, "services")

        for _, module_name, _ in iter_modules([package_dir]):
            # import the module and iterate through its attributes
            self.add_module(
                f"{__package__}.services.{module_name}", self.config[current_config], connect
            )

    @classmethod
    def from_file(cls, config_file: str, connect: bool = True) -> SparcClient:
        """Create a SparcClient instance from a configuration file.

        This is equivalent to calling SparcClient(config_file, connect) but provided
        for consistency with other factory methods.

        Parameters:
        -----------
        config_file : str
            Path to the configuration file in INI format.
        connect : bool
            Whether to connect to services after initialization.

        Returns:
        --------
        SparcClient
            A configured SparcClient instance.
        """
        return cls(config_file=config_file, connect=connect)

    @classmethod
    def from_dict(cls, config_dict: dict, connect: bool = True) -> SparcClient:
        """Create a SparcClient instance from a configuration dictionary.

        Parameters:
        -----------
        config_dict : dict
            Configuration dictionary. Can be either:
            1. Simple flat dictionary with configuration values:
               {'pennsieve_profile_name': 'prod', 'scicrunch_api_key': 'key'}
            2. Full INI-style structure with global and profile sections:
               {'global': {'default_profile': 'prod'}, 'prod': {...}}
        connect : bool
            Whether to connect to services after initialization.

        Returns:
        --------
        SparcClient
            A configured SparcClient instance.
        """
        instance = object.__new__(cls)
        instance.config = ConfigParser()

        # Check if it's a flat config (no 'global' section or 'global' is not a dict)
        if "global" not in config_dict or not isinstance(config_dict.get("global"), dict):
            # Flat dictionary - create the two-level structure internally
            instance.config["global"] = {"default_profile": "default"}
            # Ensure basic defaults exist, then overlay user config
            default_config = {"pennsieve_profile_name": "pennsieve"}
            default_config.update(config_dict)  # Add user config on top of defaults
            instance.config["default"] = default_config
        else:
            # Full INI-style structure - use as-is
            # Set defaults if not provided
            if config_dict["global"].get("default_profile", "default") not in config_dict:
                config_dict[config_dict["global"].get("default_profile", "default")] = {
                    "pennsieve_profile_name": "pennsieve"
                }
            # Load configuration from dictionary
            for section, values in config_dict.items():
                instance.config[section] = values

        instance._initialize_modules(connect)
        return instance

    @classmethod
    def from_env(cls, dotenv_path: Optional[str] = None, connect: bool = True) -> SparcClient:
        """Create a SparcClient instance from environment variables and .env files.

        Parameters:
        -----------
        dotenv_path : str, optional
            Path to .env file. If None, looks for .env in current directory.
            Set to False to skip loading any .env file.
        connect : bool
            Whether to connect to services after initialization.

        Environment Variables:
        ----------------------
        SPARC_PENNSIEVE_PROFILE : str
            Pennsieve profile name (maps to pennsieve_profile_name)
        SPARC_SCICRUNCH_API_KEY : str
            SciCrunch API key (maps to scicrunch_api_key)
        SPARC_O2SPARC_HOST : str
            O2SPARC host URL (maps to o2sparc_host)
        SPARC_O2SPARC_USERNAME : str
            O2SPARC username (maps to o2sparc_username)
        SPARC_O2SPARC_PASSWORD : str
            O2SPARC password (maps to o2sparc_password)

        Returns:
        --------
        SparcClient
            A configured SparcClient instance.
        """
        # Load .env file if specified
        if dotenv_path is not False:
            if dotenv_path is None:
                dotenv_path = ".env"
            if os.path.exists(dotenv_path):
                load_dotenv(dotenv_path)

        # Map environment variables to config keys
        env_mapping = {
            "SPARC_PENNSIEVE_PROFILE": "pennsieve_profile_name",
            "SPARC_SCICRUNCH_API_KEY": "scicrunch_api_key",
            "SPARC_O2SPARC_HOST": "o2sparc_host",
            "SPARC_O2SPARC_USERNAME": "o2sparc_username",
            "SPARC_O2SPARC_PASSWORD": "o2sparc_password",
        }

        # Build config dict from environment variables
        config_dict = {}
        for env_var, config_key in env_mapping.items():
            value = os.environ.get(env_var)
            if value is not None:
                config_dict[config_key] = value

        # Use from_dict to create the instance (handles defaults properly)
        return cls.from_dict(config_dict, connect=connect)

    def add_module(
        self,
        paths: str | list[str],
        config: dict | SectionProxy | None = None,
        connect: bool = True,
    ) -> None:
        """Adds and optionally connects to a module in a given path with configuration
        variables defined in config.

        Parameters:
        -----------
        paths : str or list[str]
            a path to the module
        config : dict or configparser.SectionProxy
            a dictionary (or Section of the config file parsed by ConfigParser)
            with the configuration variables
        connect : bool
            determines if the module should auto-connect
        """
        if not isinstance(paths, list):
            paths = [paths]

        for path in paths:
            module_name = path.split(".")[-1] if "." in path else path
            try:
                module = import_module(path)
                for attribute_name in dir(module):
                    attribute = getattr(module, attribute_name)
                    if (
                        isclass(attribute)
                        and issubclass(attribute, ServiceBase)
                        and not isabstract(attribute)
                    ):
                        # Add the class to this package's variables
                        self.module_names.append(module_name)
                        c = attribute(connect=connect, config=config)
                        setattr(self, module_name, c)
                        if connect:
                            c.connect()

            except ModuleNotFoundError:
                logging.debug(
                    "Skipping module. Failed to import from %s", f"{path=}", exc_info=True
                )
                raise

    def connect(self) -> bool:
        """Connects each of the modules loaded into self.module_names"""
        for module_name in self.module_names:
            module = getattr(self, module_name)
            if hasattr(module, "connect"):
                getattr(self, module_name).connect()
        return True

    def get_config(self) -> ConfigParser:
        """Returns config for sparc.client"""
        return self.config
