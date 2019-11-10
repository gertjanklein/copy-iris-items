#!/usr/bin/env python3
# encoding: UTF-8

import sys
import os
from os.path import dirname, join, isabs, abspath, exists, splitext, isfile, basename
import logging
from configparser import ConfigParser
import datetime, time
import re
import base64
import urllib.request as urq
import http.cookiejar
import json


def main(inifile):
    """ Loads items as specified in the ini file """

    # Set up logging to file next to ini file
    setup_logging(inifile)
    
    # Log unhandled exceptions
    sys.excepthook = unhandled_exception

    # Get configuration
    config = read_cfg(inifile)

    # Setup authorization and cookie handling
    setup_urllib(config)

    # Log appends; create visible separation for this run
    logging.info(f"\n\n===== Starting sync at {str(datetime.datetime.now()).split('.')[0]}")

    # Get list of all items we're interested in
    items = []
    for tp in config['types']:
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
    
    # Save cookies for reuse if we call the same server quickly again
    if config['savecookies']:
        config['cookiejar'].save(ignore_discard=True)

    msgbox(f"Copied {len(items)} items.")


def read_cfg(inifile):
    """ Reads server and project specifications from the ini file """

    # Get config parser that allows keys without values, and preserves case
    ini = ConfigParser(allow_no_value=True)
    ini.optionxform = str
    ini.read(inifile, 'UTF-8')

    # Return configuration as a dictionary
    config = {}
    config['svr'] = ini['Server']

    # Get project specifications
    config['specs'], config['types'] = get_specs(ini['Project'].keys())

    # Directories are relative to the ini file, not the 'current' dir:
    basedir = dirname(inifile)
    tplvars = {'{ininame}': splitext(basename(inifile))[0] }
    config['dir'] = determine_dir(ini['Local'].get('dir'), '{ininame}\\src', basedir, tplvars)
    config['cspdir'] = determine_dir(ini['Local'].get('cspdir'), '{ininame}\\csp', basedir, tplvars)

    # Cookie file next to this one. Keep one file per IRIS instance.
    # Keep jar in config structure so we can save it at the end of the program.
    svr = ini['Server']
    cookiefile = f"cookies;{svr['host']};{svr['port']}.txt"
    cookiefile = join(dirname(__file__), cookiefile)
    config['cookiejar'] = http.cookiejar.LWPCookieJar(cookiefile, delayload=False)

    # File encoding, defaulting to UTF-8
    encoding = ini['Local'].get('encoding')
    config['encoding'] = encoding if encoding else 'UTF-8'

    # Flags
    config['subdirs'] = ini['Local'].getboolean('subdirs', fallback=True)
    config['savecookies'] = ini['Local'].getboolean('cookies', fallback=False)

    return config


def get_specs(input):
    """ Get project specification and convert to regular expressions. """

    specs = [ spec for spec in input ]

    # Determine the types of items we're interested in
    types = { 'csp' if '/' in spec else spec.rsplit('.', maxsplit=1)[1] for spec in specs }

    # Convert specifications to regexes for matching
    regexes = { '+': [], '-': [] }
    for spec in specs:
        # Exclusion spec?
        if spec[0] == '-':
            spec = spec[1:]
            stype = '-'
        else:
            stype = '+'
        # Escape dots in spec
        spec = spec.replace('.', '\\.')
        # Create valid regex for star
        spec = spec.replace('*', '.*')
        regex = re.compile(spec)
        regexes[stype].append(regex)
    
    return regexes, types


def determine_dir(input, default, basedir, replacements):
    """ Determines directory and makes it an absolute path. """

    result = input if input else default
    for name in replacements:
        result = result.replace(name, replacements[name])
    if not isabs(result):
        result = join(basedir, result)
    return result


def get_modified_items(config, itemtype):
    """ Retrieves all items of specified type from the server """

    logging.info(f"Retrieving available items of type {itemtype}")

    # Assemble URL and create request
    svr = config['svr']
    url = f"http://{svr['host']}:{svr['port']}/api/atelier/v1/{svr['namespace']}/modified/{itemtype}?generated=0"
    rq = urq.Request(url, data=b'[]', headers={'Content-Type': 'application/json'}, method='POST')
    
    # Get and convert to JSON
    with urq.urlopen(rq) as rsp:
        data = json.load(rsp)
    
    return data


