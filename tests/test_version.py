"""Package versioning tests."""

from importlib.metadata import version
from importlib.util import module_from_spec, spec_from_file_location

import ska_dlm

PACKAGE_VER = version("ska-data-lifecycle")


def test_module_version():
    """Test module __version__ matches package version."""
    assert ska_dlm.__version__ == PACKAGE_VER


def test_doc_version():
    """Test sphinx config version matches package version."""
    spec = spec_from_file_location("conf", "docs/src/conf.py")
    assert spec
    assert spec.loader
    conf = module_from_spec(spec)
    assert conf
    spec.loader.exec_module(conf)
    assert conf.version == PACKAGE_VER
    assert conf.release == PACKAGE_VER


def test_cicd_version():
    """Test CICD version matches package version."""
    with open(".release", encoding="utf-8") as f:
        lines = f.readlines()
        assert f"release={PACKAGE_VER}\n" in lines
        assert f"tag={PACKAGE_VER}\n" in lines
