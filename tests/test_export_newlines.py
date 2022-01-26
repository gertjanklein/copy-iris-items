from os.path import join
from typing import Any
from importlib import import_module

import requests

import pytest
from conftest import list_files

import namespace as ns
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
[Local]
dir = '{dir}/src'
logdir = '{dir}'
[Project]
items = ['{name}']
"""


@pytest.mark.usefixtures("reload_modules")
def test_class_newlines(tmp_path, server_toml, get_files, get_config_ns):
    """ Tests classes export the same data as $System.OBJ """
    
    name = 'Strix.Std.EAN.cls'
    compare_exports(tmp_path, server_toml, get_files, get_config_ns, name)
    

@pytest.mark.usefixtures("reload_modules")
def test_inc_newlines(tmp_path, server_toml, get_files, get_config_ns):
    """ Tests include files export the same data as $System.OBJ """
    
    name = 'Strix.inc'
    compare_exports(tmp_path, server_toml, get_files, get_config_ns, name)
    

# =====


def compare_exports(tmp_path, server_toml, get_files, get_config_ns, name):
    """ Compares exports to $System.OBJ.ExportUDL. """
    
    # First retrieve the data using copy-iris-items
    cfg = CFG.format(dir=tmp_path, name=name)
    toml = f"{cfg}\n{server_toml}"
    get_files(toml, tmp_path)
    expect = [name]
    got = list_files(join(tmp_path, 'src'))
    
    # Make sure we retrieved the right item
    assert expect == got, f"Should get {expect}, got {got}"
    
    # Get the export data
    with open(join(tmp_path, 'src', name), 'rt') as f:
        data_from_api = f.read()
    
    # Get configuration namespace object
    cfg = get_config_ns(toml, tmp_path)
    
    # Get data from $System.OBJ.ExportUDL()
    data_from_export = get_export(cfg.Server, name)
    
    # Save for debugging purposes
    if data_from_api != data_from_export:
        with open(join(tmp_path, 'src', name + '2'), 'wt') as f:
            f.write(data_from_export)
    
    assert data_from_api == data_from_export, "Both methods should return the same data"
    

def get_export(svr:ns.Namespace, name:str):
    """Returns UDL export data for the given item"""
    
    # Authorization information
    auth = (svr.user, svr.password)
    
    # URL for query actions
    scheme = 'https' if svr.https else 'http'
    qurl = f"{scheme}://{svr.host}:{svr.port}/api/atelier/v1/{svr.namespace}/action/query"
    
    # Remove an existing helper class (regardless of whether it exists)
    query = "DELETE FROM %Dictionary.ClassDefinition WHERE ID = 'Tmp.CII.Tests'"
    requests.post(qurl, json={"query":query}, auth=auth)
    
    # Create the stored procedure
    rsp = requests.post(qurl, json={"query":CREATE_EXPORT_PROC}, auth=auth)
    data = rsp.json()
    if errors := data['status']['errors']:
        raise RuntimeError(errors[0]['error'])
    
    # Get export for the requested name
    query = f"SELECT Tmp_CII.GetExport('{name}') AS result"
    rsp = requests.post(qurl, json={"query":query}, auth=auth)
    data = rsp.json()

    # Check for errors
    if errors := data['status']['errors']:
        raise RuntimeError(errors[0]['error'])
    result = '\n'.join(data['result']['content'][0]['result'])
    
    # Remove helper class
    query = "DELETE FROM %Dictionary.ClassDefinition WHERE ID = 'Tmp.CII.Tests'"
    requests.post(qurl, json={"query":query}, auth=auth)
    
    return result
