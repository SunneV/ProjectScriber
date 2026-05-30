use pyo3::exceptions::PyOSError;
use pyo3::prelude::*;
use std::fs;
use std::path::Path;

pub fn io_err(context: &str, path: &str, err: std::io::Error) -> PyErr {
    PyOSError::new_err(format!("{}: {}: {}", context, path, err))
}

pub fn read_text_lossy_native(path: &str) -> PyResult<String> {
    let bytes = fs::read(path).map_err(|e| io_err("Failed to read", path, e))?;
    Ok(String::from_utf8_lossy(&bytes).into_owned())
}

pub fn write_text_native(path: &str, content: &str) -> PyResult<()> {
    let p = Path::new(path);
    if let Some(parent) = p.parent() {
        fs::create_dir_all(parent)
            .map_err(|e| io_err("Failed to create parent directory", path, e))?;
    }
    fs::write(path, content).map_err(|e| io_err("Failed to write", path, e))
}

pub fn is_binary_native(path: &str) -> PyResult<bool> {
    Ok(is_binary(Path::new(path)))
}

pub fn is_binary(path: &Path) -> bool {
    use std::fs::File;
    use std::io::Read;
    let mut file = match File::open(path) {
        Ok(f) => f,
        Err(_) => return true,
    };
    let mut buf = [0u8; 4096];
    let n = match file.read(&mut buf) {
        Ok(n) => n,
        Err(_) => return true,
    };
    memchr::memchr(0, &buf[..n]).is_some()
}

pub fn read_many_text_native(paths: Vec<String>) -> PyResult<Vec<String>> {
    paths
        .into_iter()
        .map(|path| read_text_lossy_native(&path))
        .collect()
}
