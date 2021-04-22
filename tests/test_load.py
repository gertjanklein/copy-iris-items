from os import scandir
from os.path import join
from importlib import import_module
from typing import Any

import pytest
import docker

copier = import_module("copy-iris-items") # type: Any


# Check whether docker(-compose) is available
try:
    client = docker.from_env()
    NODOCKER = False
    del client
except docker.errors.DockerException:
    NODOCKER = True


CFG = """
[Server]
host = "{host}"
port = "{port}"
namespace = "{ns}"
user = "SuperUser"
password = "SYS"
[Local]
dir = '{dir}/src'
logdir = '{dir}'
[Project]
items = ['Strix.Std.*.cls']
"""


@pytest.mark.skipif(NODOCKER, reason="Docker not available.")
@pytest.mark.usefixtures("reload_modules")
def test_connect(tmpdir, iris, get_files):
    """Retrieve and build specific packge."""
    host, port = iris
    toml = CFG.format(host=host, port=port, dir=tmpdir, ns="USER")
    get_files(toml, tmpdir)
    expect = 'Strix.Std.EAN.cls,Strix.Std.IBAN.cls,Strix.Std.VATNumber.cls'
    got = list_files(join(tmpdir, 'src'))
    check_files(expect, got)


    # =====

def check_files(expected, got):
    """
    Checks that two lists of filenames are equal.
    """

    if isinstance(expected, str):
        expected = expected.split(',')
    expected.sort()
    got.sort()
    assert expected == got, f"Should get {expected}, got {got}"


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


