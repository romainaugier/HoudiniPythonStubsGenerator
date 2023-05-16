# Generate stubs for hou.py with the correct type annotation

import inspect
import os
import importlib
import sys
import optparse
import io
import re

from typing import List

class TypePattern():

    __slots__ = (
        "pattern",
        "replace",
        "hash"
    )    
    
    def __init__(self, type_pattern: str, replace: str):
        self.pattern = re.compile(type_pattern)
        self.replace = replace
        self.hash = hash((type_pattern + replace).encode("utf-8"))
        
    def sub(self, string: str) -> str:
        return self.pattern.sub(self.replace, string)

    def __hash__(self) -> int:
        return self.hash

TYPES_PATTERN_DECL = {
    TypePattern(r"char const \*",  "str"),
    TypePattern("int64",  "int"),
    TypePattern(r"std\:\:string const \&", "str"),
    TypePattern(r"std\:\:string", "str"),
    TypePattern("void", "None"),
    TypePattern(r"std\:\:vector< (HOM_|UT_)?([A-Za-z0-9_]+),.*", r"typing.List[\g<2>]"),
    TypePattern(r"UT_SharedPtr< (HOM_|UT_)?([a-zA-Z0-9_]+) >", r"\g<2>"),
    TypePattern(r"HOM_([A-Za-z]+) ?\*?", r"\g<1>"),
    TypePattern(r"UT_([a-zA-Z]+) ?\*?", r"\g<1>")
}

def fix_types(string: str) -> str:
    for pattern in TYPES_PATTERN_DECL:
        _string = pattern.sub(string)

        _string = _string.replace("HOM_", "")

        if _string != string:
            return _string

    return string

RE_CLEAN_PATTERN = re.compile("\(|\)|'")

RE_ENUM_VALUE_PATTERN = re.compile("^ {8}[a-zA-Z\.0-9]*$")

def get_enumeration(doc: str,
                    class_name: str) -> List[str]:
    values = list()

    try:
        enum_str = doc.split("VALUES")[1]

        if "RELATED" in enum_str:
            enum_str = doc.split("RELATED")[0]
        
        for line in enum_str.splitlines():
            if RE_ENUM_VALUE_PATTERN.search(line) is not None:
                line_clean = line.strip().replace("hou.", "").replace(f"{class_name}.", "")
                values.append(line_clean)

    except IndexError as err:
        print("Cannot split doc")
        print(doc)

    return values

if __name__ == "__main__":
    print("Generating stubs for HOM")
    
    parser = optparse.OptionParser()
    parser.add_option("--path-to-hou",
                      dest="hou_path",
                      default=None,
                      help="Path to hou.py file")
    
    options, args = parser.parse_args()
    hou_path = options.hou_path
    
    if hou_path is None:
        sys.exit(1)

    if not os.path.exists(hou_path):
        sys.exit(1)

    hou_name, _ = os.path.splitext(os.path.basename(hou_path))
    hou_dir = os.path.dirname(hou_path)

    sys.path.append(hou_dir)

    module = importlib.import_module(hou_name)

    classes = inspect.getmembers(module, inspect.isclass)
    functions = inspect.getmembers(module, inspect.isfunction)

    output = io.StringIO()
    output.write("# Houdini stubs\n")
    output.write("from __future__ import annotations\n")
    output.write("\n")
    output.write("import typing\n")
    output.write("\n")
    output.write("\n")

    classes = sorted(classes, key=lambda c: inspect.getsourcelines(c[1])[1])

    for _class in classes:
        class_name = _class[0]
        _class = _class[1]

        if class_name.startswith("_"):
            continue

        class_mro = inspect.getmro(_class)

        class_parent = class_mro[1].__name__.replace("hou.", "") if len(class_mro) > 1 else "object"
        class_sig = inspect.signature(_class)

        # return_annotation = fix_types(class_sig.return_annotation)

        parms = list()

        for parm in class_sig.parameters.values():
            parm_str = RE_CLEAN_PATTERN.sub("", str(parm))

            parms.append(fix_types(parm_str))

        parms_str = ", ".join(parms)

        class_doc = _class.__doc__
        
        if class_doc is None:
            class_doc = "    No documentation available"
        else:
            class_doc = class_doc.replace("\\t", "    ")

        output.write(f"class {class_name}({class_parent}):\n")
        output.write("    \"\"\"")
        output.write(class_doc) 
        output.write("\"\"\"\n")
        output.write("\n")

        if "Enum" in class_doc:
            enum = get_enumeration(class_doc, class_name)

            for i, val in enumerate(enum):
                output.write(f"    {val} = {i}\n")

        output.write("\n")
        
        output.write(f"    def __init__(self, {parms_str}):\n")
        output.write(f"        pass\n")
        output.write("\n")

        # class_methods = inspect.getmembers(_class, inspect.isfunction)

    with open("hou_stubs.py", "w") as file:
        file.write(output.getvalue())

    sys.exit(0)
