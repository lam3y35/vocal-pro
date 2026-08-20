"""Compatibility loader — import split omnibus test modules for discovery.

Kept for old CI/scripts that expect tests/omnibus/test_all.py
but real tests are split into topic files under tests/omnibus/.
"""

from tests.omnibus import (  # noqa: F401
    test_config,
    test_utils,
    test_audio_postprocess,
    test_separation_engine,
    test_bulk,
)

# Nothing else here — pytest will collect the imported modules' tests.
