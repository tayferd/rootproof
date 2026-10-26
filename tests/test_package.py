"""Verify the initial package can be imported from the repository."""

from importlib import import_module


def test_application_package_imports() -> None:
    import_module("app")
