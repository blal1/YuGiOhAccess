import os

import cyal

binaries = []
# add cyal to the list of binaries
# go through the list of binaries in cyal
for file in os.listdir(os.path.dirname(cyal.__file__)):
    # check if the file is a binary
    if file.endswith('.dll') or file.endswith('.pyd') or file.endswith('.so') or file.endswith('.dylib') or ".so" in file:
        binaries.append((os.path.join(os.path.dirname(cyal.__file__), file), "cyal"))

datas = [
    ('../src/data', 'data')
    ]

hiddenimports = ["cyal", "cyal.listener"]
hookspath = ["specs/"]