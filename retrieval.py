from typing import List, Dict
import json
import base64
import urllib.request as urq
from urllib.error import URLError
import logging

import namespace as ns
from config import ConfigurationError


def get_modified_items(config:ns.Namespace, itemtype:str):
    """ Retrieves all items of specified type from the server """

    logging.info(f"Retrieving available items of type {itemtype}")

    # Assemble URL and create request
    svr = config.Server
    scheme = 'https' if svr.https else 'http'
    generated = '1' if config.Project.generated else '0'
    url = f"{scheme}://{svr.host}:{svr.port}/api/atelier/v1/{svr.namespace}/modified/{itemtype}?generated={generated}"
    rq = urq.Request(url, data=b'[]', headers={'Content-Type': 'application/json'}, method='POST')
    
    try:
        # Get and convert to JSON
        with urq.urlopen(rq) as rsp:
            data = json.load(rsp)
    except URLError:
        logging.error(f"Accessing {url}:")
        raise
    
    # Check for configuration issue:
    if data['status']['errors']:
        e = data['status']['errors'][0]
        if e['code'] == 16004:
            raise ConfigurationError(f"Fout van server: onbekend type item '{itemtype}'.")

    return data

def get_items_for_type(config:ns.Namespace, itemtype:str):
    """ Retrieves all items of a given type from the server """

    logging.info(f"Retrieving available {itemtype} items")
    
    # Assemble URL
    svr = config.Server
    scheme = 'https' if svr.https else 'http'
    url = f"{scheme}://{svr.host}:{svr.port}/api/atelier/v1/{svr.namespace}/docnames/{itemtype}"
    
    # Get and convert to JSON
    try:
        with urq.urlopen(url) as rsp:
            data = json.load(rsp)
    except URLError:
        logging.error(f"Accessing {url}:")
        raise
    
    return data


def extract_items(config:ns.Namespace, result:List, items:List):
    """ Extract items from service call result and store in list. """

    mapped = config.Project.mapped
    generated = config.Project.generated
    for db in result:
        # Skip stuff coming from system databases
        if not mapped and db.get('dbsys', False): continue
        # Check items ('docs') in this DB
        for doc in db['docs']:
            # Skip generated (if so configured) and deployed documents
            if not generated and doc.get('gen', False): continue
            if doc.get('depl', False): continue
            # Skip item if it doesn't match the project spec
            if not check_item(config.itemsrx, doc['name']): continue
            # Remove irrelevant data
            del doc['gen']
            del doc['depl']
            # Store item for saving
            items.append(doc)

def extract_csp_items(config:ns.Namespace, result:List, items:List):
    """ Extract items from service call result and store in list. """
    
    specs = config.itemsrx
    for item in result:
        if not check_item(specs, item['name']): continue
        del item['db']
        del item['upd']
        items.append(item)


def retrieve_item(config:ns.Namespace, item:dict):
    """ Retrieves an item from the server """

    svr = config.Server

    # CSP items start with a slash; remove it
    name = item['name']
    if name[0] == '/': name = name[1:]

    scheme = 'https' if svr.https else 'http'
    url = f"{scheme}://{svr.host}:{svr.port}/api/atelier/v1/{svr.namespace}/doc/{name}"
    
    try:
        with urq.urlopen(url) as rsp:
            data = json.load(rsp)
    except URLError:
        logging.error(f"Accessing {url}:")
        raise
    
    result = data['result']
    content = result['content']

    # CSP/RTN text contents is missing a trailing newline; fix this unless
    # the configuration says no.
    nofix = config.Local.disable_eol_fix
    if not nofix and result['cat'] in ('CSP', 'RTN') and not result['enc']:
        content.append('')
    
    # Contents may be returned line-by-line: always for text, and for
    # base-64 if too big.
    content = '\n'.join(content)

    if result['enc'] and content:
        # Base-64 encoded data, to decode convert to bytes first
        content = base64.decodebytes(content.encode())
    
    return content


def check_item(specs:Dict[str,List], item:str):
    """ Checks if a name matches the project specifications """

    # First check exclusion specs
    for spec in specs['-']:
        if spec.match(item):
            return False
    
    # Check inclusion spec
    for spec in specs['+']:
        if spec.match(item):
            return True
    
    # Not mentioned in any spec: don't include
    return False


def init(config:ns.Namespace):
    """ Setup urllib opener for auth and cookie handling """

    svr = config.Server

    # Setup a (preemptive) basic auth handler
    password_mgr = urq.HTTPPasswordMgrWithPriorAuth()
    scheme = 'https' if svr.https else 'http'
    password_mgr.add_password(None, f"{scheme}://{svr.host}:{svr.port}/",
        svr.user, svr.password, is_authenticated=True)
    auth_handler = urq.HTTPBasicAuthHandler(password_mgr)

    # Setup the cookie handler
    cookiejar = config.cookiejar
    cookie_handler = urq.HTTPCookieProcessor(cookiejar)

    # Create an opener using these handlers, and make it default
    opener = urq.build_opener(auth_handler, cookie_handler)
    opener.addheaders = [('Accept', 'application/json')]
    urq.install_opener(opener)


