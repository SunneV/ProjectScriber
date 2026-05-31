use pyo3::prelude::*;

mod import;
mod io;
mod render;
mod scan;
mod score;

#[pyfunction]
#[pyo3(name = "read_text")]
fn read_text(path: &str) -> PyResult<String> {
    io::read_text_lossy_native(path)
}

#[pyfunction]
#[pyo3(name = "write_text")]
fn write_text(path: &str, content: &str) -> PyResult<()> {
    io::write_text_native(path, content)
}

#[pyfunction]
#[pyo3(name = "is_probably_binary")]
fn is_probably_binary(path: &str) -> PyResult<bool> {
    io::is_binary_native(path)
}

#[pyfunction]
#[pyo3(name = "read_many_text")]
fn read_many_text(paths: Vec<String>) -> PyResult<Vec<String>> {
    io::read_many_text_native(paths)
}

#[pyfunction]
#[pyo3(name = "scan_project")]
#[allow(clippy::too_many_arguments)]
fn scan_project(
    root_path: &str,
    use_gitignore: bool,
    hard_ignore_patterns: Vec<String>,
    code_patterns: Vec<String>,
    support_patterns: Vec<String>,
    support_full_patterns: Vec<String>,
    support_tree_only_patterns: Vec<String>,
    support_default_policy: String,
    support_enabled: bool,
) -> PyResult<Vec<scan::NativeFileInfo>> {
    scan::scan_project_native(
        root_path,
        use_gitignore,
        hard_ignore_patterns,
        code_patterns,
        support_patterns,
        support_full_patterns,
        support_tree_only_patterns,
        support_default_policy,
        support_enabled,
    )
}

#[pyfunction]
fn native_api_version() -> u32 {
    1
}

#[pyfunction]
fn build_info() -> PyResult<String> {
    Ok(format!(
        "scriber-native {} {}",
        env!("CARGO_PKG_VERSION"),
        std::env::consts::OS
    ))
}

#[pymodule]
#[allow(deprecated)]
fn _native(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<scan::NativeFileInfo>()?;
    m.add_class::<import::NativeImportEdge>()?;
    m.add_class::<import::NativeRelationEdge>()?;
    m.add_class::<score::NativeCandidate>()?;
    m.add_class::<score::NativePackOptions>()?;
    m.add_function(wrap_pyfunction!(read_text, m)?)?;
    m.add_function(wrap_pyfunction!(write_text, m)?)?;
    m.add_function(wrap_pyfunction!(is_probably_binary, m)?)?;
    m.add_function(wrap_pyfunction!(read_many_text, m)?)?;
    m.add_function(wrap_pyfunction!(scan_project, m)?)?;
    m.add_function(wrap_pyfunction!(import::build_import_graph, m)?)?;
    m.add_function(wrap_pyfunction!(import::build_relation_graph, m)?)?;
    m.add_function(wrap_pyfunction!(score::score_candidates_native, m)?)?;
    m.add_function(wrap_pyfunction!(render::render_tree, m)?)?;
    m.add_function(wrap_pyfunction!(native_api_version, m)?)?;
    m.add_function(wrap_pyfunction!(build_info, m)?)?;
    Ok(())
}
