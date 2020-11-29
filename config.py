
import sys, os
from os.path import exists, isfile, abspath, isabs, dirname, basename, splitext, join
import re
import http.cookiejar
import json

import toml

import namespace as ns
from namespace import ConfigurationError


def get_config(cfgfile):
    # Get parsed config data
    config = ns.dict2ns(toml.load(cfgfile))
    config.cfgfile = cfgfile
    config.cfgdir = dirname(cfgfile)
    config.cfgname = splitext(basename(cfgfile))[0]

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
    config.cookiejar = http.cookiejar.LWPCookieJar(cookiefile, delayload=False)

    # File encoding defaults to UTF-8
    config.encoding = local.encoding if local.encoding else 'UTF-8'

    return config


def get_specs(input):
    """ Get project specifications and convert to regular expressions. """

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


def get_lookup_specs(input):
    """ Get data lookup specifications and convert to regular expressions. """

    specs = [ spec for spec in input ]
    
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

    project = ns.check_section(config, "Project")
    ns.check_default(project, 'mapped', False)
    ns.check_default(project, 'generated', False)
    ns.check_default(project, 'items', [])
    ns.check_default(project, 'lookup', [])

    ens = ns.get_section(project, 'enssettings')
    if ens:
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


# =====

def main(cfgfile):
    config = get_config(cfgfile)
    print(json.dumps(ns.ns2dict(config), indent=2, default=str))

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <configfile>")
        sys.exit(1)

    cfgfile = sys.argv[1]
    if not exists(cfgfile) or not isfile(cfgfile):
        print(f"File {cfgfile} not found.\nUsage: {sys.argv[0]} <configfile>")
        sys.exit(1)
    
    main(cfgfile)
