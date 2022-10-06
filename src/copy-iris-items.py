#!venv/Scripts/python
# encoding: UTF-8

import os
from os.path import join, isdir, dirname
from typing import Any, List, Dict
from concurrent.futures import ThreadPoolExecutor, wait
import threading
import logging
import datetime, time

import requests
import lxml.etree as ET

import namespace as ns
from config import get_config, ConfigurationError, msgbox
import data_handler
import retrieval as ret


# Thread-local storage for requests session objects
tls = threading.local()


def main():
    # Get configuration and handle command line arguments
    config = get_config()
    run(config)


def run(config):
    """Loads items as specified in the config file"""

    # Initialize requests session and check server accessibility
    init(config)

    # If needed, make sure we have the support code to retrieve data exports
    project = config.Project
    if project.enssettings.name or project.lookup:
        data_handler.init(config, tls)
    
    # Place thread local storage object in retrieval module
    ret.tls = tls

    # Log appends; create visible separation for this run
    now = str(datetime.datetime.now())
    logging.info(f"\n\n===== Starting sync at {now.split('.')[0]}") #pylint:disable=C0207

    # Get list of all items we're interested in
    items: List[dict] = []
    for tp in config.types:
        # Get server items for this type
        if tp != 'csp':
            # This call is way faster than get_items_for_type
            data = ret.get_modified_items(config, tp)
            ret.extract_items(config, data['result']['content'], items)
        else:
            # get_modified_items doesn't support CSP
            data = ret.get_items_for_type(config, 'csp')
            ret.extract_csp_items(config, data['result']['content'], items)

    # Save each one to disk
    save_items(config, items)
    count = len(items)

    # Save Ensemble deployable settings and lookup tables, if asked
    if project.enssettings.name:
        count += save_deployable_settings(config)
    if project.lookup:
        count += save_lookup_tables(config)
    
    # Cleanup
    data_handler.cleanup(config.Server)
    ret.cleanup()

    # Give feedback we're done, unless this was turned off
    if not config.no_gui:
        msgbox(f"Copied {count} items.")


def determine_filename(config:ns.Namespace, item:dict):
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


def save_deployable_settings(config:ns.Namespace):
    """ Retrieves and saves Ensemble deployable config settings. """
    
    logging.info("Retrieving and saving Ens.Config.DefaultSettings.esd")
    
    data = data_handler.get_export(config.Server, 'Ens.Config.DefaultSettings.esd')
    if not data:
        return 0
    
    # Make sure the output directory exists
    if not isdir(config.datadir):
        os.makedirs(config.datadir)
    
    # Filename for settings
    fname = join(config.datadir, config.Project.enssettings.name)
    
    # Remove timestamp and version from export
    root = ET.fromstring(data.encode('UTF-8')) # type: ignore
    for name in 'ts', 'zv':
        if name in root.attrib:
            del root.attrib[name]

    # Strip the actual values, if so requested
    if config.Project.enssettings.strip:
        for item in root.iter('item'):
            if 'value' in item.attrib:
                del item.attrib['value']
    
    # tostring doesn't return an XML declaration
    data = '<?xml version="1.0" encoding="UTF-8"?>\n'
    data += ET.tostring(root, encoding='unicode') # type: ignore
    
    with open(fname, 'w', encoding='UTF-8') as f:
        f.write(data + '\n')
    
    return 1


def save_lookup_tables(config:ns.Namespace):
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
        
        # Remove timestamp and version from export
        root = ET.fromstring(data.encode('UTF-8')) # type: ignore
        for name in 'ts', 'zv':
            if name in root.attrib:
                del root.attrib[name]
        # tostring doesn't return an XML declaration
        data = '<?xml version="1.0" encoding="UTF-8"?>\n'
        data += ET.tostring(root, encoding='unicode') # type: ignore

        # Make sure the output directory exists
        if not isdir(config.datadir):
            os.makedirs(config.datadir)
    
        fname = join(config.datadir, table[:-3] + 'lut')
        with open(fname, 'w', encoding='UTF-8') as f:
            f.write(data + '\n')
        count += 1
    
    return count


def save_items(config:ns.Namespace, items:List):
    """ Saves items either in serial or in parallel """

    # Check if/how many threads we should use:
    threads = config.Server.threads
    if threads > 1:
        save_items_parallel(config, items, threads)
        return
    
    # Just save the items one by one
    for item in items:
        save_item(config, item)


