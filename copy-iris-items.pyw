#!/usr/bin/env python3
# encoding: UTF-8

import sys
import os
from os.path import join, isdir, isfile, exists, dirname, isabs, abspath, splitext, basename
import logging
import datetime, time
import re
import base64
import urllib.request as urq
import json
import xml.etree.ElementTree as ET

import data_handler
from config import get_config, ConfigurationError


def main(cfgfile):
    """ Loads items as specified in the config file """

    # Initial logging setup: file next to ini file. Errors parsing the
    # config file will be logged here.
    setup_basic_logging(cfgfile)
    
    # Log unhandled exceptions
    sys.excepthook = unhandled_exception

    # Get configuration
    config = get_config(cfgfile)

    # Final logging setup: file in directory specified in config file.
    setup_logging(config)

    # Setup authorization and cookie handling
    setup_urllib(config)

    # If needed, make sure we have the support code to retrieve data exports
    project = config.Project
    if project.enssettings.name or project.lookup:
        data_handler.init(config.Server)

    # Log appends; create visible separation for this run
    now = str(datetime.datetime.now())
    logging.info(f"\n\n===== Starting sync at {now.split('.')[0]}")

    # Get list of all items we're interested in
    items = []
    for tp in config.types:
        # Get server items for this type
        if tp != 'csp':
            # This call is way faster than get_items_for_type
            data = get_modified_items(config, tp)
            extract_items(config, data['result']['content'], items)
        else:
            # get_modified_items doesn't support CSP
            data = get_items_for_type(config, 'csp')
            extract_csp_items(config, data['result']['content'], items)

    # Save each one to disk
    for item in items:
        save_item(config, item)
    count = len(items)

    # Save Ensemble deployable settings and lookup tables, if asked
    if project.enssettings.name:
        count += save_deployable_settings(config)
    if project.lookup:
        count += save_lookup_tables(config)
    
    # Save cookies for reuse if we call the same server quickly again
    if config.Local.cookies:
        config['cookiejar'].save(ignore_discard=True)

    # Cleanup support code
    data_handler.cleanup(config.Server)

    msgbox(f"Copied {count} items.")


def get_modified_items(config, itemtype):
    """ Retrieves all items of specified type from the server """

    logging.info(f"Retrieving available items of type {itemtype}")

    # Assemble URL and create request
    svr = config.Server
    scheme = 'https' if svr.https else 'http'
    url = f"{scheme}://{svr.host}:{svr.port}/api/atelier/v1/{svr.namespace}/modified/{itemtype}?generated=0"
    rq = urq.Request(url, data=b'[]', headers={'Content-Type': 'application/json'}, method='POST')
    
    try:
        # Get and convert to JSON
        with urq.urlopen(rq) as rsp:
            data = json.load(rsp)
    except urq.URLError:
        logging.error(f"Accessing {url}:")
        raise
    
    return data


def get_items_for_type(config, itemtype):
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
    except urq.URLError:
        logging.error(f"Accessing {url}:")
        raise
    
    return data


def extract_items(config, result, items):
    """ Extract items from service call result and store in list. """

    mapped = config.Project.mapped
    for db in result:
        # Skip stuff coming from system databases
        if not mapped and db.get('dbsys', False): continue
        # Check items ('docs') in this DB
        for doc in db['docs']:
            # Skip generated and deployed documents
            if doc.get('gen', False): continue
            if doc.get('depl', False): continue
            # Skip item if it doesn't match the project spec
            if not check_item(config.itemsrx, doc['name']): continue
            # Remove irrelevant data
            del doc['gen']
            del doc['depl']
            # Store item for saving
            items.append(doc)


def extract_csp_items(config, result, items):
    """ Extract items from service call result and store in list. """
    
    specs = config.itemsrx
    for item in result:
        if not check_item(specs, item['name']): continue
        del item['db']
        del item['upd']
        items.append(item)


def check_item(specs, item):
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


def determine_filename(config, item):
    """ Determine output filename for an item """

    name = item['name']
    if name[0] == '/':
        # A CSP item. Always keep directory structure as-is.
        parts = item['name'].split('/')
        name = parts[-1]
        parts = parts[1:-1]
        cspdir = config['cspdir']
        return join(cspdir, *parts, name)
    
    # Non-CSP item (cls, mac, inc, ...)
    if config.Local.subdirs:
        # Non-CSP, make packages directories.
        parts = name.split('.')
        name = '.'.join(parts[-2:])
        parts = parts[:-2]
    else:
        # Non-CSP, packages as part of filename.
        parts = []
    
    return join(config.dir, *parts, name)


def retrieve_item(config, item):
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
    except urq.URLError:
        logging.error(f"Accessing {url}:")
        raise
    
    # Contents may be returned line-by-line
    content = data['result']['content']
    content = '\n'.join(content)
    if data['result']['enc'] and content:
        # Base-64 encoded data, to decode convert to bytes first
        content = base64.decodebytes(content.encode())
    
    return content


def save_deployable_settings(config):
    """ Retrieves and saves Ensemble deployable config settings. """
    
    logging.info(f"Retrieving and saving Ens.Config.DefaultSettings.esd")
    
    data = data_handler.get_export(config.Server, 'Ens.Config.DefaultSettings.esd')
    if not data:
        return 0
    
    # Make sure the output directory exists
    if not isdir(config.datadir):
        os.makedirs(config.datadir)
    
    # Filename for settings
    fname = join(config.datadir, config.Project.enssettings.name)
    
    # Strip the actual values, if so requested
    if config.Project.enssettings.strip:
        root = ET.fromstring(data)
        for item in root.iter('item'):
            del item.attrib['value']
        # tostring doesn't return an XML declaration
        data = '<?xml version="1.0" encoding="UTF-8"?>\n'
        data += ET.tostring(root, encoding='unicode')
    
    with open(fname, 'w', encoding='UTF-8') as f:
        f.write(data + '\n')
    
    return 1


