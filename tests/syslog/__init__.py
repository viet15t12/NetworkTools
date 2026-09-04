import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import main as _main_bootstrap  # noqa: F401,E402 - configures application/PyQt paths