def save_items_parallel(config:ns.Namespace, items:List, threads:int):
    """ Saves items in parallel """

    # Pass to worker threads: login information and cookies
    svr = config.Server
    auth = (svr.user, svr.password) if svr.user else ()
    cookie_data = "#LWP-Cookies-2.0\n" + tls.session.cookies.as_lwp_str()
    args = (auth, cookie_data)

    futures = []
    with ThreadPoolExecutor(max_workers=threads, 
            initializer=ret.init, initargs=args) as executor:
        # Retrieve the items
        for item in items:
            futures.append(executor.submit(save_item, config, item))
        wait(futures)
        
        # Call cleanup code to release requests sessions
        futures.clear()
        for _ in range(threads):
            futures.append(executor.submit(ret.cleanup))
        wait(futures)


def save_item(config:ns.Namespace, item:Dict[str,Any]):
    """ Retrieves an item and saves it to disk """

    logging.info(f"Retrieving and saving {item['name']}")

    data = ret.retrieve_item(config, item)
    fname = determine_filename(config, item)

    dir = dirname(fname)
    os.makedirs(dir, exist_ok=True)

    # Write the data to the output file. If this fails, catch the exception
    # to log the name of the file we tried to write to, and reraise; function
    # unhandled_exception will log the stack trace.
    try:
        if not isinstance(data, bytes):
            # Text document; store in specified encoding (default UTF-8)
            with open(fname, 'wt', encoding=config['encoding']) as ft:
                ft.write(data)
        else:
            # Binary document (e.g. image from CSP application)
            with open(fname, 'wb') as fb:
                fb.write(data)
    except UnicodeEncodeError as e:
        faulty = data[e.start-1:e.end]
        msg = f"Error saving {item['name']}: some characters can't be saved" \
            f" in the configured encoding ({config['encoding']}). Problem" \
            f" starts around character {e.start}; data: {faulty}."
        raise ConfigurationError(msg) from None
    
    except Exception:
        logging.error(f"\nException detected writing to file {fname}")
        raise

    # Set modified date/time to that of item in IRIS
    set_file_datetime(fname, item['ts'])


def set_file_datetime(filename:str, timestamp:str):
    """ Sets a file's modified date/time """

    # Convert timestamp string to datetime object
    dt = datetime.datetime.fromisoformat(timestamp)
    # Convert to seconds since epoch
    tm = time.mktime(dt.timetuple())
    # Set access end modified times
    os.utime(filename, (tm, tm))


def init(config:ns.Namespace):
    # Set up the main thread requests session, and give it our cookie jar
    svr = config.Server
    tls.session = requests.Session()
    tls.session.cookies = config.cookiejar
    if config.Server.user:
        tls.session.auth = (svr.user, svr.password)
    
    # Make sure the server can be reached
    try:
        scheme = 'https' if svr.https else 'http'
        # This URL returns namespace information. If it returns a 200 then
        # we can access the server.
        url = f"{scheme}://{svr.host}:{svr.port}/api/atelier/v1/{svr.namespace}"
        rsp = tls.session.get(url)
        
        if rsp.status_code == 404:
            msg = f"Url {url} returns a 404 (not found).\n" \
                "Did you specify the correct namespace?\n" \
                "Is the /api/atelier CSP application enabled?"
            raise ns.ConfigurationError(msg)
        
        if rsp.status_code == 401:
            msg = f"Url {url} returns a 401 (unauthorized).\n" \
                "Are the credentials present and correct?"
            raise ns.ConfigurationError(msg)
        
        if rsp.status_code != 200:
            msg = f"Url {url} returns a {rsp.status_code} ({rsp.reason}).\n" \
                "Please check your setup."
            raise ns.ConfigurationError(msg)
        
    except requests.exceptions.RequestException:
        logging.error(f"Accessing [POST] {url}:") # type: ignore
        raise
    
    # Save cookies for reuse if we call the same server quickly again
    if config.Local.cookies:
        config.cookiejar.save(ignore_discard=True)


def cleanup_logging():
    """ Closes all resources taken by the loggers' handlers """

    # Get root logger
    loggers = [logging.getLogger()]
    # Get all other loggers, if any
    logger_names = logging.root.manager.loggerDict # pylint: disable=no-member
    loggers = loggers + [logging.getLogger(name) for name in logger_names]

    # Call close() on each handler in each logger
    for logger in loggers:
        for handler in logger.handlers:
            handler.close()
        logger.handlers.clear()


if __name__ == '__main__':
    main()
