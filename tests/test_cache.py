from __future__ import annotations

import json
from pathlib import Path
from scriber.core.models import ScriberConfig
from scriber.cache import ScriberCache, get_config_hash


def test_cache_functionality(tmp_path: Path) -> None:
    config = ScriberConfig()
    # Ensure cache is enabled
    config.cache.enabled = True
    config.cache.dir = ".scriber/cache"
    
    cache = ScriberCache(config, tmp_path)
    
    rel_path = Path("src/main.py")
    mtime = 123456789
    size = 1000
    data = {"kind": "code", "language": "python", "size_bytes": 1000, "is_binary": False, "support_category": None, "content_policy": "auto", "absolute": "src/main.py", "relative": "src/main.py"}
    
    assert cache.get_file(rel_path, mtime, size) is None
    
    cache.set_file(rel_path, mtime, size, data)
    assert cache.get_file(rel_path, mtime, size) == data
    
    # Check imports cache
    imports = {Path("src/auth.py"), Path("src/db.py")}
    assert cache.get_imports(rel_path) is None
    cache.set_imports(rel_path, imports)
    assert cache.get_imports(rel_path) == imports
    
    # Save cache
    cache.save(active_files={rel_path})
    
    # Check that cache files were created
    assert (tmp_path / ".scriber/cache/files.json").exists()
    assert (tmp_path / ".scriber/cache/imports_v2.json").exists()
    
    # Reload cache and check if retrieved properly
    new_cache = ScriberCache(config, tmp_path)
    assert new_cache.get_file(rel_path, mtime, size) == data
    assert new_cache.get_imports(rel_path) == imports
