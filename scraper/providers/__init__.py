import pkgutil
import importlib
import inspect
from .base_provider import BaseProvider

# This dictionary will hold the map: 'keio_university' -> KeioProvider class
PROVIDER_REGISTRY = {}

def _register_providers():
    """
    Scans the current directory for modules, imports them,
    and looks for classes that inherit from BaseProvider.
    """
    # Look at the current folder (where this __init__.py is)
    package_path = __path__
    prefix = __name__ + "."

    # Iterate over all files in this folder
    for _, name, _ in pkgutil.walk_packages(package_path, prefix):
        try:
            # Dynamically import the module (e.g., scraper.providers.Japan.KeioProvider)
            module = importlib.import_module(name)

            # Scan the module for classes
            for attribute_name, attribute_value in inspect.getmembers(module):
                # Check if it is a class, inherits from BaseProvider, and is not BaseProvider itself
                if (inspect.isclass(attribute_value) and issubclass(attribute_value, BaseProvider) and attribute_value is not BaseProvider):
                    code = attribute_value.university_name
                    if code:
                        PROVIDER_REGISTRY[code] = attribute_value
                        
        except Exception as e:
            print(f"Could not load provider from {name}: {e}")

# As soon as we import the providers module, being registering the providers
_register_providers()

# For use in GUI/user interface later
def get_provider_class(uni_code: str):
    return PROVIDER_REGISTRY.get(uni_code)