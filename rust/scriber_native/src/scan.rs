use globset::GlobBuilder;
use ignore::WalkBuilder;
use pyo3::prelude::*;
use std::path::Path;

#[pyclass]
#[derive(Clone)]
pub struct NativeFileInfo {
    #[pyo3(get)]
    pub relative: String,
    #[pyo3(get)]
    pub kind: String,
    #[pyo3(get)]
    pub language: String,
    #[pyo3(get)]
    pub size_bytes: u64,
    #[pyo3(get)]
    pub is_binary: bool,
    #[pyo3(get)]
    pub support_category: Option<String>,
    #[pyo3(get)]
    pub content_policy: String,
    #[pyo3(get)]
    pub mtime_ns: u64,
}

#[derive(Clone)]
pub struct PreparedPattern {
    pub normalized_pat: String,
    pub prefix_star_star: Option<String>,
    pub matcher: globset::GlobMatcher,
    pub double_star_short_matcher: Option<globset::GlobMatcher>,
}

#[derive(Clone)]
pub struct PathMatcher {
    patterns: Vec<PreparedPattern>,
}

impl PathMatcher {
    pub fn new(raw_patterns: &[String]) -> Self {
        let mut patterns = Vec::new();
        for raw in raw_patterns {
            let mut pat = raw.replace("\\", "/").trim().to_string();
            if pat.is_empty() {
                continue;
            }
            if pat.starts_with('/') {
                pat = pat[1..].to_string();
            }
            if pat.ends_with('/') {
                pat = pat[..pat.len() - 1].to_string();
            }

            let mut prefix_star_star = None;
            if pat.ends_with("/**") {
                let prefix = pat[..pat.len() - 3].trim_matches('/').to_string();
                prefix_star_star = Some(prefix);
            }

            let mut double_star_short_glob = None;
            if let Some(short) = pat.strip_prefix("**/") {
                if let Ok(g) = GlobBuilder::new(short).literal_separator(false).build() {
                    double_star_short_glob = Some(g);
                }
            }

            if let Ok(g) = GlobBuilder::new(&pat).literal_separator(false).build() {
                let matcher = g.compile_matcher();
                let double_star_short_matcher = double_star_short_glob
                    .as_ref()
                    .map(|d_g| d_g.compile_matcher());
                patterns.push(PreparedPattern {
                    normalized_pat: pat,
                    prefix_star_star,
                    matcher,
                    double_star_short_matcher,
                });
            }
        }
        PathMatcher { patterns }
    }

    pub fn matches(&self, rel_path: &str) -> bool {
        if self.patterns.is_empty() {
            return false;
        }
        let rel = rel_path.replace("\\", "/").trim_matches('/').to_string();
        for p in &self.patterns {
            if rel == p.normalized_pat {
                return true;
            }
            if let Some(ref prefix) = p.prefix_star_star {
                if rel == *prefix || rel.starts_with(&format!("{}/", prefix)) {
                    return true;
                }
            }
            if p.matcher.is_match(&rel) {
                return true;
            }
            if !p.normalized_pat.contains('/') {
                if let Some(filename) = rel.rsplit('/').next() {
                    if p.matcher.is_match(filename) {
                        return true;
                    }
                }
            }
            if let Some(ref short_matcher) = p.double_star_short_matcher {
                if short_matcher.is_match(&rel) {
                    return true;
                }
                if let Some(filename) = rel.rsplit('/').next() {
                    if short_matcher.is_match(filename) {
                        return true;
                    }
                }
            }
        }
        false
    }
}

fn to_posix_string(path: &Path) -> String {
    path.to_string_lossy().replace("\\", "/")
}

fn language_for(name: &str) -> String {
    if name.starts_with("Dockerfile") {
        return "dockerfile".to_string();
    }
    let suffix = match name.rfind('.') {
        Some(idx) => &name[idx..],
        None => "",
    };
    let lang = match suffix.to_lowercase().as_str() {
        ".py" | ".pyi" => "python",
        ".rs" => "rust",
        ".js" | ".jsx" => "javascript",
        ".ts" | ".tsx" => "typescript",
        ".go" => "go",
        ".java" => "java",
        ".kt" => "kotlin",
        ".c" | ".h" => "c",
        ".cpp" | ".hpp" | ".cc" | ".cxx" | ".hh" | ".hxx" => "cpp",
        ".toml" => "toml",
        ".yaml" | ".yml" => "yaml",
        ".json" => "json",
        ".md" => "markdown",
        ".rst" => "rst",
        ".txt" => "text",
        ".ini" | ".cfg" => "ini",
        ".lock" => "lock",
        _ => "text",
    };
    lang.to_string()
}

