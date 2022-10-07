from os.path import join
from importlib import import_module
from typing import Any

import pytest

from conftest import list_files

copier = import_module("copy-iris-items") # type: Any


CFG = """
[Local]
dir = '{dir}/src'
cspdir = '{dir}/csp'
logdir = '{dir}'
[Project]
items = [{spec}]
"""


@pytest.mark.usefixtures("reload_modules")
def test_load(tmp_path, server_toml, get_files):
    """
    Test loading all classes in a package
    """
    
    spec = "'Strix.Std.*.cls'"
    cfg = CFG.format(dir=tmp_path, spec=spec)
    toml = f"{cfg}\n{server_toml}"
    get_files(toml, tmp_path)
    expect = 'Strix.Std.EAN.cls,Strix.Std.IBAN.cls,Strix.Std.VATNumber.cls'
    got = list_files(join(tmp_path, 'src'))
    check_files(expect, got)
    

@pytest.mark.usefixtures("reload_modules")
def test_exclude_single(tmp_path, server_toml, get_files):
    """
    Test excluding a class
    """
    
    spec = "'Strix.Std.*.cls', '-Strix.Std.IBAN.cls'"
    cfg = CFG.format(dir=tmp_path, spec=spec)
    toml = f"{cfg}\n{server_toml}"
    get_files(toml, tmp_path)
    expect = 'Strix.Std.EAN.cls,Strix.Std.VATNumber.cls'
    got = list_files(join(tmp_path, 'src'))
    check_files(expect, got)
    

@pytest.mark.usefixtures("reload_modules")
def test_load_csp(tmp_path, server_toml, get_files):
    """
    Test loading a CSP item
    """
    
    spec = "'Strix.Std.EAN.cls', '/csp/user/menu.csp'"
    cfg = CFG.format(dir=tmp_path, spec=spec)
    toml = f"{cfg}\n{server_toml}"
    get_files(toml, tmp_path)
    expect = 'Strix.Std.EAN.cls,csp/user/menu.csp'
    got = list_files(join(tmp_path, 'src')) + list_files(join(tmp_path, 'csp'))
    check_files(expect, got)


@pytest.mark.usefixtures("reload_modules")
def test_load_csp_wildcard(tmp_path, server_toml, get_files):
    """
    Test loading CSP items with a wildcard spec
    """
    
    spec = "'/csp/user/*.csp'"
    cfg = CFG.format(dir=tmp_path, spec=spec)
    toml = f"{cfg}\n{server_toml}"
    get_files(toml, tmp_path)
    expect = 'csp/user/showsource.csp,csp/user/menu.csp'
    got = list_files(join(tmp_path, 'csp'))
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


