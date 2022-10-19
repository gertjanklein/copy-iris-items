
import sys, os
from os.path import exists, isfile, abspath, isabs, dirname, basename, splitext, join
import re
import http.cookiejar
import argparse
from io import StringIO
import logging

from typing import List, cast

import toml

import namespace as ns
from namespace import ConfigurationError


def get_config() -> ns.Namespace:
    """
    Creates and returns the configuration namespace
    """

    # Get configuration filename from commandline
    args = parse_args()
    cfgfile = args.config

    # Initial logging setup: file next to config file. Errors parsing the
    # config file will be logged here.
    setup_basic_logging(cfgfile)
    
    # Log unhandled exceptions
    sys.excepthook = unhandled_exception

    # Get parsed config data
    config = ns.dict2ns(toml.load(cfgfile))
    config.cfgfile = cfgfile
    config.cfgdir = dirname(cfgfile)
    config.cfgname = splitext(basename(cfgfile))[0]

    # Minimal check for logging configuration
    local = ns.check_section(config, 'Local')
    ns.check_default(local, 'logdir', '')
    levels = 'debug,info,warning,error,critical'.split(',')
    ns.check_oneof(local, 'loglevel', levels, 'info')
    
    # Merge-in setting from the file specified in augment_from, if any
    merge_augmented_settings(config)

    # Do final setup of logging
    setup_logging(config)

    # Merge command line overrides into configuration
    merge_overrides(args, config)

    # Make sure configuration is complete
    check(config)
    
    # Create regexes where needed
    config.itemsrx, config.types = get_specs(config.Project.items)
    config.lookuprx = get_lookup_specs(config.Project.lookup)

    # Determine various directories
    local = config.Local
    basedir = abspath(dirname(cfgfile))
    cfgname = splitext(basename(cfgfile))[0]
    tpl = { 'cfgname': cfgname }
    for name, default in ("dir", "src"), ("cspdir", "csp"), ("datadir", "data"):
        default = join(cfgname, default)
        config[name] = determine_dir(local[name], default, basedir, tpl)
    
    # Create cookie jar for session persistence
    svr = config.Server
    cookiefile = f"cookies;{svr['host']};{svr['port']}.txt"
    cookiefile = join(dirname(__file__), cookiefile)
    config.cookiejar = http.cookiejar.LWPCookieJar(cookiefile)
    if exists(cookiefile):
        config.cookiejar.load(ignore_discard=True)

    # File encoding defaults to UTF-8
    config.encoding = local.encoding if local.encoding else 'UTF-8'

    return config


def get_specs(input):
    """ Get project specifications and convert to regular expressions. """

    # Determine the types of items we're interested in
    types = set()
    for spec in input:
        if '/' in spec:
            types.add('csp')
        else:
            _, ext = splitext(spec)
            if not ext:
                msg = f"Project item specifications need an extension; {spec} doesn't have one."
                raise ConfigurationError(msg)
            types.add(ext[1:])
    
    # Convert specifications to regexes for matching
    regexes = { '+': [], '-': [] }
    for spec in input:
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


def get_lookup_specs(input):
    """ Get data lookup specifications and convert to regular expressions. """

    # Convert specifications to regexes for matching
    regexes = { '+': [], '-': [] }
    for spec in input:
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
    
    return regexes


def determine_dir(input, default, basedir, tpl):
    """ Determines directory and makes it an absolute path. """

    result = input if input else default
    result = result.format(**tpl)
    if not isabs(result):
        result = join(basedir, result)
    return result


# =====

def check(config:ns.Namespace):
    """Check validity of values in the parsed configuration."""

    svr = ns.check_section(config, "Server")
    ns.check_notempty(svr, 'host')
    ns.check_notempty(svr, 'port')
    ns.check_notempty(svr, 'namespace')
    ns.check_notempty(svr, 'user')
    ns.check_notempty(svr, 'password')
    ns.check_default(svr, 'https', False)
    ns.check_default(svr, 'threads', 1)
    if not isinstance(svr.threads, int):
        raise ConfigurationError("Setting 'threads' must be an integral number")
    if not 1 <= svr.threads <= 20:
        raise ConfigurationError("Setting 'threads' must be between 1 and 20")

    project = ns.check_section(config, "Project")
    ns.check_default(project, 'mapped', False)
    ns.check_default(project, 'generated', False)
    ns.check_default(project, 'items', [])
    ns.check_default(project, 'lookup', [])

    ens = ns.get_section(project, 'enssettings', create=True)
    assert ens is not None # silence mypy
    ns.check_default(ens, 'name', '')
    ns.check_default(ens, 'strip', True)

    local = ns.check_section(config, "Local")
    ns.check_default(local, 'dir', '')
    ns.check_default(local, 'cspdir', '')
    ns.check_default(local, 'datadir', '')
    ns.check_default(local, 'logdir', '')
    ns.check_default(local, 'subdirs', False)
    ns.check_default(local, 'cookies', False)
    ns.check_encoding(local, 'encoding', 'UTF-8')
    
    # Output compatibility setting
    ns.check_oneof(local, 'compatibility', ('vscode', 'export'), 'export')
    
    # Warn about now unused settings
    if 'disable_eol_fix' in local or 'disable_class_eol_fix' in local:
        msg = "..._eol_fix settings are no longer supported. Use 'compatibility'" \
            " setting instead. Value: false -> 'export', true -> 'vscode'."
        raise ConfigurationError(msg)
    


