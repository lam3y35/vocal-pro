"""Compatibility loader — import split omnibus test modules for discovery.

This file intentionally minimal: keep for old CI/scripts that expect tests/omnibus/test_all.py
but real tests are split into topic files under tests/omnibus/.
"""

from . import (
    test_config,
    test_utils,
    test_audio_postprocess,
    test_separation_engine,
    test_bulk,
)

# Nothing else here — pytest will collect the imported modules' tests.