fn support_category(rel_s: &str, name: &str) -> String {
    if name == "pyproject.toml"
        || name.ends_with(".toml")
        || name == "setup.py"
        || name == "setup.cfg"
        || name == "tox.ini"
        || name == "pytest.ini"
        || name == "mypy.ini"
        || name == "ruff.toml"
        || name == ".ruff.toml"
    {
        return "project config".to_string();
    }
    if name.ends_with(".lock")
        || name == "requirements.txt"
        || name == "poetry.lock"
        || name == "uv.lock"
        || name == "Pipfile"
        || name == "Pipfile.lock"
        || name == "package.json"
        || name == "package-lock.json"
        || name == "pnpm-lock.yaml"
        || name == "yarn.lock"
        || name == "Cargo.toml"
        || name == "Cargo.lock"
        || name == "go.mod"
        || name == "go.sum"
        || rel_s.starts_with("requirements/")
    {
        return "dependency file".to_string();
    }
    if name.starts_with("README")
        || name == "CHANGELOG.md"
        || name == "CONTRIBUTING.md"
        || rel_s.starts_with("docs/")
    {
        return "documentation".to_string();
    }
    if name.starts_with("Dockerfile")
        || name.starts_with("docker-compose")
        || name.starts_with("compose")
    {
        return "runtime support".to_string();
    }
    if rel_s.starts_with(".github/workflows/") || name == ".gitlab-ci.yml" {
        return "ci support".to_string();
    }
    if name.starts_with(".env") || rel_s.starts_with("config/") || rel_s.starts_with("settings/") {
        return "runtime config".to_string();
    }
    if name == ".pre-commit-config.yaml"
        || name == "tsconfig.json"
        || name.starts_with("vite.config")
        || name.starts_with("webpack.config")
    {
        return "tooling config".to_string();
    }
    "support file".to_string()
}

#[allow(clippy::too_many_arguments)]
pub fn scan_project_native(
    root_path: &str,
    use_gitignore: bool,
    hard_ignore_patterns: Vec<String>,
    code_patterns: Vec<String>,
    support_patterns: Vec<String>,
    support_full_patterns: Vec<String>,
    support_tree_only_patterns: Vec<String>,
    support_default_policy: String,
    support_enabled: bool,
) -> PyResult<Vec<NativeFileInfo>> {
    let root = Path::new(root_path);
    let hard_ignore_matcher = PathMatcher::new(&hard_ignore_patterns);
    let code_matcher = PathMatcher::new(&code_patterns);
    let support_matcher = PathMatcher::new(&support_patterns);
    let support_tree_only_matcher = PathMatcher::new(&support_tree_only_patterns);
    let support_full_matcher = PathMatcher::new(&support_full_patterns);

    let mut builder = WalkBuilder::new(root);
    builder.standard_filters(use_gitignore);
    builder.hidden(false);

    let hard_ignore_matcher_clone = hard_ignore_matcher.clone();
    let root_clone = root.to_path_buf();
    builder.filter_entry(move |entry| {
        if let Ok(rel) = entry.path().strip_prefix(&root_clone) {
            let rel_s = to_posix_string(rel);
            if rel_s != "." && !rel_s.is_empty() && hard_ignore_matcher_clone.matches(&rel_s) {
                return false;
            }
        }
        true
    });

    let mut file_infos = Vec::new();

    for result in builder.build() {
        let entry = match result {
            Ok(e) => e,
            Err(_) => continue,
        };

        if !entry.file_type().is_some_and(|ft| ft.is_file()) {
            continue;
        }

        let path = entry.path();
        let rel = match path.strip_prefix(root) {
            Ok(r) => r,
            Err(_) => continue,
        };
        let rel_s = to_posix_string(rel);

        if rel_s.is_empty() {
            continue;
        }

        if hard_ignore_matcher.matches(&rel_s) {
            continue;
        }

        let kind;
        let mut category = None;
        let mut policy = "auto".to_string();

        if code_matcher.matches(&rel_s) {
            kind = "code";
        } else if support_enabled && support_matcher.matches(&rel_s) {
            kind = "support";
            let name = path.file_name().and_then(|n| n.to_str()).unwrap_or("");
            category = Some(support_category(&rel_s, name));
            if support_tree_only_matcher.matches(&rel_s) {
                policy = "tree_only".to_string();
            } else if support_full_matcher.matches(&rel_s) {
                policy = "full".to_string();
            } else {
                policy = support_default_policy.clone();
            }
        } else {
            continue;
        }

        let metadata = match entry.metadata() {
            Ok(m) => m,
            Err(_) => continue,
        };
        let size_bytes = metadata.len();

        let mtime_ns = match metadata.modified() {
            Ok(t) => t
                .duration_since(std::time::SystemTime::UNIX_EPOCH)
                .map_or(0, |d| d.as_nanos() as u64),
            Err(_) => 0,
        };

        let is_binary = crate::io::is_binary(path);

        file_infos.push(NativeFileInfo {
            relative: rel_s,
            kind: kind.to_string(),
            language: language_for(path.file_name().and_then(|n| n.to_str()).unwrap_or("")),
            size_bytes,
            is_binary,
            support_category: category,
            content_policy: policy,
            mtime_ns,
        });
    }

    Ok(file_infos)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn matches_double_star_suffix() {
        let matcher = PathMatcher::new(&["**/*.py".to_string()]);
        assert!(matcher.matches("src/main.py"));
        assert!(matcher.matches("main.py"));
        assert!(!matcher.matches("src/main.rs"));
    }

    #[test]
    fn matches_dir_prefix() {
        let matcher = PathMatcher::new(&["target/**".to_string()]);
        assert!(matcher.matches("target/debug/x"));
        assert!(!matcher.matches("src/target.rs"));
    }

    #[test]
    fn matches_basename() {
        let matcher = PathMatcher::new(&["Cargo.toml".to_string()]);
        assert!(matcher.matches("Cargo.toml"));
        assert!(matcher.matches("crates/a/Cargo.toml"));
    }
}
