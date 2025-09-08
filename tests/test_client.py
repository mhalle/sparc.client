import os
import os.path
from tempfile import NamedTemporaryFile

import pytest

from sparc.client import SparcClient


# Test creating a default instance
def test_class(config_file):
    c = SparcClient(connect=False, config_file=config_file)
    assert len(c.module_names) > 0


# Test config file with incorrect section pointer
def test_config_no_section(test_resources_dir):
    config_file = os.path.join(test_resources_dir, "dummy_config.ini")
    with pytest.raises(KeyError):
        SparcClient(config_file, connect=False)


# Config non-existing config
def test_config_non_existing(config_file=None):
    client = SparcClient(config_file, connect=False)
    c = client.get_config()
    assert c["global"]["default_profile"] == "default"
    assert c["default"]["pennsieve_profile_name"] == "pennsieve"


# Test proper config provided
def test_get_config(test_resources_dir):
    config_file = os.path.join(test_resources_dir, "config.ini")
    client = SparcClient(config_file, connect=False)
    c = client.get_config()
    assert c["global"]["default_profile"] == "ci"
    assert c["ci"]["pennsieve_profile_name"] == "ci"


# Test module addition
def test_failed_add_module(config_file):
    client = SparcClient(connect=False, config_file=config_file)
    with pytest.raises(ModuleNotFoundError):
        client.add_module(paths="sparc.client.xyz", connect=False)


# Test using a config with the module
def test_add_module_connect(config_file):
    sc = SparcClient(config_file=config_file, connect=False)

    expected_module_config = {"module_param": "value"}
    sc.add_module("mock_service", config=expected_module_config, connect=True)

    assert "mock_service" in sc.module_names
    assert hasattr(sc, "mock_service")

    d = sc.mock_service
    from mock_service import MockService

    assert isinstance(d, MockService)
    assert d.init_connect_arg is True
    assert d.init_config_arg == expected_module_config
    assert d.connect_method_called is True


# Test adding a Pennsieve module
def test_add_pennsieve(config_file):
    sc = SparcClient(config_file=config_file, connect=False)
    assert "pennsieve" in sc.module_names
    assert hasattr(sc, "pennsieve")
    from sparc.client.services.pennsieve import PennsieveService

    assert isinstance(sc.pennsieve, PennsieveService)


# Test connection to the module
def test_module_connect(config_file, monkeypatch):
    sc = SparcClient(config_file=config_file, connect=False)
    mock_connect_results = []

    def make_mock_connect(service_name):
        return lambda: mock_connect_results.append(service_name)

    for name in sc.module_names:
        service = getattr(sc, name)
        monkeypatch.setattr(service, "connect", make_mock_connect(name))

    sc.connect()
    assert mock_connect_results == sc.module_names


# Test factory method from_file
def test_from_file(test_resources_dir):
    config_file = os.path.join(test_resources_dir, "config.ini")
    client = SparcClient.from_file(config_file, connect=False)
    c = client.get_config()
    assert c["global"]["default_profile"] == "ci"
    assert c["ci"]["pennsieve_profile_name"] == "ci"
    assert len(client.module_names) > 0


# Test factory method from_dict with full INI-style configuration
def test_from_dict_full():
    config_dict = {
        "global": {"default_profile": "test"},
        "test": {"pennsieve_profile_name": "test_profile"},
    }
    client = SparcClient.from_dict(config_dict, connect=False)
    c = client.get_config()
    assert c["global"]["default_profile"] == "test"
    assert c["test"]["pennsieve_profile_name"] == "test_profile"
    assert len(client.module_names) > 0


# Test factory method from_dict with flat configuration
def test_from_dict_flat():
    config_dict = {"pennsieve_profile_name": "prod", "scicrunch_api_key": "test-key"}
    client = SparcClient.from_dict(config_dict, connect=False)
    c = client.get_config()
    assert c["global"]["default_profile"] == "default"
    assert c["default"]["pennsieve_profile_name"] == "prod"
    assert c["default"]["scicrunch_api_key"] == "test-key"
    assert len(client.module_names) > 0


# Test factory method from_dict with empty configuration
def test_from_dict_empty():
    config_dict = {}
    client = SparcClient.from_dict(config_dict, connect=False)
    c = client.get_config()
    assert c["global"]["default_profile"] == "default"
    # Empty dict should get defaults applied
    assert c["default"]["pennsieve_profile_name"] == "pennsieve"
    assert len(client.module_names) > 0


# Test that all factory methods produce similar results
def test_factory_methods_consistency(test_resources_dir):
    config_file = os.path.join(test_resources_dir, "config.ini")

    # Load from file
    client1 = SparcClient(config_file, connect=False)
    client2 = SparcClient.from_file(config_file, connect=False)

    # Both should have same configuration
    assert (
        client1.get_config()["global"]["default_profile"]
        == client2.get_config()["global"]["default_profile"]
    )
    assert client1.module_names == client2.module_names

    # Load from dict
    config_dict = {"global": {"default_profile": "ci"}, "ci": {"pennsieve_profile_name": "ci"}}
    client3 = SparcClient.from_dict(config_dict, connect=False)
    assert (
        client1.get_config()["global"]["default_profile"]
        == client3.get_config()["global"]["default_profile"]
    )
    assert client1.module_names == client3.module_names


