"""
Runtime hook: fix pythonnet Python.Runtime.dll path when frozen by PyInstaller.
"""
import sys
import os

if getattr(sys, 'frozen', False):
    # Patch pythonnet to find Python.Runtime.dll inside the bundle
    import pythonnet as _pn
    from pathlib import Path
    _pn_file = Path(sys._MEIPASS) / 'pythonnet' / '__init__.py'
    # Override the module __file__ so the dll_path resolves correctly
    _pn.__file__ = str(_pn_file)
