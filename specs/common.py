import os

import cyal

SPEC_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SPEC_DIR)
DATA_ROOT = os.path.join(ROOT, "src", "data")

binaries = []
# add cyal to the list of binaries
# go through the list of binaries in cyal
for file in os.listdir(os.path.dirname(cyal.__file__)):
    # check if the file is a binary
    if file.endswith('.dll') or file.endswith('.pyd') or file.endswith('.so') or file.endswith('.dylib') or ".so" in file:
        binaries.append((os.path.join(os.path.dirname(cyal.__file__), file), "cyal"))


# Whole trees that are runtime assets and ship as they stand: the sounds, the
# card scripts ocgcore runs, the engine itself, the card string tables and the
# public decks.
BUNDLED_DATA_DIRS = ("sounds", "scripts", "core", "locales", "decks")

# Trees that hold a mix of runtime assets and build leftovers, and so are
# walked file by file.
FILTERED_DATA_DIRS = ("databases", "bot")

# Directories anywhere under src/data that are working files rather than
# things the application reads.
#
# bot-publish-test is a copy of the bot's published output kept for manual
# checking; nothing in the code refers to it, and it was adding 34 MB to every
# build. BabelCDB-master and babelcdb.zip are the downloaded card database
# archive and its extraction, which the app re-downloads into its own data
# directory at startup anyway.
EXCLUDED_DATA_DIRS = {"bot-publish-test", "BabelCDB-master", "ci", "__pycache__"}

EXCLUDED_DATA_NAMES = {"babelcdb.zip", "crash.log", "README.md"}

# Debug symbols. Useful next to a local build, pointless inside an installer.
EXCLUDED_DATA_SUFFIXES = (".pdb", ".pyc")


def _should_bundle(name, is_dir):
    if is_dir:
        return name not in EXCLUDED_DATA_DIRS
    if name in EXCLUDED_DATA_NAMES:
        return False
    return not name.endswith(EXCLUDED_DATA_SUFFIXES)


def _filtered_tree(relative_dir):
    """Every file under one src/data subdirectory that is worth shipping."""
    found = []
    source_root = os.path.join(DATA_ROOT, relative_dir)
    for current, directories, files in os.walk(source_root):
        directories[:] = [name for name in directories if _should_bundle(name, True)]
        for name in files:
            if not _should_bundle(name, False):
                continue
            source = os.path.join(current, name)
            inside = os.path.relpath(current, DATA_ROOT).replace(os.sep, "/")
            found.append((source, f"data/{inside}"))
    return found


datas = []
for _name in BUNDLED_DATA_DIRS:
    _path = os.path.join(DATA_ROOT, _name)
    if os.path.isdir(_path):
        datas.append((_path, f"data/{_name}"))
for _name in FILTERED_DATA_DIRS:
    datas.extend(_filtered_tree(_name))

# The compiled UI translations. Without this the catalogues never reached a
# packaged build, so every release was English only no matter how much had
# been translated. core.i18n looks for them here when frozen.
datas.append((os.path.join(ROOT, "locales"), "locales"))

hiddenimports = ["cyal", "cyal.listener"]
hookspath = ["specs/"]
