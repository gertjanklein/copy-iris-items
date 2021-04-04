
from typing import List, Dict
import threading
import base64
import logging
import http.cookiejar
from io import StringIO
from time import sleep

import requests

import namespace as ns
from config import ConfigurationError


 # Thread local storage for requests session objects
tls:threading.local


def get_modified_items(config:ns.Namespace, itemtype:str):
    """ Retrieves all items of specified type from the server """

    logging.info(f"Retrieving available items of type {itemtype}")

    # Assemble URL and create request
    svr = config.Server
    scheme = 'https' if svr.https else 'http'
    generated = '1' if config.Project.generated else '0'
    url = f"{scheme}://{svr.host}:{svr.port}/api/atelier/v1/{svr.namespace}/modified/{itemtype}?generated={generated}"

    # Get JSON response
    try:
        rsp = tls.session.post(url, json=[])
    except requests.exceptions.RequestException:
        logging.error(f"Accessing {url}:")
        raise
    data = rsp.json()

    # Check for configuration issue:
    if data['status']['errors']:
        e = data['status']['errors'][0]
        if e['code'] == 16004:
            raise ConfigurationError(f"Error from server: unknown item type '{itemtype}'.")

    return data

def get_items_for_type(config:ns.Namespace, itemtype:str):
    """ Retrieves all items of a given type from the server """

    logging.info(f"Retrieving available {itemtype} items")
    
    # Assemble URL
    svr = config.Server
    scheme = 'https' if svr.https else 'http'
    url = f"{scheme}://{svr.host}:{svr.port}/api/atelier/v1/{svr.namespace}/docnames/{itemtype}"
    
    # Get JSON response
    try:
        rsp = tls.session.get(url)
    except requests.exceptions.RequestException:
        logging.error(f"Accessing {url}:")
        raise
    data = rsp.json()
    
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
    
    # Get JSON response
    try:
        rsp = tls.session.get(url)
    except requests.exceptions.RequestException:
        logging.error(f"Accessing {url}:")
        raise
    data = rsp.json()
    
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


def init(auth, cookie_data):
    tls.session = requests.Session()
    if auth[0]:
        tls.session.auth = auth
    if cookie_data:
        jar = http.cookiejar.LWPCookieJar()
        datastream = StringIO(cookie_data)
        jar._really_load(datastream, "<copy>", ignore_discard=True, ignore_expires=False)
        tls.session.cookies = jar

def cleanup():
    if hasattr(tls, "session"):
        tls.session.close()
        # Needed to prevent unclosed socket ResourceWarning
        sleep(0.001)

