from os.path import join
from importlib import import_module
from typing import Any

import pytest

from conftest import list_files

copier = import_module("copy-iris-items") # type: Any


CFG = """
[Local]
dir = '{dir}/src'
logdir = '{dir}'
[Project]
items = ['Strix.Std.*.cls']
"""


@pytest.mark.usefixtures("reload_modules")
def test_load(tmp_path, server_toml, get_files):
    """Test loading a package """
    
    cfg = CFG.format(dir=tmp_path)
    toml = f"{cfg}\n{server_toml}"
    get_files(toml, tmp_path)
    expect = 'Strix.Std.EAN.cls,Strix.Std.IBAN.cls,Strix.Std.VATNumber.cls'
    got = list_files(join(tmp_path, 'src'))
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