# =====

def setup_basic_logging(cfgfile:str):
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


def setup_logging(config:ns.Namespace):
    """ Final logging setup: allow log location override in config """

    # If no logdir specified, setup is already complete
    logdir = config.Local._get('logdir')
    if not logdir:
        return

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
    logger.handlers.append(logging.FileHandler(name, 'a', 'UTF-8'))
    logger.setLevel(logging.INFO)


def merge_augmented_settings(config:ns.Namespace):
    """ Merges settings from file in setting augment_from, if any """
    
    local = ns.get_section(config, 'Local')
    if local is None:
        return
    fname = local._get('augment_from')
    if fname == '' or fname is None:
        return
    if not isabs(fname):
        fname = join(config.cfgdir, fname)
    if not exists(fname) or not isfile(fname):
        raise ConfigurationError(f"augment_from file {local._get('augment_from')} not found")
    cs = ns.dict2ns(toml.load(fname))
    # Add/override each key/value in augment_from
    for k, v in cs._flattened():
        ns.set_in_path(config, k, v)


def unhandled_exception(exc_type, exc_value, exc_traceback):
    """ Handle otherwise unhandled exceptions by logging them """

    if exc_type == ConfigurationError:
        msg = exc_value.args[0]
        logging.error("\n%s", msg)
    else:
        msg = f"An error occurred; please see the log file for details.\n\n{exc_value}"
        exc_info = (exc_type, exc_value, exc_traceback)
        logging.exception("\n##### Unhandled exception:", exc_info=exc_info)
    msgbox(f"An error occurred; please see the log file for details.\n\n{exc_value}", True)
    sys.exit(1)


# =====

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

# =====

# Command line overrides for values in the configuration file
ARGS:List[dict] = [
]

def parse_args():
    """Parse command line arguments."""

    parser = argparse.ArgumentParser()
    parser.add_argument("config",
       help="The (TOML) configuration file to use")
    parser.add_argument("--no-gui", action='store_true',
       help="Do not display a message box on completion.")
    
    # Add command line overrides
    for arg in ARGS:
        kwargs = arg['argparse']
        names = kwargs.pop('names')
        parser.add_argument(*names, **kwargs)

    # Replace stdout/stderr to capture argparse output
    sys.stdout = StringIO()
    sys.stderr = StringIO()
    
    # Check command line
    try:
        args = parser.parse_args()

    except SystemExit:
        # Get argparse output; either an error message in stderr, or
        # a usage message in stdout.
        msg, err = sys.stderr.getvalue(), True
        if not msg:
            msg = sys.stdout.getvalue()
            err = False
        
        # Show error or usage and exit
        msgbox(msg, err)
        raise

    finally:
        # Restore stdout/stderr
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__
    
    cfgfile = args.config
    if not isabs(cfgfile) and not exists(cfgfile):
        cfgfile = join(dirname(__file__), cfgfile)
    
    if not exists(cfgfile) or not isfile(cfgfile):
        msgbox(f"Error: file {cfgfile} not found.\n\n{parser.format_help()}", True)
        sys.exit(1)
    
    if not isabs(cfgfile):
        cfgfile = abspath(cfgfile)
    
    args.config = cfgfile

    return args


def merge_overrides(args:argparse.Namespace, config:ns.Namespace):
    """Merge command line overrides into configuration"""
    
    config.no_gui = args.no_gui
    for arg in ARGS:
        value = getattr(args, cast(str, arg['name']))
        if not value:
            continue
        ns.set_in_path(config, cast(str, arg['path']), value)
        

