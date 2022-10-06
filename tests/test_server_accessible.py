from importlib import import_module
from typing import Any

import toml
import pytest

from namespace import ConfigurationError

copier = import_module("copy-iris-items") # type: Any


CFG = """
[Local]
dir = '{dir}/src'
logdir = '{dir}'
[Project]
items = ['Strix.Std.*.cls']
"""


@pytest.mark.usefixtures("reload_modules")
def test_404(tmp_path, server_toml, get_files):
    """Test error for non-existent namespace"""
    
    svr_dict = toml.loads(server_toml)
    svr_dict['Server']['namespace'] += '_____'
    svr = toml.dumps(svr_dict)
    
    cfg = f"{CFG.format(dir=tmp_path)}\n{svr}"
    with pytest.raises(ConfigurationError) as e:
        get_files(cfg, tmp_path)
    msg:str = e.value.args[0]
    assert ' 404 ' in msg, f'Unexpected error message: "{msg}"'
    

def test_401(tmp_path, server_toml, get_files):
    """Test error for invalid user"""
    
    svr_dict = toml.loads(server_toml)
    svr_dict['Server']['user'] = "i don't exist"
    svr = toml.dumps(svr_dict)
    
    cfg = f"{CFG.format(dir=tmp_path)}\n{svr}"
    with pytest.raises(ConfigurationError) as e:
        get_files(cfg, tmp_path)
    msg:str = e.value.args[0]
    assert ' 401 ' in msg, f'Unexpected error message: "{msg}"'

