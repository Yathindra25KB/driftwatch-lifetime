"""DriftWatch: time-aware study of malware-detector lifetime (pre-release).

Package map follows build guide section 8. Every subpackage is empty until the
phase named in its docstring fills it.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("driftwatch-lifetime")
except PackageNotFoundError:  # running from a source tree without installation
    __version__ = "0.0.0"

__all__ = ["__version__"]