def get_items_for_type(config, itemtype):
    """ Retrieves all CSP items from the server """

    logging.info(f"Retrieving available {itemtype} items")
    
    # Assemble URL
    svr = config['svr']
    url = f"http://{svr['host']}:{svr['port']}/api/atelier/v1/{svr['namespace']}/docnames/{itemtype}"
    
    # Get and convert to JSON
    with urq.urlopen(url) as rsp:
        data = json.load(rsp)
    
    return data


def extract_items(config, result, items):
    """ Extract items from service call result and store in list. """

    for db in result:
        # Skip stuff coming from system databases
        if db.get('dbsys', False): continue
        # HSCUSTOM is not marked system, but we'll skip it as well
        if db['dbname'] == 'HSCUSTOM': continue
        # Check items ('docs') in this DB
        for doc in db['docs']:
            # Skip generated and deployed documents
            if doc.get('gen', False): continue
            if doc.get('depl', False): continue
            # Skip item if it doesn't match the project spec
            if not check_item(config['specs'], doc['name']): continue
            # Remove irrelevant data
            del doc['gen']
            del doc['depl']
            # Store item for saving
            items.append(doc)


def extract_csp_items(config, result, items):
    """ Extract items from service call result and store in list. """
    
    for item in result:
        if not check_item(config['specs'], item['name']): continue
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
    if config['subdirs']:
        # Non-CSP, make packages directories.
        parts = name.split('.')
        name = '.'.join(parts[-2:])
        parts = parts[:-2]
    else:
        # Non-CSP, packages as part of filename.
        parts = []
    
    outdir = config['dir']
    return join(outdir, *parts, name)


def retrieve_item(config, item):
    """ Retrieves an item from the server """

    svr = config['svr']

    # CSP items start with a slash; remove it
    name = item['name']
    if name[0] == '/': name = name[1:]

    url = f"http://{svr['host']}:{svr['port']}/api/atelier/v1/{svr['namespace']}/doc/{name}"
    
    rsp = urq.urlopen(url)
    with rsp:
        data = json.load(rsp)
    
    # Contents may be returned line-by-line
    content = data['result']['content']
    content = '\n'.join(content)
    if data['result']['enc'] and content:
        # Base-64 encoded data, to decode convert to bytes first
        content = base64.decodebytes(content.encode())
    
    return content


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

    svr = config['svr']

    # Setup a (preemptive) basic auth handler
    password_mgr = urq.HTTPPasswordMgrWithPriorAuth()
    password_mgr.add_password(None, f"http://{svr['host']}:{svr['port']}/",
        svr['user'], svr['password'], is_authenticated=True)
    auth_handler = urq.HTTPBasicAuthHandler(password_mgr)

    # Setup the cookie handler
    cookiejar = config['cookiejar']
    cookie_handler = urq.HTTPCookieProcessor(cookiejar)

    # Create an opener using these handlers, and make it default
    opener = urq.build_opener(auth_handler, cookie_handler)
    opener.addheaders = [('Accept', 'application/json')]
    urq.install_opener(opener)


def setup_logging(inifile):
    """ Setup logging to file """

    # Determine log file name
    base, ext = splitext(inifile)
    if ext.lower() == '.ini':
        logfile = f'{base}.log'
    else:
        logfile = f'{inifile}.log'
    
    # Display what we log as-is, no level strings etc.
    logging.basicConfig(
        filename=abspath(logfile),
        level=logging.INFO,
        format='%(message)s')


def unhandled_exception(exc_type, exc_value, exc_traceback):
    """ Handle otherwise unhandled exceptions by logging them """

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
        msgbox(f"Usage: {sys.argv[0]} <inifile>", True)
        sys.exit(1)

    inifile = sys.argv[1]
    if not exists(inifile) or not isfile(inifile):
        msgbox(f"File {inifile} not found.\nUsage: {sys.argv[0]} <inifile>", True)
        sys.exit(1)
    
    main(inifile)
    

