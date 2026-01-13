# Copyright (C) 2026 swanserquack
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
# 
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
import pkgutil
import importlib
import inspect
from .base_provider import BaseProvider

# This dictionary will hold the map: 'keio_university' -> KeioProvider class
PROVIDER_REGISTRY = {}

def _register_providers() -> None:
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
def get_provider_class(uni_code: str) -> type[BaseProvider] | None:
    return PROVIDER_REGISTRY.get(uni_code)