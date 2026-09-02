"""Build the optional accelerated device-sync engine in place.

Install the ``speed`` extra before running this file.  The generated extension
has the same import name as the Python engine, so callers require no branching;
when it is absent Python automatically uses ``_engine.py``.
"""

from __future__ import annotations

from Cython.Build import cythonize
from setuptools import Extension, setup


setup(
    name="cams-sync-accelerator",
    packages=[],
    py_modules=[],
    ext_modules=cythonize(
        [
            Extension(
                "features.devices.sync._engine",
                ["features/devices/sync/_engine.py"],
            )
        ],
        compiler_directives={
            "language_level": "3",
            # Type hints document the Python API; they must not narrow runtime
            # inputs (for example sqlite accepts both str and pathlib.Path).
            "annotation_typing": False,
            # The parser intentionally uses Python-style negative indices in a
            # few places, so keep these safety semantics enabled.
            "boundscheck": True,
            "wraparound": True,
            "initializedcheck": False,
            "nonecheck": False,
        },
        annotate=False,
        force=True,
    ),
    zip_safe=False,
)
