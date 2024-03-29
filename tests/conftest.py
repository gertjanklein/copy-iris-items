from typing import Any
import sys
from os import scandir
from os.path import dirname, join, exists
from importlib import reload, import_module
from unittest.mock import patch

import requests
from requests.exceptions import RequestException

import pytest
import docker

import config
copier = import_module("copy-iris-items") # type: Any


@pytest.fixture(scope="function")
def reload_modules():
    """Reload modules to clear state for new test."""

    # Reload after running the test
    yield
    # Close any handlers in the logging module
    copier.cleanup_logging()
    reload(sys.modules['logging'])
    reload(sys.modules['config'])
    reload(sys.modules['data_handler'])
    reload(sys.modules['copy-iris-items'])


@pytest.fixture
def get_files():
    """
    Runs copy-iris-items with a specic configuration.
    """

    def get_files(toml:str, tmp_path):
        cfgfile = str(tmp_path / 'cfg.toml')
        with open(cfgfile, 'wt', encoding="UTF-8") as f:
            f.write(toml)
        args = ['copier', cfgfile, '--no-gui']
        with patch('sys.argv', args):
            cfg = config.get_config()
        copier.run(cfg)
    return get_files


@pytest.fixture
def get_config_ns():
    """"
    Converts the configuration to a namespace
    """
    
    def get_config_ns(toml:str, tmp_path):
        cfgfile = str(tmp_path / 'cfg.toml')
        with open(cfgfile, 'wt', encoding="UTF-8") as f:
            f.write(toml)
        args = ['copier', cfgfile, '--no-gui']
        with patch('sys.argv', args):
            cfg = config.get_config()
        return cfg
    return get_config_ns
    

# Generic helpers

def list_files(dir, base=''):
    """
    Lists files in a directory and subdirectories; returns relative paths.
    """

    names = []
    with scandir(dir) as it:
        for f in it:
            relname = '/'.join((base,f.name)) if base else f.name
            if f.is_file():
                names.append(relname)
            else:
                names.extend(list_files(join(dir, f.name), relname))
    return names


# Helpers for the server determination code below

def _open_local():
    """ Returns the contents of server.toml, if present """

    name = join(dirname(__file__), 'server.toml')
    if not exists(name):
        return None
    with open(name, encoding="UTF-8") as f:
        return f.read()

def docker_available():
    """ Checks whether Docker is available """

    try:
        _ = docker.from_env()
        return True
    except docker.errors.DockerException: # type: ignore
        return False

# Determine what the server connection details will be, and
# create a fixture that returns an appropriate TOML file.

if _server_toml := _open_local():
    # A local toml server definition is available; use that
    @pytest.fixture(scope="session")
    def server_toml(): # type: ignore # pylint:disable=missing-function-docstring
        return _server_toml

elif docker_available():
    # Docker available; spin up a temporary IRIS
    @pytest.fixture(scope="session")
    def server_toml(iris_service): # type: ignore # pylint:disable=missing-function-docstring
        ip, port = iris_service
        toml = f"\n[Server]\nhost='{ip}'\nport='{port}'\n" \
            "namespace='user'\nuser='_SYSTEM'\npassword='SYS'\n"
        return toml

else:
    # No locat server definition and no Docker; skip tests
    @pytest.fixture(scope="session")
    def server_toml(): # type: ignore # pylint:disable=missing-function-docstring
        pytest.skip("Docker not available")


# Helper fixture: returns the IP/port of the running docker instance,
# waiting for it to become available.
@pytest.fixture(scope="session")
def iris_service(docker_ip, docker_services):
    """Ensure that HTTP service is up and responsive."""

    port = docker_services.port_for("copy-iris-items-testsvr", 52773)
    url = f"http://{docker_ip}:{port}/api/atelier/"
    docker_services.wait_until_responsive(
        timeout=120.0, pause=0.5, check=lambda: is_responsive(url)
    )

    return docker_ip, port

# Helper method: attempts to connect to the given URL, returning True
# if successful, False otherwise.
def is_responsive(url):
    """ Helper method, waits until an http URL is available """

    try:
        response = requests.get(url, auth=('_SYSTEM','SYS'), timeout=1)
        if response.status_code == 200:
            return True
    except RequestException:
        pass
    
    return False


@pytest.fixture(scope="session")
def docker_compose_file(pytestconfig):
    """ Override to specify where docker-compose.yml is """
    
    return join(pytestconfig.rootdir, "docker", "docker-compose.yml")