# Test factory method from_env with environment variables
def test_from_env_with_env_vars(monkeypatch):
    # Set environment variables
    monkeypatch.setenv("SPARC_PENNSIEVE_PROFILE", "env_profile")
    monkeypatch.setenv("SPARC_SCICRUNCH_API_KEY", "env_api_key")
    monkeypatch.setenv("SPARC_O2SPARC_HOST", "https://env.osparc.io")

    client = SparcClient.from_env(connect=False)
    c = client.get_config()

    assert c["global"]["default_profile"] == "default"
    assert c["default"]["pennsieve_profile_name"] == "env_profile"
    assert c["default"]["scicrunch_api_key"] == "env_api_key"
    assert c["default"]["o2sparc_host"] == "https://env.osparc.io"
    assert len(client.module_names) > 0


# Test factory method from_env with .env file
def test_from_env_with_dotenv_file(tmp_path, monkeypatch):
    # Clear any existing SPARC env vars
    for key in [
        "SPARC_PENNSIEVE_PROFILE",
        "SPARC_SCICRUNCH_API_KEY",
        "SPARC_O2SPARC_HOST",
        "SPARC_O2SPARC_USERNAME",
        "SPARC_O2SPARC_PASSWORD",
    ]:
        monkeypatch.delenv(key, raising=False)

    # Create a temporary .env file
    env_file = tmp_path / ".env"
    env_file.write_text(
        "SPARC_PENNSIEVE_PROFILE=dotenv_profile\n"
        "SPARC_SCICRUNCH_API_KEY=dotenv_api_key\n"
        "SPARC_O2SPARC_USERNAME=dotenv_user\n"
    )

    # Change to the temporary directory
    original_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        client = SparcClient.from_env(connect=False)
        c = client.get_config()

        assert c["global"]["default_profile"] == "default"
        assert c["default"]["pennsieve_profile_name"] == "dotenv_profile"
        assert c["default"]["scicrunch_api_key"] == "dotenv_api_key"
        assert c["default"]["o2sparc_username"] == "dotenv_user"
        assert len(client.module_names) > 0
    finally:
        os.chdir(original_cwd)


# Test factory method from_env with custom dotenv path
def test_from_env_with_custom_dotenv_path(tmp_path, monkeypatch):
    # Clear any existing SPARC env vars
    for key in [
        "SPARC_PENNSIEVE_PROFILE",
        "SPARC_SCICRUNCH_API_KEY",
        "SPARC_O2SPARC_HOST",
        "SPARC_O2SPARC_USERNAME",
        "SPARC_O2SPARC_PASSWORD",
    ]:
        monkeypatch.delenv(key, raising=False)

    # Create a custom .env file
    custom_env = tmp_path / "custom.env"
    custom_env.write_text(
        "SPARC_PENNSIEVE_PROFILE=custom_profile\n" "SPARC_O2SPARC_PASSWORD=custom_password\n"
    )

    client = SparcClient.from_env(dotenv_path=str(custom_env), connect=False)
    c = client.get_config()

    assert c["global"]["default_profile"] == "default"
    assert c["default"]["pennsieve_profile_name"] == "custom_profile"
    assert c["default"]["o2sparc_password"] == "custom_password"
    assert len(client.module_names) > 0


# Test factory method from_env with no env vars or file
def test_from_env_no_config(monkeypatch):
    # Clear any existing SPARC env vars
    for key in [
        "SPARC_PENNSIEVE_PROFILE",
        "SPARC_SCICRUNCH_API_KEY",
        "SPARC_O2SPARC_HOST",
        "SPARC_O2SPARC_USERNAME",
        "SPARC_O2SPARC_PASSWORD",
    ]:
        monkeypatch.delenv(key, raising=False)

    client = SparcClient.from_env(dotenv_path=False, connect=False)
    c = client.get_config()

    assert c["global"]["default_profile"] == "default"
    assert c["default"]["pennsieve_profile_name"] == "pennsieve"
    assert len(client.module_names) > 0


# Test factory method from_env precedence (env vars override .env file)
def test_from_env_precedence(tmp_path, monkeypatch):
    # Clear any existing SPARC env vars first
    for key in [
        "SPARC_PENNSIEVE_PROFILE",
        "SPARC_SCICRUNCH_API_KEY",
        "SPARC_O2SPARC_HOST",
        "SPARC_O2SPARC_USERNAME",
        "SPARC_O2SPARC_PASSWORD",
    ]:
        monkeypatch.delenv(key, raising=False)

    # Create .env file
    env_file = tmp_path / ".env"
    env_file.write_text("SPARC_PENNSIEVE_PROFILE=dotenv_profile\n")

    # Set environment variable (should take precedence)
    monkeypatch.setenv("SPARC_PENNSIEVE_PROFILE", "env_profile")

    original_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        client = SparcClient.from_env(connect=False)
        c = client.get_config()

        # Environment variable should win over .env file
        assert c["default"]["pennsieve_profile_name"] == "env_profile"
    finally:
        os.chdir(original_cwd)
