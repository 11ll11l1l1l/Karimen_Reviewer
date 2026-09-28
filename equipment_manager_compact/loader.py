from __future__ import annotations

import importlib.abc
import importlib.util
import sys

from bundle_core import MODULES as CORE
from bundle_ui import MODULES as UI
from bundle_workflows_a import MODULES as WORKFLOWS_A
from bundle_workflows_b import MODULES as WORKFLOWS_B
from bundle_admin import MODULES as ADMIN
from bundle_io import MODULES as IO
from bundle_integrations import MODULES as INTEGRATIONS
from bundle_demo_cli import MODULES as DEMO_CLI

MODULES: dict[str, str] = {}
for _group in (CORE, UI, WORKFLOWS_A, WORKFLOWS_B, ADMIN, IO, INTEGRATIONS, DEMO_CLI):
    MODULES.update(_group)


class _EMSBundleImporter(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def find_spec(self, fullname, path=None, target=None):
        if fullname in MODULES:
            return importlib.util.spec_from_loader(fullname, self, origin=f"<ems-bundle:{fullname}>")
        return None

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        name = module.__name__
        source = MODULES[name]
        module.__file__ = f"<ems-bundle:{name}>"
        module.__package__ = ""
        exec(compile(source, module.__file__, "exec"), module.__dict__)


_IMPORTER = _EMSBundleImporter()


def install() -> None:
    if not any(isinstance(item, _EMSBundleImporter) for item in sys.meta_path):
        sys.meta_path.insert(0, _IMPORTER)


def bundled_module_names() -> tuple[str, ...]:
    return tuple(sorted(MODULES))
