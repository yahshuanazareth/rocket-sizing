# PyInstaller build recipe: turns the tool into a double-click app that
# carries its own Python and libraries, so users install nothing.
#
# Build on the system you're building for (Mac on a Mac, Windows on Windows):
#     pyinstaller rocket_sizing.spec
# The result appears in dist/.

import sys
from PyInstaller.utils.hooks import (collect_all, collect_data_files,
                                     collect_dynamic_libs, copy_metadata)

NAME = "Rocket Engine Sizing Tool"

# Program files the Streamlit server reads at run time
datas = [("app.py", "."), ("engine.py", "."),
         (".streamlit/config.toml", ".streamlit")]
binaries = []
hiddenimports = ["engine", "rocketcea.cea_obj", "rocketcea.py_cea",
                 "matplotlib.backends.backend_agg", "matplotlib.pyplot",
                 "matplotlib.patches", "pandas", "numpy"]

# Streamlit ships its web interface as data files and reads its own version
# from package metadata, so collect everything it has.
d, b, h = collect_all("streamlit")
datas += d; binaries += b; hiddenimports += h
datas += copy_metadata("streamlit")

# NASA CEA: the compiled Fortran module and its thermo/transport data files
# (rocketcea also reads its own _version.py from disk, so include .py files)
datas += collect_data_files("rocketcea", include_py_files=True,
                            excludes=["tests/*", "examples/*", "biprop_utils/*"])
binaries += collect_dynamic_libs("rocketcea")

# The desktop window
d, b, h = collect_all("webview")
datas += d; binaries += b; hiddenimports += h

# Windows: the window uses Edge WebView2 through pythonnet (.NET)
if sys.platform == "win32":
    for pkg in ("pythonnet", "clr_loader"):
        d, b, h = collect_all(pkg)
        datas += d; binaries += b; hiddenimports += h

a = Analysis(
    ["desktop.py"],
    datas=datas,
    binaries=binaries,
    hiddenimports=hiddenimports,
    # Not used by this tool; leaving them out keeps the download smaller.
    # (SciPy is only used by an optional rocketcea module the tool never loads.)
    excludes=["scipy", "tkinter", "PyQt5", "PyQt6", "PySide2", "PySide6",
              "gi", "IPython", "jupyter", "notebook", "pytest",
              "rocketcea.biprop_utils", "rocketcea.examples", "rocketcea.tests"],
)
pyz = PYZ(a.pure)

icon = "Rocket Engine Sizing Tool.app/Contents/Resources/AppIcon.icns" \
    if sys.platform == "darwin" else "packaging/AppIcon.ico"

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name=NAME,
    console=False,          # no Terminal / command window
    icon=icon,
)
coll = COLLECT(exe, a.binaries, a.datas, name=NAME)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name=f"{NAME}.app",
        icon=icon,
        bundle_identifier="com.yahshuanazareth.rocketsizing",
        info_plist={
            "CFBundleDisplayName": NAME,
            "CFBundleShortVersionString": "1.0",
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "12.0",
        },
    )
