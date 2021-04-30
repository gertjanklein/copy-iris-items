import sys
from importlib import reload, import_module
from unittest.mock import patch
from functools import partial
from typing import Any

import logging

import requests
from requests.exceptions import RequestException
from requests.auth import HTTPBasicAuth

import pytest

import config
copier = import_module("copy-iris-items") # type: Any


@pytest.fixture(scope="function")
def reload_modules():
    """
    Reload modules to clear state for new test.
    """

    # Reload after running the test
    yield
    logging.shutdown()
    reload(sys.modules['logging'])
    reload(sys.modules['config'])
    reload(sys.modules['copy-iris-items'])


def is_responsive(url:str, auth:HTTPBasicAuth):
    """
    Check whether the given url responds
    """

    try:
        response = requests.get(url, auth=auth, timeout=0.5)
        if response.status_code == 200:
            return True
        raise ValueError(f"Unexpected status code '{response.status_code}'.")
    except RequestException:
        return False
    return False


if is_responsive("http://localhost:9000/api/atelier/", HTTPBasicAuth('_SYSTEM', 'SYS')):
    # Something is listening here, just use this URL
    @pytest.fixture(scope="session")
    def iris():
        return 'localhost', 9000
else:
    # Use docker-compose to spin up a test container
    @pytest.fixture(scope="session")
    def iris(docker_ip, docker_services):
        """
        Ensure the API is up and responsive.
        """

        # `port_for` takes a container port and returns the corresponding host port
        port = docker_services.port_for("copy-iris-items-testsvr", 52773)
        url = f"http://{docker_ip}:{port}/api/atelier/"
        auth = HTTPBasicAuth('_SYSTEM', 'SYS')
        check = partial(is_responsive, url, auth)

        docker_services.wait_until_responsive(timeout=60.0, pause=1, check=check)
        
        return docker_ip, port


@pytest.fixture
def get_files():
    """
    Runs copy-iris-items with a specic configuration.
    """

    def get_files(toml:str, tmp_path):
        cfgfile = str(tmp_path / 'cfg.toml')
        with open(cfgfile, 'wt') as f:
            f.write(toml)
        args = ['copier', cfgfile, '--no-gui']
        with patch('sys.argv', args):
            cfg = config.get_config()
        copier.run(cfg)
    return get_files

