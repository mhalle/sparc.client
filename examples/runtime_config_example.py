#!/usr/bin/env python
"""
Example demonstrating runtime configuration of SparcClient using factory methods.
"""

from configparser import ConfigParser
from sparc.client import SparcClient


def main():
    # Method 1: Traditional file-based configuration (backward compatible)
    print("1. Traditional file-based configuration:")
    client1 = SparcClient(config_file="config.ini", connect=False)
    print(f"   Profile: {client1.config['global']['default_profile']}")
    print(f"   Modules loaded: {client1.module_names}\n")

    # Method 2: Explicit file-based using factory method
    print("2. File-based using factory method:")
    client2 = SparcClient.from_file("config.ini", connect=False)
    print(f"   Profile: {client2.config['global']['default_profile']}")
    print(f"   Modules loaded: {client2.module_names}\n")

    # Method 3: Simple flat runtime configuration
    print("3. Simple flat runtime configuration:")
    config_dict = {
        "pennsieve_profile_name": "prod_pennsieve",
        "scicrunch_api_key": "your-api-key",
        "o2sparc_host": "https://api.osparc.io",
    }
    client3 = SparcClient.from_dict(config_dict, connect=False)
    print(f"   Profile: {client3.config['global']['default_profile']}")
    print(f"   Pennsieve profile: {client3.config['default']['pennsieve_profile_name']}")
    print(f"   SciCrunch key: {client3.config['default']['scicrunch_api_key']}")
    print(f"   O2SPARC host: {client3.config['default']['o2sparc_host']}")
    print(f"   Modules loaded: {client3.module_names}\n")

    # Method 4: Full INI-style runtime configuration
    print("4. Full INI-style runtime configuration:")
    config_dict = {
        "global": {"default_profile": "development"},
        "development": {
            "pennsieve_profile_name": "dev_pennsieve",
            "scicrunch_api_key": "dev-api-key",
        },
    }
    client4 = SparcClient.from_dict(config_dict, connect=False)
    print(f"   Profile: {client4.config['global']['default_profile']}")
    print(f"   Pennsieve profile: {client4.config['development']['pennsieve_profile_name']}")
    print(f"   SciCrunch key: {client4.config['development']['scicrunch_api_key']}")
    print(f"   Modules loaded: {client4.module_names}\n")

    # Method 5: Minimal runtime configuration (uses defaults)
    print("5. Minimal runtime configuration:")
    client5 = SparcClient.from_dict({}, connect=False)
    print(f"   Profile: {client5.config['global']['default_profile']}")
    print(f"   Modules loaded: {client5.module_names}")


if __name__ == "__main__":
    main()
