# Generate stubs for hou.py with the correct type annotation

import inspect
import os
import importlib
import sys
import optparse
import types
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
    TypePattern(r"std::pair< (HOM_|UT_)?([a-zA-Z0-9_:]+),std::vector< (HOM_|UT_)?([a-zA-Z0-9_:]+),.*", r"typing.Tuple[\g<2>, typing.List[\g<4>]]"),
    TypePattern(r"UT_Tuple< (HOM_|UT_)?([a-zA-Z0-9_]+),std::vector.*", r"typing.Tuple[\g<2>, typing.List[typing.Any]]"),
    TypePattern(r"std::vector< std::map< .+ >", r"typing.List[typing.Dict]"),
    TypePattern(r"std::map< .+ >", r"typing.Dict"),
    TypePattern(r"std::vector< std::pair< .+ >", r"typing.List[typing.Any]"),
    TypePattern(r"std::vector< std::vector< (HOM_ElemPtr< |HOM_|UT_)?([A-Za-z0-9_:]+)( >)?( \*)?,.*", r"typing.List[typing.List[\g<2>]]"),
    TypePattern(r"std::vector< UT_Tuple.*", "typing.List[typing.Tuple]"),
    TypePattern(r"std::vector< (HOM_ElemPtr< |HOM_|UT_)?([A-Za-z0-9_:]+)( >)?( \*)?,.*", r"typing.List[\g<2>]"),
    TypePattern(r"(HOM_)?IterableList< (HOM_ElemPtr< |HOM_|UT_)?([A-Za-z0-9_]+)( >)?( \*)?", r"typing.List[\g<3>]"),
    TypePattern(r"UT_SharedPtr< (HOM_|UT_)?([a-zA-Z0-9_]+) >", r"\g<2>"),
    TypePattern(r"HOM_PtrOrNull< (HOM_|UT_)?([a-zA-Z0-9_]+) ?>", r"\g<2>"),
    TypePattern(r"std::pair< (HOM_|UT_)?([a-zA-Z0-9_:]+),.*", r"typing.Tuple[\g<2>, \g<2>]"),
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

def generate_stubs(hou) -> None:
    if not hou.isUIAvailable():
        print("hou.ui is not available, cannot generate stubs for ui class")
    
    module = hou

    classes = inspect.getmembers(module, inspect.isclass)
    functions = inspect.getmembers(module, inspect.isfunction)
    modules = inspect.getmembers(module, inspect.ismodule)

    classes = sorted(classes, key=lambda c: inspect.getsourcelines(c[1])[1])
    functions = sorted(functions, key=lambda c: inspect.getsourcelines(c[1])[1])
    
    classes_names = [c[0] for c in classes]
    functions_names = [f[0] for f in functions]
    modules_names = [m[0] for m in modules]

    others = list()
    
    for obj in dir(hou):
        if (not obj in classes_names and 
            not obj in functions_names and
            not obj in modules_names and
            not obj.startswith(("__", "_"))):
            if hasattr(hou, obj):
                others.append((obj, getattr(hou, obj)))
            
    for other in others:
        if callable(other[1]):
            functions.append(other)
            continue

        members = inspect.getmembers(other[1])

        if len(members) > 0:
            classes.append(other)
            continue

    output = io.StringIO()
    output.write("# Houdini stubs\n")
    output.write("from __future__ import annotations\n")
    output.write("\n")
    output.write("import typing\n")
    output.write("from enum import Enum")
    output.write("\n")
    output.write("\n")


    for _class in classes:
        class_name = _class[0]
        _class = _class[1]

        if class_name.startswith("_"):
            continue

        try:
            class_mro = inspect.getmro(_class)

            class_parent = class_mro[1].__name__.replace("hou.", "") if len(class_mro) > 1 else "object"
        except AttributeError:
            class_parent = "object"

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

        class_methods_names = [f[0] for f in class_methods]
        
        others = list()
        
        for obj in dir(_class):
            if not obj in class_methods_names:
                if hasattr(_class, obj):
                    others.append((obj, getattr(_class, obj)))
        
        for other in others:
            if callable(other[1]):
                class_methods.append(other)

        for method in class_methods:
            method_name = method[0]
            _method = method[1]

            if method_name.startswith("_") and not "__init__" in method_name:
                continue

            try:
                method_sig = inspect.signature(_method)        
            except ValueError:
                print(f"Cannot find signature for function \"{method_name}\", skipping it")
                
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

    for function in functions:
        function_name = function[0]
        _function = function[1]

        try:
            function_sig = inspect.signature(_function)        
        except ValueError:
            print(f"Cannot find signature of function \"{function_name}\", skipping it")

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

    stubs_file_path = "{0}/stubs/hou.py".format(os.path.dirname(__file__))
    
    os.makedirs(os.path.dirname(stubs_file_path), exist_ok=True)
    
    with open(stubs_file_path, "w") as file:
        file.write(output.getvalue())

    print(f"Stubs have been written to {stubs_file_path}")

if __name__ == "__main__":
    print("Generating stubs for HOM")

    if "hython" in sys.executable:
        print("Hython detected")
        import hou
        generate_stubs(hou)

        sys.exit(0)

    if sys.version_info.major != 3:
        print("Stubs generator does not work with python 2 !")
        sys.exit(1)

    if hasattr(sys, "setdlopenflags"):
        old_dlopen_flags = sys.getdlopenflags()
        sys.setdlopenflags(old_dlopen_flags | os.RTLD_GLOBAL)
        
    if sys.platform == "win32" and hasattr(os, "add_dll_directory"):
        os.add_dll_directory("{}/bin".format(os.environ["HFS"]))

    try:
        import hou
    except ImportError:
        sys.path.append(os.environ["HHP"])

        import hou
    finally:
        if hasattr(sys, "setdlopenflags"):
            sys.setdlopenflags(old_dlopen_flags)

    generate_stubs(hou)
    
    sys.exit(0)
