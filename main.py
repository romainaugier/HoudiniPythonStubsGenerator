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

TYPES_PATTERN_DECL = [
    TypePattern(r"(HOM_)?IterableList< (HOM_IterableList|std::vector)< (HOM_ElemPtr< |HOM_|UT_)?([A-Za-z0-9_]+)( >)?( \*)?.*", r"typing.List[typing.List[\g<4>]]"),
    TypePattern(r"std::vector< std::map< .+ >", r"typing.List[typing.Dict]"),
    TypePattern(r"std::map< .+ >", r"typing.Dict"),
    TypePattern(r"std::vector< std::pair< .+ >", r"typing.List[typing.Any]"),
    TypePattern(r"std::vector< std::vector< (HOM_ElemPtr< |HOM_|UT_)?([A-Za-z0-9_:]+)( >)?( \*)?,.*", r"typing.List[typing.List[\g<2>]]"),
    TypePattern(r"std::vector< UT_Tuple.*", "typing.List[typing.Tuple]"),
    TypePattern(r"std::vector< (HOM_ElemPtr< |HOM_|UT_)?([A-Za-z0-9_:]+)( >)?( \*)?,.*", r"typing.List[\g<2>]"),
    TypePattern(r"(HOM_)?IterableList< (HOM_ElemPtr< |HOM_|UT_)?([A-Za-z0-9_]+)( >)?( \*)?", r"typing.List[\g<3>]"),
    TypePattern(r"UT_SharedPtr< (HOM_|UT_)?([a-zA-Z0-9_]+) >", r"\g<2>"),
    TypePattern(r"HOM_PtrOrNull< (HOM_|UT_)?([a-zA-Z0-9_]+) ?>", r"\g<2>"),
    TypePattern(r"std::pair< (HOM_|UT_)?([a-zA-Z0-9_]+),.*", r"typing.Tuple[\g<2>, \g<2>]"),
    TypePattern(r"std::pair< (HOM_ElemPtr< |UT_|HOM_)?([a-zA-Z0-9_]+)( >)?,(HOM_ElemPtr< |UT_|HOM_)?([a-zA-Z0-9_]+)( >)?.*", r"typing.Tuple[\g<2>, \g<5>]"),
    TypePattern(r"(HOM|UT)?_Tuple< (HOM_|UT_|HOM_ElemPtr< )?([A-Za-z0-9_,]+.*)", r"typing.Tuple"),
    TypePattern(r"(HOM|UT)?_Tuple< ([A-Za-z0-9_,]+) >", r"typing.Tuple[\g<2>]"),
    TypePattern(r"(HOM|UT)?_([A-Za-z0-9]+)Tuple( \*)?", r"typing.Tuple[\g<2>]"),
    TypePattern(r"(HOM|UT)_([A-Za-z0-9_]+)::[A-Za-z0-9_]+", r"typing.Dict"),
    TypePattern(r"(HOM|UT)_([A-Za-z0-9_]+)( \*| \&)?", r"\g<2>"),
    TypePattern(r"char const \*", "str"),
    TypePattern(r"int(64)?( &)?", "int"),
    TypePattern(r"std\:\:string const \&", "str"),
    TypePattern(r"std\:\:string", "str"),
    TypePattern(r"void( \*)?", "None"),
    TypePattern("double", "float"),
    TypePattern("ptrdiff_t", "int"),
    TypePattern("size_t", "int"),
    TypePattern(r"swig::SwigPyIterator( \*| \&)?", "SwigPyIterator"),
    TypePattern(r"InterpreterObject", "typing.Any"),
    TypePattern(r"hboost::any", "typing.Any"),
    TypePattern(r"PyObject( \*| \&)?", "typing.Any"),
    TypePattern(r"\".*\"", "str"),
    TypePattern("P N", "str"), # special case for one function, setBlendshapeDeformerParms
    TypePattern(r"id", "str")
]

TYPES_POST_FIX = {
    "Double" : "float",
    "Float" : "float",
    "BinaryString" : "bytes",
    "String" : "str",
    "std::string" : "str",
    "InterpreterObject" : "typing.Any",
    "Int" : "int",
    "int64" : "int",
    "double" : "float",
    "HOM_" : "",
    "const &" : "",
    "const" : "",
    " &" : ""
}

