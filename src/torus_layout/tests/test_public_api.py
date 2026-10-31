import ast
import importlib
import inspect
from pathlib import Path
import typing
import pytest

PACKAGE = Path(__file__).resolve().parents[1]
SOURCES = [p for p in PACKAGE.rglob("*.py") if "tests" not in p.parts]


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: str(p.relative_to(PACKAGE)))
def test_modules_have_resolvable_runtime_annotations(path):
    relative = path.relative_to(PACKAGE).with_suffix("")
    parts = relative.parts[:-1] if relative.name == "__init__" else relative.parts
    name = ".".join(("torus_layout", *parts))
    module = importlib.import_module(name)
    for value in vars(module).values():
        if inspect.isfunction(value) and value.__module__ == name:
            hints = typing.get_type_hints(value)
            assert "return" in hints, value.__name__
            for parameter in inspect.signature(value).parameters:
                assert parameter in hints, (value.__name__, parameter)
    for exported in getattr(module, "__all__", []):
        assert hasattr(module, exported)


def test_runtime_modules_do_not_import_old_implementations():
    for path in SOURCES:
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and not node.level:
                assert node.module.split(".")[0] not in {
                    "main",
                    "lib",
                    "layer_assignment",
                    "crossing_reduction",
                    "coordinate_assignment",
                    "drawing",
                }


def test_protected_files_are_unchanged():
    from torus_layout.checks.check_legacy_files import check_legacy_files

    check_legacy_files()
