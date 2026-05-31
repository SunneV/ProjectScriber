use crate::scan::NativeFileInfo;
use pyo3::prelude::*;
use regex::Regex;
use std::collections::{HashMap, HashSet};
use std::path::Path;

#[pyclass]
#[derive(Clone, Debug)]
pub struct NativeImportEdge {
    #[pyo3(get)]
    pub from: String,
    #[pyo3(get)]
    pub to: String,
    #[pyo3(get)]
    pub kind: String,
}

fn is_under(relative: &str, root: &str) -> bool {
    if root.is_empty() || root == "." {
        return true;
    }
    let rel_parts: Vec<&str> = relative.split('/').collect();
    let root_parts: Vec<&str> = root.split('/').collect();
    if rel_parts.len() < root_parts.len() {
        return false;
    }
    for i in 0..root_parts.len() {
        if rel_parts[i] != root_parts[i] {
            return false;
        }
    }
    true
}

fn relative_to_root(relative: &str, root: &str) -> String {
    if root.is_empty() || root == "." {
        return relative.to_string();
    }
    let rel_parts: Vec<&str> = relative.split('/').collect();
    let root_parts: Vec<&str> = root.split('/').collect();
    rel_parts[root_parts.len()..].join("/")
}

fn module_name_for_file(
    relative: &str,
    source_roots: &[String],
    module_init_files: &[String],
) -> Option<String> {
    let mut roots = source_roots.to_vec();
    roots.sort_by_key(|r| if r == "." { 0 } else { r.len() });
    roots.reverse();

    for r in roots {
        if !is_under(relative, &r) {
            continue;
        }
        let under = relative_to_root(relative, &r);
        if under.is_empty() {
            continue;
        }
        let p = Path::new(&under);
        let file_name = p.file_name()?.to_str()?;
        if file_name.ends_with(".py") || file_name.ends_with(".pyi") {
            let mut parts: Vec<String> = Vec::new();
            if let Some(parent) = p.parent() {
                for c in parent.components() {
                    parts.push(c.as_os_str().to_string_lossy().to_string());
                }
            }
            if !module_init_files.contains(&file_name.to_string()) {
                if let Some(stem) = p.file_stem() {
                    parts.push(stem.to_string_lossy().to_string());
                }
            }
            if parts.is_empty() {
                continue;
            }
            return Some(parts.join("."));
        }
    }
    None
}

fn resolve_relative_module(
    current_module: &str,
    current_is_init: bool,
    level: usize,
    module: &str,
) -> String {
    if level == 0 {
        return module.to_string();
    }
    let mut parts: Vec<&str> = current_module.split('.').collect();
    if !current_is_init && !parts.is_empty() {
        parts.pop();
    }
    let up = level.saturating_sub(1);
    if up < parts.len() {
        parts.truncate(parts.len() - up);
    } else {
        parts.clear();
    }
    if !module.is_empty() {
        for part in module.split('.') {
            parts.push(part);
        }
    }
    parts.join(".")
}

fn normalize_posix_path(path: &str) -> String {
    let mut parts = Vec::new();
    for part in path.split('/') {
        if part.is_empty() || part == "." {
            continue;
        }
        if part == ".." {
            parts.pop();
        } else {
            parts.push(part);
        }
    }
    parts.join("/")
}