def fix_types(string: str) -> str:
    string = RE_CLEAN_PATTERN.sub("", string)
    
    for pattern in TYPES_PATTERN_DECL:
        _string = pattern.sub(string)

        if _string != string:

            for type, sub in TYPES_POST_FIX.items():
                if type in _string:
                    _string = _string.replace(type, sub)            
                    break
            
            return _string

    return string

RE_CLEAN_PATTERN = re.compile("(=\(\))|\(|\)|'")

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

    return list(set(values))

if __name__ == "__main__":
    print("Generating stubs for HOM")

    try:
        import hou

        module = hou

        print("hou module has been imported, using it to generate the stubs")
    except ImportError:
        print("Cannot import hou, trying to find it with the provided path")
    
        parser = optparse.OptionParser()
        parser.add_option("--path-to-hou",
                        dest="hou_path",
                        default=None,
                        help="Path to hou.py file")
        
        options, args = parser.parse_args()
        hou_path = options.hou_path
        
        if hou_path is None:
            print("No path has been provided to find hou.py, exiting")
            sys.exit(1)

        if not os.path.exists(hou_path):
            print("Path provided to find hou.py does not exist, exiting")
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
    output.write("from enum import Enum")
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

        class_doc = _class.__doc__
        
        if class_doc is None:
            class_doc = "\n    No documentation available\n"
        else:
            class_doc = class_doc.replace("\\t", "    ")

        if "Enum" in class_doc or "VALUES" in class_doc:
            class_parent = "Enum"
            
        output.write(f"class {class_name}({class_parent}):\n")
        output.write("    \"\"\"")
        output.write(class_doc) 
        output.write("\"\"\"\n")
        output.write("\n")

        if "Enum" in class_doc or "VALUES" in class_doc:
            enum = get_enumeration(class_doc, class_name)

            for i, val in enumerate(enum):
                output.write(f"    {val} = {i}\n")

        output.write("\n")

        class_methods = inspect.getmembers(_class, inspect.isfunction)

        for method in class_methods:
            method_name = method[0]
            _method = method[1]

            if method_name.startswith("_") and not "__init__" in method_name:
                continue

            method_sig = inspect.signature(_method)        
            method_doc = _method.__doc__

            if method_doc is None:
                method_doc = "\n        No documentation available\n        "

            parms = list()
            
            for parm in method_sig.parameters.values():
                parm_str = str(parm)
                
                parm_default = None

                if "=" in parm_str:
                    parm_type, parm_default = parm_str.split("=")
                    parms.append(f"{fix_types(parm_type)} = {parm_default}")
                else:
                    parms.append(fix_types(parm_str))
                
            parms_str = ", ".join(parms)

            if method_sig.return_annotation == inspect._empty:
                return_annotation = "None"
            else:
                return_annotation = fix_types(method_sig.return_annotation)

            output.write(f"    def {method_name}({parms_str}) -> {return_annotation}:\n")
            output.write(f"        \"\"\"")
            output.write(method_doc)
            output.write(f"\"\"\"\n")
            output.write(f"        pass\n")
            output.write("\n")

    functions = sorted(functions, key=lambda c: inspect.getsourcelines(c[1])[1])

    for function in functions:
        function_name = function[0]
        _function = function[1]

        function_sig = inspect.signature(_function)        
        function_doc = _function.__doc__

        if function_doc is None:
            function_doc = "\n    No documentation available\n    "

        parms = list()
        
        for parm in function_sig.parameters.values():
            parm_str = str(parm)
            
            parm_default = None

            if "=" in parm_str:
                parm_type, parm_default = parm_str.split("=")
                parms.append(f"{fix_types(parm_type)} = {parm_default}")
            else:
                parms.append(fix_types(parm_str))
            
        parms_str = ", ".join(parms)

        if function_sig.return_annotation == inspect._empty:
            return_annotation = "None"
        else:
            return_annotation = fix_types(function_sig.return_annotation)

        output.write(f"def {function_name}({parms_str}) -> {return_annotation}:\n")
        output.write(f"    \"\"\"")
        output.write(function_doc)
        output.write(f"\"\"\"\n")
        output.write(f"    pass\n")
        output.write("\n")

    os.makedirs("stubs", exist_ok=True)    
    
    with open("stubs/hou.py", "w") as file:
        file.write(output.getvalue())

    sys.exit(0)