def save_lookup_tables(config):
    logging.info('Loading list of lookup tables')
    tables = data_handler.list_lookup_tables(config.Server, config.Project.lookup)
    if not tables:
        logging.info('No data lookup tables matching the specifications found.')
        return 0

    count = 0
    for table in tables:
        if not table.lower().endswith('.lut'):
            table = table + '.LUT'
        # Extension must be uppercase or mgmt portal won't recognize it
        if not table.endswith('.LUT'):
            table = table[:-4] + '.LUT'

        logging.info(f"Retrieving and saving {table}")

        data = data_handler.get_export(config.Server, table)
        if not data:
            logging.info(f"  {table} contains no data, skipping.")
            continue
        
        # Make sure the output directory exists
        if not isdir(config.datadir):
            os.makedirs(config.datadir)
    
        fname = join(config.datadir, table[:-3] + 'lut')
        with open(fname, 'w', encoding='UTF-8') as f:
            f.write(data + '\n')
        count += 1
    
    return count


def save_item(config, item):
    """ Retrieves an item and saves it to disk """

    logging.info(f"Retrieving and saving {item['name']}")

    data = retrieve_item(config, item)
    fname = determine_filename(config, item)

    dir = dirname(fname)
    os.makedirs(dir, exist_ok=True)

    # Write the data to the output file. If this fails, catch the exception
    # to log the name of the file we tried to write to, and reraise; function
    # unhandled_exception will log the stack trace.
    try:
        if type(data) != bytes:
            # Text document; store in specified encoding (default UTF-8)
            with open(fname, 'wt', encoding=config['encoding']) as f:
                f.write(data)
        else:
            # Binary document (e.g. image from CSP application)
            with open(fname, 'wb') as f:
                f.write(data)
    except Exception:
        logging.error(f"\nException detected writing to file {fname}")
        raise

    # Set modified date/time to that of item in IRIS
    set_file_datetime(fname, item['ts'])


def set_file_datetime(filename, timestamp):
    """ Sets a file's modified date/time """

    # Convert timestamp string to datetime object
    dt = datetime.datetime.fromisoformat(timestamp)
    # Convert to seconds since epoch
    tm = time.mktime(dt.timetuple())
    # Set access end modified times
    os.utime(filename, (tm, tm))


def setup_urllib(config):
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


def setup_basic_logging(cfgfile):
    """ Initial logging setup: log to file next to config file """

    # Determine log file name
    base, ext = splitext(cfgfile)
    if ext.lower() == '.toml':
        logfile = f'{base}.log'
    else:
        logfile = f'{cfgfile}.log'
    
    # Create handler with delayed creation of log file
    handlers = [logging.FileHandler(logfile, delay=True)]

    # Display what we log as-is, no level strings etc.
    logging.basicConfig(handlers=handlers, level=logging.INFO,
        format='%(message)s')


def setup_logging(config):
    """ Final logging setup: allow log location override in config """

    # If no logdir specified, setup is already complete
    logdir = config.Local._get('logdir')
    if not logdir: return

    # Determine filename (without path)
    base, ext = splitext(basename(config.cfgfile))
    if ext.lower() == '.toml':
        logfile = f'{base}.log'
    else:
        logfile = f'{base}.{ext}.log'

    # Determine filename (with path)
    name = join(logdir, logfile)
    if not isabs(logdir):
        # Logdir not absolute: make it relative to dir config file is in
        name = join(dirname(config.cfgfile), name)

    # Make sure the log directory exists
    logdir = dirname(name)
    os.makedirs(logdir, exist_ok=True)

    # Replace the current logging handler with one using the newly
    # determined path
    logger = logging.getLogger()
    logger.handlers.clear()
    logger.handlers.append(logging.FileHandler(name, 'a'))


def unhandled_exception(exc_type, exc_value, exc_traceback):
    """ Handle otherwise unhandled exceptions by logging them """

    if exc_type == ConfigurationError:
        msg = exc_value.args[0]
        logging.error("\n%s", msg)
    else:
        msg = f"An error occurred; please see the log file for details.\n\n{exc_value}"
        logging.exception("\n##### Unhandled exception:", exc_info=(exc_type, exc_value, exc_traceback))
    msgbox(f"An error occurred; please see the log file for details.\n\n{exc_value}", True)
    sys.exit(1)


def msgbox(msg, is_error=False):
    """ Display, if on Windows, a message box """

    if os.name == 'nt':
        if is_error:
            flags = 0x30
            title = "Error"
        else:
            flags = 0
            title = "Info"
        import ctypes
        MessageBox = ctypes.windll.user32.MessageBoxW
        MessageBox(None, msg, title, flags)
    else:
        print(msg)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        msgbox(f"Usage: {sys.argv[0]} <cfgfile>", True)
        sys.exit(1)

    cfgfile = sys.argv[1]
    if not exists(cfgfile) or not isfile(cfgfile):
        msgbox(f"File {cfgfile} not found.\nUsage: {sys.argv[0]} <cfgfile>", True)
        sys.exit(1)
    
    main(cfgfile)
    