#[pyfunction]
pub fn build_import_graph(
    root: &str,
    files: Vec<NativeFileInfo>,
    python_source_roots: Vec<String>,
    python_module_init_files: Vec<String>,
) -> PyResult<Vec<NativeImportEdge>> {
    let mut edges = Vec::new();
    if files.is_empty() {
        return Ok(edges);
    }

    let absolute_to_file: HashMap<String, &NativeFileInfo> =
        files.iter().map(|f| (f.relative.clone(), f)).collect();

    let mut dir_to_files: HashMap<String, Vec<String>> = HashMap::new();
    for file in &files {
        let parent = Path::new(&file.relative)
            .parent()
            .unwrap_or(Path::new(""))
            .to_string_lossy()
            .replace("\\", "/");
        dir_to_files
            .entry(parent)
            .or_default()
            .push(file.relative.clone());
    }

    // Pre-calculate Python module map
    let mut module_to_path: HashMap<String, String> = HashMap::new();
    let mut path_to_module: HashMap<String, String> = HashMap::new();
    for file in &files {
        if let Some(mod_name) = module_name_for_file(
            &file.relative,
            &python_source_roots,
            &python_module_init_files,
        ) {
            path_to_module.insert(file.relative.clone(), mod_name.clone());
            module_to_path
                .entry(mod_name)
                .or_insert_with(|| file.relative.clone());
        }
    }

    // Go module resolution
    let mut go_module_name = None;
    let go_mod_path = Path::new(root).join("go.mod");
    if go_mod_path.exists() {
        if let Ok(content) = std::fs::read_to_string(go_mod_path) {
            let go_mod_re = Regex::new(r"(?m)^\s*module\s+(\S+)").unwrap();
            if let Some(m) = go_mod_re.captures(&content) {
                go_module_name = Some(m.get(1).unwrap().as_str().to_string());
            }
        }
    }

    // Regex compile
    let py_import_re = Regex::new(r"(?m)^\s*import\s+([a-zA-Z0-9_.,\t ]+)").unwrap();
    let py_from_paren_re =
        Regex::new(r"(?m)^\s*from\s+(\.+[a-zA-Z0-9_.]*|[a-zA-Z0-9_.]+)\s+import\s+\(([^)]+)\)")
            .unwrap();
    let py_from_simple_re = Regex::new(
        r"(?m)^\s*from\s+(\.+[a-zA-Z0-9_.]*|[a-zA-Z0-9_.]+)\s+import\s+([a-zA-Z0-9_.,\t ]+)",
    )
    .unwrap();

    let js_import_re = Regex::new(r#"(?:import|export)\s+(?:[\w*\s{},]*\s+from\s+)?['"]([^'"]+)['"]|require\s*\(\s*['"]([^'"]+)['"]\s*\)"#).unwrap();

    let rust_mod_re = Regex::new(r"\bmod\s+(\w+)\s*;").unwrap();
    let rust_use_re = Regex::new(r"\buse\s+([^;]+)\s*;").unwrap();

    let go_import_single_re = Regex::new(r#"\bimport\s+['"]([^'"]+)['"]"#).unwrap();
    let go_import_block_re = Regex::new(r"(?s)\bimport\s*\(([^)]+)\)").unwrap();

    let cpp_include_re = Regex::new(r#"#include\s*["<]([^">]+)[">]"#).unwrap();

    for file in &files {
        if file.kind != "code" || file.is_binary {
            continue;
        }

        let file_abs_path = Path::new(root).join(&file.relative);
        let mut source = match std::fs::read(&file_abs_path) {
            Ok(bytes) => String::from_utf8_lossy(&bytes).to_string(),
            Err(_) => continue,
        };

        if file.language == "python" {
            let normalized = source.replace("\r\n", "\n");
            let mut clean = String::new();
            for line in normalized.lines() {
                if let Some(idx) = line.find('#') {
                    clean.push_str(&line[..idx]);
                } else {
                    clean.push_str(line);
                }
                clean.push('\n');
            }
            source = clean.replace("\\\n", " ");
        }

        let mut resolved_set = HashSet::new();

        if file.language == "python" {
            if let Some(current_module) = path_to_module.get(&file.relative) {
                let current_is_init = file.relative.ends_with("__init__.py");

                // Parse standard imports
                for cap in py_import_re.captures_iter(&source) {
                    if let Some(m) = cap.get(1) {
                        for alias in m.as_str().split(',') {
                            let parts: Vec<&str> = alias.split_whitespace().collect();
                            if !parts.is_empty() {
                                let imported_module = parts[0].to_string();
                                resolved_set.insert((imported_module, true, 0, Vec::new()));
                            }
                        }
                    }
                }

                // Parse from ... import (...)
                for cap in py_from_paren_re.captures_iter(&source) {
                    let from_module = cap.get(1).unwrap().as_str().trim().to_string();
                    let names_str = cap.get(2).unwrap().as_str().trim();
                    let mut names = Vec::new();
                    for name in names_str.split(',') {
                        let parts: Vec<&str> = name.split_whitespace().collect();
                        if !parts.is_empty() && parts[0] != "*" {
                            names.push(parts[0].to_string());
                        }
                    }

                    let mut level = 0;
                    let mut module = from_module;
                    while module.starts_with('.') {
                        level += 1;
                        module = module[1..].to_string();
                    }

                    resolved_set.insert((module, false, level, names));
                }

                // Parse from ... import ... (simple)
                for cap in py_from_simple_re.captures_iter(&source) {
                    let from_module = cap.get(1).unwrap().as_str().trim().to_string();
                    let names_str = cap.get(2).unwrap().as_str().trim();
                    let mut names = Vec::new();
                    for name in names_str.split(',') {
                        let parts: Vec<&str> = name.split_whitespace().collect();
                        if !parts.is_empty() && parts[0] != "*" {
                            names.push(parts[0].to_string());
                        }
                    }

                    let mut level = 0;
                    let mut module = from_module;
                    while module.starts_with('.') {
                        level += 1;
                        module = module[1..].to_string();
                    }

                    resolved_set.insert((module, false, level, names));
                }

                // Resolve python imports
                for (module, is_import, level, names) in resolved_set {
                    let mut candidates = Vec::new();
                    if is_import {
                        candidates.push(module);
                    } else {
                        let base = if level > 0 {
                            resolve_relative_module(current_module, current_is_init, level, &module)
                        } else {
                            module
                        };
                        for name in &names {
                            if !base.is_empty() {
                                candidates.push(format!("{}.{}", base, name));
                            } else {
                                candidates.push(name.clone());
                            }
                        }
                        if !base.is_empty() {
                            candidates.push(base);
                        }
                    }

                    for candidate in candidates {
                        if candidate.is_empty() {
                            continue;
                        }
                        let parts: Vec<&str> = candidate.split('.').collect();
                        for end in (1..=parts.len()).rev() {
                            let mod_name = parts[..end].join(".");
                            if let Some(target_path) = module_to_path.get(&mod_name) {
                                if target_path != &file.relative {
                                    edges.push(NativeImportEdge {
                                        from: file.relative.clone(),
                                        to: target_path.clone(),
                                        kind: "import".to_string(),
                                    });
                                    break;
                                }
                            }
                        }
                    }
                }
            }
        } else if file.language == "javascript" || file.language == "typescript" {
            let parent = Path::new(&file.relative)
                .parent()
                .unwrap_or(Path::new(""))
                .to_string_lossy()
                .replace("\\", "/");
            for cap in js_import_re.captures_iter(&source) {
                let spec = cap
                    .get(1)
                    .or_else(|| cap.get(2))
                    .map(|m| m.as_str())
                    .unwrap_or("");
                if !spec.starts_with('.') {
                    continue;
                }

                let raw_base = if parent.is_empty() {
                    spec.to_string()
                } else {
                    format!("{}/{}", parent, spec)
                };
                let base_normalized = normalize_posix_path(&raw_base);

                let mut resolved = false;
                let extensions = vec!["", ".ts", ".tsx", ".js", ".jsx", ".d.ts"];
                for ext in extensions {
                    let cand = if ext.is_empty() {
                        base_normalized.clone()
                    } else {
                        format!("{}{}", base_normalized, ext)
                    };
                    if let Some(target) = absolute_to_file.get(&cand) {
                        if !target.is_binary && target.relative != file.relative {
                            edges.push(NativeImportEdge {
                                from: file.relative.clone(),
                                to: target.relative.clone(),
                                kind: "import".to_string(),
                            });
                            resolved = true;
                            break;
                        }
                    }
                }

                if !resolved {
                    let index_names = vec!["index.ts", "index.tsx", "index.js", "index.jsx"];
                    for idx in index_names {
                        let cand = format!("{}/{}", base_normalized, idx);
                        if let Some(target) = absolute_to_file.get(&cand) {
                            if !target.is_binary && target.relative != file.relative {
                                edges.push(NativeImportEdge {
                                    from: file.relative.clone(),
                                    to: target.relative.clone(),
                                    kind: "import".to_string(),
                                });
                                break;
                            }
                        }
                    }
                }
            }
        } else if file.language == "rust" {
            let parent = Path::new(&file.relative)
                .parent()
                .unwrap_or(Path::new(""))
                .to_string_lossy()
                .replace("\\", "/");
            let mut mod_specs = Vec::new();

            for cap in rust_mod_re.captures_iter(&source) {
                if let Some(m) = cap.get(1) {
                    mod_specs.push(("mod".to_string(), m.as_str().to_string()));
                }
            }

            for cap in rust_use_re.captures_iter(&source) {
                if let Some(m) = cap.get(1) {
                    let spec = m.as_str().trim();
                    if spec.contains('{') {
                        if let Some(idx) = spec.find('{') {
                            let base = spec[..idx].trim();
                            let rest = spec[idx + 1..].replace('}', "");
                            for part in rest.split(',') {
                                let part_trimmed = part.trim();
                                if !part_trimmed.is_empty() {
                                    mod_specs.push((
                                        "use".to_string(),
                                        format!("{}{}", base, part_trimmed),
                                    ));
                                }
                            }
                        }
                    } else {
                        mod_specs.push(("use".to_string(), spec.to_string()));
                    }
                }
            }

            // Resolve rust
            for (kind, spec) in mod_specs {
                if kind == "mod" {
                    let cand1 = if parent.is_empty() {
                        format!("{}.rs", spec)
                    } else {
                        format!("{}/{}.rs", parent, spec)
                    };
                    let cand2 = if parent.is_empty() {
                        format!("{}/mod.rs", spec)
                    } else {
                        format!("{}/{}/mod.rs", parent, spec)
                    };
                    for cand in &[cand1, cand2] {
                        if let Some(target) = absolute_to_file.get(cand) {
                            if target.relative != file.relative {
                                edges.push(NativeImportEdge {
                                    from: file.relative.clone(),
                                    to: target.relative.clone(),
                                    kind: "mod".to_string(),
                                });
                                break;
                            }
                        }
                    }
                } else {
                    let parts: Vec<&str> = spec.split("::").collect();
                    if parts.is_empty() {
                        continue;
                    }

                    let mut crate_root = "".to_string();
                    let mut curr = Path::new(&file.relative).parent();
                    while let Some(c) = curr {
                        let c_str = c.to_string_lossy().replace("\\", "/");
                        let cargo_toml = if c_str.is_empty() {
                            "Cargo.toml".to_string()
                        } else {
                            format!("{}/Cargo.toml", c_str)
                        };
                        let src_dir = if c_str.is_empty() {
                            "src".to_string()
                        } else {
                            format!("{}/src", c_str)
                        };

                        let has_cargo = absolute_to_file.contains_key(&cargo_toml);
                        let has_src = absolute_to_file
                            .keys()
                            .any(|k| k.starts_with(&format!("{}/", src_dir)) || *k == src_dir);

                        if has_cargo || has_src {
                            crate_root = if has_src { src_dir } else { c_str };
                            break;
                        }
                        curr = c.parent();
                    }

                    if crate_root.is_empty() {
                        crate_root = parent.clone();
                    }

                    if parts[0] == "crate" || parts[0] == "super" || parts[0] == "self" {
                        let base_dir = match parts[0] {
                            "crate" => crate_root,
                            "super" => Path::new(&parent)
                                .parent()
                                .unwrap_or(Path::new(""))
                                .to_string_lossy()
                                .replace("\\", "/"),
                            _ => parent.clone(),
                        };

                        let sub_parts = &parts[1..];
                        if !sub_parts.is_empty() {
                            let mut resolved = false;
                            for end in (1..=sub_parts.len()).rev() {
                                let sub_path = sub_parts[..end].join("/");
                                let path_str = if base_dir.is_empty() {
                                    sub_path
                                } else {
                                    format!("{}/{}", base_dir, sub_path)
                                };
                                let cand1 = format!("{}.rs", path_str);
                                let cand2 = format!("{}/mod.rs", path_str);
                                for cand in &[cand1, cand2] {
                                    if let Some(target) = absolute_to_file.get(cand) {
                                        if target.relative != file.relative {
                                            edges.push(NativeImportEdge {
                                                from: file.relative.clone(),
                                                to: target.relative.clone(),
                                                kind: "use".to_string(),
                                            });
                                            resolved = true;
                                            break;
                                        }
                                    }
                                }
                                if resolved {
                                    break;
                                }
                            }
                        }
                    }
                }
            }
        } else if file.language == "go" {
            let mut specs = Vec::new();
            for cap in go_import_single_re.captures_iter(&source) {
                specs.push(cap.get(1).unwrap().as_str().to_string());
            }
            for cap in go_import_block_re.captures_iter(&source) {
                let block = cap.get(1).unwrap().as_str();
                for line in block.lines() {
                    let line_trimmed = line.trim();
                    if line_trimmed.starts_with("//") {
                        continue;
                    }
                    if let Some(idx) = line_trimmed.find('"') {
                        let sub = &line_trimmed[idx + 1..];
                        if let Some(end) = sub.find('"') {
                            specs.push(sub[..end].to_string());
                        }
                    }
                }
            }

            if let Some(ref mod_name) = go_module_name {
                for spec in specs {
                    if spec.starts_with(mod_name) {
                        let rel_spec = spec[mod_name.len()..].trim_start_matches('/').to_string();
                        if let Some(targets) = dir_to_files.get(&rel_spec) {
                            for target in targets {
                                if target.ends_with(".go") && target != &file.relative {
                                    edges.push(NativeImportEdge {
                                        from: file.relative.clone(),
                                        to: target.clone(),
                                        kind: "import".to_string(),
                                    });
                                }
                            }
                        }
                    }
                }
            }
        } else if file.language == "c" || file.language == "cpp" {
            let parent = Path::new(&file.relative)
                .parent()
                .unwrap_or(Path::new(""))
                .to_string_lossy()
                .replace("\\", "/");
            for cap in cpp_include_re.captures_iter(&source) {
                let spec = cap.get(1).unwrap().as_str();
                let raw_base = if parent.is_empty() {
                    spec.to_string()
                } else {
                    format!("{}/{}", parent, spec)
                };
                let base_normalized = normalize_posix_path(&raw_base);

                if let Some(target) = absolute_to_file.get(&base_normalized) {
                    if !target.is_binary && target.relative != file.relative {
                        edges.push(NativeImportEdge {
                            from: file.relative.clone(),
                            to: target.relative.clone(),
                            kind: "include".to_string(),
                        });
                    }
                } else {
                    for (rel_path, target) in &absolute_to_file {
                        if target.is_binary {
                            continue;
                        }
                        if (*rel_path == spec || rel_path.ends_with(&format!("/{}", spec)))
                            && target.relative != file.relative
                        {
                            edges.push(NativeImportEdge {
                                from: file.relative.clone(),
                                to: target.relative.clone(),
                                kind: "include".to_string(),
                            });
                            break;
                        }
                    }
                }
            }
        }
    }

    Ok(edges)
}

#[pyclass]
#[derive(Clone, Debug)]
pub struct NativeRelationEdge {
    #[pyo3(get)]
    pub source: String,
    #[pyo3(get)]
    pub target: String,
    #[pyo3(get)]
    pub kind: String,
    #[pyo3(get)]
    pub weight: f64,
    #[pyo3(get)]
    pub confidence: f64,
    #[pyo3(get)]
    pub evidence: Option<String>,
    #[pyo3(get)]
    pub line: Option<usize>,
    #[pyo3(get)]
    pub analyzer: String,
}

#[pymethods]
impl NativeRelationEdge {
    #[new]
    #[pyo3(signature = (source, target, kind, weight, confidence, evidence, line, analyzer))]
    fn new(
        source: String,
        target: String,
        kind: String,
        weight: f64,
        confidence: f64,
        evidence: Option<String>,
        line: Option<usize>,
        analyzer: String,
    ) -> Self {
        NativeRelationEdge {
            source,
            target,
            kind,
            weight,
            confidence,
            evidence,
            line,
            analyzer,
        }
    }
}

#[pyfunction]
pub fn build_relation_graph(
    root: &str,
    files: Vec<NativeFileInfo>,
    python_source_roots: Vec<String>,
    python_module_init_files: Vec<String>,
) -> PyResult<Vec<NativeRelationEdge>> {
    let import_edges = build_import_graph(root, files, python_source_roots, python_module_init_files)?;
    
    let mut relation_edges = Vec::with_capacity(import_edges.len());
    for edge in import_edges {
        relation_edges.push(NativeRelationEdge {
            source: edge.from,
            target: edge.to,
            kind: "import".to_string(), // we map everything to "import" for now to match python
            weight: 1.0,
            confidence: 0.98,
            evidence: None,
            line: None,
            analyzer: "imports:native".to_string(),
        });
    }
    
    Ok(relation_edges)
}
