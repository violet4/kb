"""kb's ORM: one SQLite database at schema_version.DB_PATH (data/kb.db).

Import each model from the module that defines it (`from models.work.todo import Todo`). This
package re-exports nothing; importing it imports every module, so every table is registered on
Base.metadata and every flush listener is attached.
"""

import importlib
import inspect
import pkgutil
from types import ModuleType

MODULES: list[ModuleType] = [
    importlib.import_module(info.name) for info in pkgutil.walk_packages(__path__, prefix=f"{__name__}.")
]


def defined_names() -> dict[str, object]:
    """Every public class, function, and module-level object defined (not imported) in a
    models module, by name."""
    return {
        name: obj
        for module in MODULES
        for name, obj in vars(module).items()
        if not name.startswith("_") and inspect.getmodule(obj) is module
    }
