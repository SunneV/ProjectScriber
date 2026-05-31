from pathlib import Path
from scriber.core.symbols import SymbolIndex, SymbolNode
from scriber.graph.languages.extractor import extract_python_symbols

def test_extract_python_symbols() -> None:
    code = """
class MyClass:
    def __init__(self):
        pass

    async def my_method(self):
        pass

def global_function():
    pass
"""
    index = SymbolIndex()
    file_path = Path("src/dummy.py")
    
    extract_python_symbols(file_path, code, index)
    
    symbols = index.get_symbols(file_path)
    assert len(symbols) == 4
    
    # Check Class
    class_sym = next(s for s in symbols if s.name == "MyClass")
    assert class_sym.kind == "class"
    assert class_sym.parent_name is None
    
    # Check Constructor
    init_sym = next(s for s in symbols if s.name == "__init__")
    assert init_sym.kind == "function"
    assert init_sym.parent_name == "MyClass"
    
    # Check Async Method
    method_sym = next(s for s in symbols if s.name == "my_method")
    assert method_sym.kind == "function"
    assert method_sym.parent_name == "MyClass"
    
    # Check Global Function
    func_sym = next(s for s in symbols if s.name == "global_function")
    assert func_sym.kind == "function"
    assert func_sym.parent_name is None
