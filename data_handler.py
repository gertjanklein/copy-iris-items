import urllib.request as urq
from urllib.error import URLError
import json
import logging

import namespace as ns


# SQL to create a stored procedure that can export things by calling
# $System.OBJ.Export. Note that versions before IRIS don't support
# nested curly braces in the code, hence the use of For instead of While.
CREATE_EXPORT_PROC = """
CREATE PROCEDURE GetExport(name SYSNAME) FOR Tmp.CII.Procs RETURNS CHAR LANGUAGE OBJECTSCRIPT
{
  Set Stream = ##class(%Stream.TmpCharacter).%New()
  Do $System.OBJ.ExportToStream(name, Stream, "d")
  Set a = []
  For  Quit:Stream.AtEnd  Do a.%Push(Stream.ReadLine())
  Return a.%ToJSON()
}
"""

# Whether we created the stored procedure in init()
created = False


def get_export(svr:ns.Namespace, name:str):
    # URL for query actions
    scheme = 'https' if svr.https else 'http'
    url = f"{scheme}://{svr.host}:{svr.port}/api/atelier/v1/{svr.namespace}/action/query"
    
    # Get export for the requested name
    query = f"SELECT Tmp_CII.GetExport('{name}') AS result"
    dataout = json.dumps({ "query": query }).encode()
    rq = urq.Request(url, data=dataout, headers={'Content-Type': 'application/json'}, method='POST')
    
    try:
        with urq.urlopen(rq) as rsp:
            data = json.load(rsp)
    except URLError:
        logging.error(f"Accessing [POST] {url}:")
        raise
    
    # Check for errors
    errors = data['status']['errors']
    if errors:
        raise RuntimeError(errors[0]['error'])
    
    result = '\n'.join(data['result']['content'][0]['result'])
    return result


def list_lookup_tables(svr:ns.Namespace, specs:list):
    # URL for query actions
    scheme = 'https' if svr.https else 'http'
    url = f"{scheme}://{svr.host}:{svr.port}/api/atelier/v1/{svr.namespace}/action/query"

    # Build query for tables matching spec(s)
    condlst = []
    parmlst = []
    for spec in specs:
        condlst.append("TableName LIKE ?")
        parmlst.append(spec.replace('*', '%'))
    conds = ' OR '.join(condlst)
    query = "SELECT DISTINCT TableName FROM Ens_Util.LookupTable WHERE " + conds
    
    # Convert to JSON and UTF8-encode
    dataout = json.dumps({
            "query": query,
            "parameters": parmlst
        }).encode()

    # Run query
    rq = urq.Request(url, data=dataout, headers={'Content-Type': 'application/json'}, method='POST')
    try:
        with urq.urlopen(rq) as rsp:
            data = json.load(rsp)
    except URLError:
        logging.error(f"Accessing [POST] {url}:")
        raise
    
    # Check for errors
    errors = data['status']['errors']
    if errors:
        raise RuntimeError(errors[0]['error'])
    
    tables = [ item['TableName'] for item in data['result']['content']]

    return tables


def init(svr:ns.Namespace):
    global created

    # URL for query actions
    scheme = 'https' if svr.https else 'http'
    url = f"{scheme}://{svr.host}:{svr.port}/api/atelier/v1/{svr.namespace}/action/query"
    
    # Check whether the class containing the stored procedure exists
    query = "SELECT 1 FROM %Dictionary.ClassDefinition WHERE ID = 'Tmp.CII.Procs'"
    dataout = json.dumps({ "query": query }).encode()
    rq = urq.Request(url, data=dataout, headers={'Content-Type': 'application/json'}, method='POST')
    
    try:
        with urq.urlopen(rq) as rsp:
            data = json.load(rsp)
    except URLError:
        logging.error(f"Accessing [POST] {url}:")
        raise
    
    # If the class still exists, we're done
    if data['result']['content']:
        return

    # Get the SQL to create the stored procedure
    dataout = json.dumps({ "query": CREATE_EXPORT_PROC }).encode()
    rq = urq.Request(url, data=dataout, headers={'Content-Type': 'application/json'}, method='POST')
    
    try:
        with urq.urlopen(rq) as rsp:
            data = json.load(rsp)
    except URLError:
        logging.error(f"Accessing [POST] {url}:")
        raise
    
    errors = data['status']['errors']
    if errors:
        raise RuntimeError(errors[0]['error'])
    
    created = True


def cleanup(svr:ns.Namespace):
    global created

    # If we did not create the stored procedure, there's nothing to do here
    if not created:
        return
    
    # URL for query actions
    scheme = 'https' if svr.https else 'http'
    url = f"{scheme}://{svr.host}:{svr.port}/api/atelier/v1/{svr.namespace}/action/query"
    
    # Drop the stored procedure we created
    query = "DROP PROCEDURE Tmp_CII.GetExport"
    dataout = json.dumps({ "query": query }).encode()
    rq = urq.Request(url, data=dataout, headers={'Content-Type': 'application/json'}, method='POST')
    
    try:
        with urq.urlopen(rq) as rsp:
            data = json.load(rsp)
    except URLError:
        logging.error(f"Accessing [POST] {url}:")
        raise
    
    # If that returned errors, don't raise but do add a warning to the log
    errors = data['status']['errors']
    if errors:
        logging.warn('Error cleaning up stored procedure:' + '\n'.join(errors))

