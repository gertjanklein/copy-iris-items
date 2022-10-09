from os.path import join
from typing import Any
from importlib import import_module

import requests
import toml

import pytest
from conftest import list_files

import namespace as ns
import config
copier = import_module("copy-iris-items") # type: Any


"""
Various tests to ensure copy-iris-items saves the same data as
$System.OBJ.ExportUDL(). Mainly intended to catch problems with
trailing newlines: older versions of copy-iris-items saved one
newline less than it should.
"""


# SQL statement that can be run through the /api/atelier API.
# Creates a class with a stored procedure that returns the
# $System.OBJ.ExportUDL() data for a given source item.
CREATE_EXPORT_PROC = """
CREATE PROCEDURE GetExport(Name SYSNAME) FOR Tmp.CII.Tests RETURNS CHAR LANGUAGE OBJECTSCRIPT
{
  Set FileName = ##class(%File).TempFilename()
  Do $System.OBJ.ExportUDL(Name,FileName,"-d",,"UTF8")
  Set Stream = ##class(%FileBinaryStream).%New()
  Do Stream.LinkToFile(FileName)
  Set JSON = [(Stream.Read())]
  Kill Stream
  Do ##class(%File).Delete(FileName)
  Return JSON.%ToJSON()
}
"""


# Base configuration toml data to use. Templates will be replaced,
# and server information appended.
CFG = """
[Project]
items = ['{name}']
[Local]
dir = '{dir}/src'
logdir = '{dir}'
"""


@pytest.mark.usefixtures("reload_modules")
def test_class_newlines(tmp_path, server_toml, get_files):
    """ Tests classes export the same data as $System.OBJ """
    
    name = 'Strix.Std.EAN.cls'
    
    cfg = CFG.format(dir=tmp_path, name=name)
    cfg = f"{cfg}\n{server_toml}"
    
    compare_exports(tmp_path, get_files, cfg, name)
    
@pytest.mark.usefixtures("reload_modules")
def test_class_newlines_vscode(tmp_path, server_toml, get_files):
    """ Tests classes with VS Code compatibility setting """
    
    name = 'Strix.Std.EAN.cls'
    
    cfg = CFG.format(dir=tmp_path, name=name)
    cfg = f"{cfg}\ncompatibility='vscode'\n{server_toml}"
    
    compare_exports(tmp_path, get_files, cfg, name, True)
    
@pytest.mark.usefixtures("reload_modules")
def test_class_newlines_vscode_aug(tmp_path, server_toml, get_files):
    """ Tests compatibility setting from augment config file """
    
    name = 'Strix.Std.EAN.cls'
    
    aug = "[Local]\ncompatibility='vscode'\n"
    aug_name = tmp_path / 'aug.toml'
    with open(aug_name, 'wt', encoding='UTF8') as f:
        f.write(aug)
    
    cfg = '\n'.join([CFG.format(dir=tmp_path, name=name),
        f"augment_from='{aug_name}'",
        server_toml ])
    
    compare_exports(tmp_path, get_files, cfg, name, True)
    
# ---

@pytest.mark.usefixtures("reload_modules")
def test_inc_newlines(tmp_path, server_toml, get_files):
    """ Tests include files export the same data as $System.OBJ """
    
    name = 'Strix.inc'
    
    cfg = CFG.format(dir=tmp_path, name=name)
    cfg = f"{cfg}\n{server_toml}"
    
    compare_exports(tmp_path, get_files, cfg, name)
    
@pytest.mark.usefixtures("reload_modules")
def test_inc_newlines_vscode(tmp_path, server_toml, get_files):
    """ Tests include files with VS Code compatibility setting """
    
    name = 'Strix.inc'
    
    cfg = CFG.format(dir=tmp_path, name=name)
    cfg = f"{cfg}\ncompatibility='vscode'\n{server_toml}"
    
    compare_exports(tmp_path, get_files, cfg, name, True)
    

# ===== Helpers


def compare_exports(tmp_path, get_files, cfg_toml, name, addline=False):
    """ Compares exports to $System.OBJ.ExportUDL. """
    
    # First retrieve the data using copy-iris-items
    get_files(cfg_toml, tmp_path)
    expect = [name]
    got = list_files(join(tmp_path, 'src'))
    
    # Make sure we retrieved the right item
    assert expect == got, f"Should get {expect}, got {got}"
    
    # Get the export data
    with open(join(tmp_path, 'src', name), 'rt', encoding="UTF-8") as f:
        data_from_api = f.read()
    
    # Add a line to the copy-iris-items export, if so requested. This
    # should remove the difference, created by a backward-compatibility
    # setting, with the data retrieved below.
    if addline:
        data_from_api += '\n'
    
    # Convert config toml string to get at server properties. Set
    # defaults by calling the regular config check method.
    cfg_ns = ns.dict2ns(toml.loads(cfg_toml))
    config.check(cfg_ns)
    
    # Get data from $System.OBJ.ExportUDL()
    data_from_export = get_export(cfg_ns.Server, name)
    
    # Save for debugging purposes
    if data_from_api != data_from_export:
        with open(join(tmp_path, 'src', name + '2'), 'wt', encoding="UTF-8") as f:
            f.write(data_from_export)
    
    assert data_from_api == data_from_export, "Both methods should return the same data"
    

def get_export(svr:ns.Namespace, name:str):
    """Returns UDL export data for a source item."""
    
    # Authorization information
    auth = (svr.user, svr.password)
    
    # URL for query actions
    scheme = 'https' if svr.https else 'http'
    qurl = f"{scheme}://{svr.host}:{svr.port}/api/atelier/v1/{svr.namespace}/action/query"
    
    # Remove an existing helper class (regardless of whether it exists)
    query = "DELETE FROM %Dictionary.ClassDefinition WHERE ID = 'Tmp.CII.Tests'"
    requests.post(qurl, json={"query":query}, auth=auth, timeout=60)
    
    # Create the stored procedure
    rsp = requests.post(qurl, json={"query":CREATE_EXPORT_PROC}, auth=auth, timeout=60)
    data = rsp.json()
    if errors := data['status']['errors']:
        raise RuntimeError(errors[0]['error'])
    
    # Get export for the requested name
    query = f"SELECT Tmp_CII.GetExport('{name}') AS result"
    rsp = requests.post(qurl, json={"query":query}, auth=auth, timeout=60)
    data = rsp.json()

    # Check for errors
    if errors := data['status']['errors']:
        raise RuntimeError(errors[0]['error'])
    
    # The stored procedure returns everything on one line
    result = data['result']['content'][0]['result'][0]
    
    # Remove helper class
    query = "DELETE FROM %Dictionary.ClassDefinition WHERE ID = 'Tmp.CII.Tests'"
    requests.post(qurl, json={"query":query}, auth=auth, timeout=60)
    
    return result
