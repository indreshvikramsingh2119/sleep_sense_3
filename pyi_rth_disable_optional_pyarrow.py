"""Keep the frozen app independent of a host machine's PyArrow install.

SleepSense does not use Arrow/Parquet.  Pandas treats PyArrow as optional and
works normally when importing it raises ImportError.  Some Windows machines
can expose a partial ``pyarrow`` namespace (for example via PYTHONPATH); that
module has no ``__version__`` and makes Pandas fail during startup instead.
Marking the optional package unavailable gives Pandas the supported fallback.
"""

import sys


sys.modules["pyarrow"] = None
