"""
Tests the [Local] augment_from setting.
"""

from os.path import isdir, isfile
import pytest

import namespace as ns


# Base configuration for tests below
CFG = """
[Project]
items = ['Test.cls']
[Local]
dir = 'src'
logdir = 'log'
augment_from = 'ovr.toml'
"""

# Overrides to merge-in
OVR = """
[Local]
dir = 'src2'
logdir = 'log2'
"""

# Server config section to place in either of the above fragments
SVR = """
[Server]
host='localhost'
port='52773'
namespace='USER'
user='_SYSTEM'
password='SYS'
"""


@pytest.mark.usefixtures("reload_modules")
def test_change_dirs(tmp_path, get_config_ns):
    """ Tests overriding directory settings using augment_from setting """
    
    # Write override toml
    ovr = tmp_path / 'ovr.toml'
    with open(ovr, 'wt') as f:
        f.write(OVR)
    
    # Get the parsed and augmented configuration settings
    cfg = get_config_ns(CFG+SVR, tmp_path)
    
    assert cfg.Local.dir == 'src2', "Override not applied to Local.dir"
    assert cfg.Local.logdir == 'log2', "Override not applied to Local.logdir"
    assert isdir(tmp_path / 'log2'), "Logdir not actually changed"
    assert isfile(tmp_path / 'log2' / 'cfg.log'), "Logfile not at overridden location"
    

@pytest.mark.usefixtures("reload_modules")
def test_add_required_section(tmp_path, get_config_ns):
    """ Tests adding a required section via augment_from """
    
    # Write override toml
    ovr = tmp_path / 'ovr.toml'
    with open(ovr, 'wt') as f:
        f.write(OVR+SVR)
    
    # If the server section is not merged-in, a configuration error will occur
    try:
        # Get the parsed and augmented configuration settings
        get_config_ns(CFG, tmp_path)
    except ns.ConfigurationError:
        pytest.fail("Server section not merged from augment_from file")
    
