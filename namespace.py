
from types import SimpleNamespace


class Namespace(SimpleNamespace):
    """Namespace that also supports mapping access."""

    def __getitem__(self, name):
        """ Adds support for value = ns['key'] """
        return self.__dict__[name]
    
    def __setitem__(self, key, value):
        """ Adds support for ns['key'] = value """
        self.__dict__[key] = value

    def __getattribute__(self, name):
        """ Adds support for local attributes """
        try:
            return object.__getattribute__(self, name)
        except AttributeError:
            return self.__dict__[name]
    
    def _get(self, key, default=None):
        """ Retrieves a value, or default if not found """
        return self.__dict__.get(key, default)


def dict2ns(input:dict) -> Namespace:
    """Converts a dict to a namespace for attribute access."""

    ns = Namespace()
    for k, v in input.items():
        if isinstance(v, dict):
            ns[k] = dict2ns(v)
        else:
            ns[k] = v
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

