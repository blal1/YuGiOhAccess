# Bundled EDOPro Engine

Place the platform-specific `ocgcore` shared library here so the local/offline
server can use the real EDOPro rules engine without manual configuration.

Expected filenames:

- Windows: `ocgcore.dll`
- macOS: `libocgcore.dylib`
- Linux: `libocgcore.so`

Build helper:

```powershell
.\.venv\Scripts\python.exe scripts\build_ocgcore.py
```

The helper builds ProjectIgnis/EDOPro-core and copies the resulting library into
this directory. The current upstream core uses Meson/Ninja and requires Lua 5.4
development files plus a C++17 compiler.

Official ProjectIgnis Windows release archives currently ship a 32-bit
`ocgcore.dll`. A 64-bit Python process cannot load that DLL; use a matching
32-bit Python runtime or build a matching 64-bit `ocgcore.dll` with the helper.

Card databases are loaded from `src/data/databases/*.cdb`. Card scripts are
loaded from `src/data/scripts` when that directory exists.
