
import sys, os
from os.path import exists, isfile, abspath, isabs, dirname, basename, splitext, join
import re
from types import SimpleNamespace
import http.cookiejar
import json

import toml


def get_config(cfgfile):
    # Create namespace for configuration data
    config = Namespace()

    # Get parsed config data
    config.input = dict2ns(toml.load(cfgfile))

    # Create regexes where needed
    config.itemsrx, config.types = get_specs(config.input.Project.items)
    config.lookuprx = get_lookup_specs(config.input.Project.lookup)

    # Determine various directories
    local = config.input.Local
    basedir = abspath(dirname(cfgfile))
    cfgname = splitext(basename(cfgfile))[0]
    tpl = { 'cfgname': cfgname }
    for name, default in ("dir", "src"), ("cspdir", "csp"), ("datadir", "data"):
        default = join(cfgname, default)
        config.__dict__[name] = determine_dir(local[name], default, basedir, tpl)
    
    # Create cookie jar for session persistence
    svr = config.input.Server
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


# ===== Helpers

class Namespace(SimpleNamespace):
    """Namespace that also supports mapping access."""

    def __getitem__(self, name):
        return self.__dict__[name]

def dict2ns(input:dict) -> Namespace:
    """Converts a dict to a namespace for attribute access."""

    ns = Namespace()
    for k, v in input.items():
        if isinstance(v, dict):
            ns.__dict__[k] = dict2ns(v)
        else:
            ns.__dict__[k] = v
    return ns

def ns2dict(input:Namespace) -> dict:
    """Converts a Namespace to a dict."""

    d = {}
    for k, v in input.__dict__.items():
        if isinstance(v, Namespace):
            d[k] = ns2dict(v)
        else:
            d[k] = v
    return d


# =====

def main(cfgfile):
    config = get_config(cfgfile)
    print(json.dumps(ns2dict(config), indent=2, default=str))


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <configfile>")
        sys.exit(1)

    cfgfile = sys.argv[1]
    if not exists(cfgfile) or not isfile(cfgfile):
        print(f"File {cfgfile} not found.\nUsage: {sys.argv[0]} <configfile>")
        sys.exit(1)
    
    main(cfgfile)
