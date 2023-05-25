# HoudiniPythonStubsGenerator

Python generator for Houdini Python module stubs

The stubs can be generated with hython :
```bat
/path/to/hython main.py
```

You can also, if you want to have all the modules available in the ui, generate the stubs from a houdini session using the Python shell :
```py
import sys
import hou

sys.path.append("/path/to/HoudiniPythonStubsGenerator")

import main
main.generate_stubs(hou)
```

You can also use the `gen.bat` script but the python major and minor version must match with the python shipped with Houdini.
```bat
.\gen.bat /path/to/houdini/dir/Houdini 19.5.435
```

Then you can use in your favorite editor by making the autocomplete path pointing to the `/stubs` directory.