use crate::import::NativeRelationEdge;
use crate::scan::NativeFileInfo;
use pyo3::prelude::*;
use std::collections::{HashMap, HashSet};
use std::path::Path;

#[pyclass]
#[derive(Clone, Debug)]
pub struct NativeCandidate {
    #[pyo3(get)]
    pub path: String,
    #[pyo3(get)]
    pub kind: String,
    #[pyo3(get, set)]
    pub score: i32,
    #[pyo3(get, set)]
    pub reasons: Vec<String>,
    #[pyo3(get, set)]
    pub reason_summary: String,
    #[pyo3(get, set)]
    pub include_content: bool,
    #[pyo3(get, set)]
    pub omitted_reason: Option<String>,
}

#[pyclass]
#[derive(Clone, Debug)]
pub struct NativePackOptions {
    #[pyo3(get, set)]
    pub mode: String,
    #[pyo3(get, set)]
    pub max_files: usize,
    #[pyo3(get, set)]
    pub min_score: i32,
    #[pyo3(get, set)]
    pub tree_min_score: i32,

    // Config scoring values
    #[pyo3(get, set)]
    pub seed_file_score: i32,
    #[pyo3(get, set)]
    pub seed_folder_file_score: i32,
    #[pyo3(get, set)]
    pub direct_dependency_score: i32,
    #[pyo3(get, set)]
    pub reverse_dependency_score: i32,
    #[pyo3(get, set)]
    pub same_package_score: i32,
    #[pyo3(get, set)]
    pub parent_entrypoint_score: i32,
    #[pyo3(get, set)]
    pub related_test_score: i32,
    #[pyo3(get, set)]
    pub name_similarity_score: i32,
    #[pyo3(get, set)]
    pub support_near_seed_score: i32,
    #[pyo3(get, set)]
    pub project_config_score: i32,
    #[pyo3(get, set)]
    pub dependency_file_score: i32,
    #[pyo3(get, set)]
    pub runtime_support_score: i32,
    #[pyo3(get, set)]
    pub documentation_score: i32,
    #[pyo3(get, set)]
    pub shared_dependency_bonus: i32,

    // Module flags
    #[pyo3(get, set)]
    pub modules_enabled: bool,
    #[pyo3(get, set)]
    pub include_direct_dependencies: bool,
    #[pyo3(get, set)]
    pub include_reverse_dependencies: bool,
    #[pyo3(get, set)]
    pub include_same_package: bool,
    #[pyo3(get, set)]
    pub include_parent_entrypoints: bool,
    #[pyo3(get, set)]
    pub include_tests: bool,
    #[pyo3(get, set)]
    pub include_project_configs: bool,
    #[pyo3(get, set)]
    pub depth: usize,

    // Support file scanning
    #[pyo3(get, set)]
    pub support_enabled: bool,

    // Python module info
    #[pyo3(get, set)]
    pub entrypoint_patterns: Vec<String>,
    #[pyo3(get, set)]
    pub test_roots: Vec<String>,
}

#[pymethods]
impl NativePackOptions {
    #[new]
    #[pyo3(signature = (
        mode = "focused".to_string(),
        max_files = 0,
        min_score = 0,
        tree_min_score = 0,
        seed_file_score = 100,
        seed_folder_file_score = 90,
        direct_dependency_score = 80,
        reverse_dependency_score = 70,
        same_package_score = 75,
        parent_entrypoint_score = 70,
        related_test_score = 85,
        name_similarity_score = 65,
        support_near_seed_score = 50,
        project_config_score = 70,
        dependency_file_score = 60,
        runtime_support_score = 50,
        documentation_score = 45,
        shared_dependency_bonus = 10,
        modules_enabled = true,
        include_direct_dependencies = true,
        include_reverse_dependencies = true,
        include_same_package = true,
        include_parent_entrypoints = true,
        include_tests = true,
        include_project_configs = true,
        depth = 2,
        support_enabled = true,
        entrypoint_patterns = Vec::new(),
        test_roots = Vec::new(),
    ))]
    #[allow(clippy::too_many_arguments)]
    fn new(
        mode: String,
        max_files: usize,
        min_score: i32,
        tree_min_score: i32,
        seed_file_score: i32,
        seed_folder_file_score: i32,
        direct_dependency_score: i32,
        reverse_dependency_score: i32,
        same_package_score: i32,
        parent_entrypoint_score: i32,
        related_test_score: i32,
        name_similarity_score: i32,
        support_near_seed_score: i32,
        project_config_score: i32,
        dependency_file_score: i32,
        runtime_support_score: i32,
        documentation_score: i32,
        shared_dependency_bonus: i32,
        modules_enabled: bool,
        include_direct_dependencies: bool,
        include_reverse_dependencies: bool,
        include_same_package: bool,
        include_parent_entrypoints: bool,
        include_tests: bool,
        include_project_configs: bool,
        depth: usize,
        support_enabled: bool,
        entrypoint_patterns: Vec<String>,
        test_roots: Vec<String>,
    ) -> Self {
        NativePackOptions {
            mode,
            max_files,
            min_score,
            tree_min_score,
            seed_file_score,
            seed_folder_file_score,
            direct_dependency_score,
            reverse_dependency_score,
            same_package_score,
            parent_entrypoint_score,
            related_test_score,
            name_similarity_score,
            support_near_seed_score,
            project_config_score,
            dependency_file_score,
            runtime_support_score,
            documentation_score,
            shared_dependency_bonus,
            modules_enabled,
            include_direct_dependencies,
            include_reverse_dependencies,
            include_same_package,
            include_parent_entrypoints,
            include_tests,
            include_project_configs,
            depth,
            support_enabled,
            entrypoint_patterns,
            test_roots,
        }
    }
}

// Internal Candidate builder struct to aggregate reasons
struct ScoringCandidate {
    info: NativeFileInfo,
    score: i32,
    reasons: Vec<String>,
    reason_counts: HashMap<String, usize>,
    reason_examples: HashMap<String, Vec<String>>,
    seed_sources: HashSet<String>,
}

fn add_reason(c: &mut ScoringCandidate, kind: &str, label: &str, example: Option<&str>) {
    *c.reason_counts.entry(kind.to_string()).or_default() += 1;
    if let Some(ex) = example {
        let examples = c.reason_examples.entry(kind.to_string()).or_default();
        if !examples.contains(&ex.to_string()) {
            examples.push(ex.to_string());
        }
    }
    if !c.reasons.contains(&label.to_string()) {
        c.reasons.push(label.to_string());
    }
}

fn build_reason_summary(c: &ScoringCandidate) -> String {
    let mut parts = Vec::new();
    let order = vec![
        "seed_file",
        "seed_folder_file",
        "direct_dependency",
        "reverse_dependency",
        "related_test",
        "same_package",
        "parent_entrypoint",
        "name_similarity",
        "support_near_seed",
        "project_support",
        "shared_dependency",
        "entrypoint",
        "test_file",
        "code_file",
        "other_file",
    ];

    for kind in order {
        if let Some(&count) = c.reason_counts.get(kind) {
            let examples = c.reason_examples.get(kind);
            if kind == "seed_file" {
                parts.push("seed file".to_string());
            } else if kind == "seed_folder_file" {
                parts.push("seed folder file".to_string());
            } else if kind == "direct_dependency" {
                if count > 1 {
                    parts.push(format!("imports {} included files", count));
                } else if let Some(exs) = examples {
                    if !exs.is_empty() {
                        let filename = Path::new(&exs[0])
                            .file_name()
                            .unwrap_or(std::ffi::OsStr::new(""))
                            .to_string_lossy();
                        parts.push(format!("imports {}", filename));
                    } else {
                        parts.push("imports seed".to_string());
                    }
                } else {
                    parts.push("imports seed".to_string());
                }
            } else if kind == "reverse_dependency" {
                if count > 1 {
                    parts.push(format!("imported by {} included files", count));
                } else if let Some(exs) = examples {
                    if !exs.is_empty() {
                        let filename = Path::new(&exs[0])
                            .file_name()
                            .unwrap_or(std::ffi::OsStr::new(""))
                            .to_string_lossy();
                        parts.push(format!("imported by {}", filename));
                    } else {
                        parts.push("imported by seed".to_string());
                    }
                } else {
                    parts.push("imported by seed".to_string());
                }
            } else if kind == "related_test" {
                parts.push("related test".to_string());
            } else if kind == "same_package" {
                parts.push("same package".to_string());
            } else if kind == "parent_entrypoint" {
                parts.push("parent entrypoint".to_string());
            } else if kind == "name_similarity" {
                parts.push("name similarity".to_string());
            } else if kind == "support_near_seed" {
                parts.push("support file".to_string());
            } else if kind == "project_support" {
                parts.push("project support file".to_string());
            } else if kind == "shared_dependency" {
                parts.push("shared dependency bonus".to_string());
            } else if kind == "entrypoint" {
                parts.push("entrypoint file".to_string());
            } else if kind == "test_file" {
                parts.push("test file".to_string());
            } else if kind == "code_file" {
                parts.push("code file".to_string());
            } else if kind == "other_file" {
                parts.push("other file".to_string());
            }
        }
    }
    parts.join("; ")
}

fn is_test_file(rel: &str, test_roots: &[String]) -> bool {
    let p = Path::new(rel);
    let name = p
        .file_name()
        .unwrap_or(std::ffi::OsStr::new(""))
        .to_string_lossy()
        .to_lowercase();
    for part in p.components().filter_map(|c| c.as_os_str().to_str()) {
        if test_roots.contains(&part.to_string()) {
            return true;
        }
    }
    name.starts_with("test_") || name.ends_with("_test.py") || name.ends_with(".test.py")
}

fn name_related(a: &str, b: &str) -> bool {
    let a_stem = Path::new(a)
        .file_stem()
        .unwrap_or(std::ffi::OsStr::new(""))
        .to_string_lossy()
        .to_lowercase()
        .replace("test_", "")
        .replace("_test", "");
    let b_stem = Path::new(b)
        .file_stem()
        .unwrap_or(std::ffi::OsStr::new(""))
        .to_string_lossy()
        .to_lowercase()
        .replace("test_", "")
        .replace("_test", "");
    if a_stem.is_empty() || b_stem.is_empty() {
        return false;
    }
    a_stem.contains(&b_stem) || b_stem.contains(&a_stem)
}

fn is_near_seed(support_file: &str, seed: &str) -> bool {
    let sf_parent = Path::new(support_file).parent().unwrap_or(Path::new(""));
    if sf_parent == Path::new("") {
        return true;
    }
    let seed_parent = Path::new(seed).parent().unwrap_or(Path::new(""));
    sf_parent == seed_parent
        || sf_parent.starts_with(seed_parent)
        || seed_parent.starts_with(sf_parent)
}

use std::cmp::Ordering;
use std::collections::BinaryHeap;

#[derive(Debug, Clone)]
struct QueueState {
    strength: f64,
    depth: usize,
    node: String,
}

impl Eq for QueueState {}

impl PartialEq for QueueState {
    fn eq(&self, other: &Self) -> bool {
        self.strength == other.strength && self.depth == other.depth && self.node == other.node
    }
}

impl Ord for QueueState {
    fn cmp(&self, other: &Self) -> Ordering {
        self.strength.partial_cmp(&other.strength)
            .unwrap_or(Ordering::Equal)
            .then_with(|| other.depth.cmp(&self.depth))
    }
}

impl PartialOrd for QueueState {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}

fn walk_weighted_neighbors(
    edges: &[NativeRelationEdge],
    start: &str,
    depth: usize,
    reverse: bool,
) -> HashMap<String, f64> {
    let mut adj: HashMap<String, Vec<(String, &NativeRelationEdge)>> = HashMap::new();
    for edge in edges {
        let u = if reverse { &edge.target } else { &edge.source };
        let v = if reverse { &edge.source } else { &edge.target };
        adj.entry(u.clone())
            .or_default()
            .push((v.clone(), edge));
    }

    let mut max_strength: HashMap<String, f64> = HashMap::new();
    max_strength.insert(start.to_string(), 1.0);

    let mut best_at_state: HashMap<(String, usize), f64> = HashMap::new();
    best_at_state.insert((start.to_string(), 0), 1.0);

    let mut heap = BinaryHeap::new();
    heap.push(QueueState {
        strength: 1.0,
        depth: 0,
        node: start.to_string(),
    });

    while let Some(QueueState { strength: u_str, depth: u_depth, node: u }) = heap.pop() {
        if u_str < *best_at_state.get(&(u.clone(), u_depth)).unwrap_or(&0.0) {
            continue;
        }

        if u_depth >= depth {
            continue;
        }

        if let Some(neighbors) = adj.get(&u) {
            for (neighbor, edge) in neighbors {
                let edge_str = if edge.kind == "import" || edge.kind == "reexport" {
                    if u_depth == 0 { 1.0 } else { 0.88 }
                } else {
                    edge.weight * edge.confidence
                };

                let next_str = u_str * edge_str;
                let next_depth = u_depth + 1;

                if next_str > *max_strength.get(neighbor).unwrap_or(&0.0) {
                    max_strength.insert(neighbor.clone(), next_str);
                }

                let state_key = (neighbor.clone(), next_depth);
                if next_str > *best_at_state.get(&state_key).unwrap_or(&0.0) {
                    best_at_state.insert(state_key, next_str);
                    heap.push(QueueState {
                        strength: next_str,
                        depth: next_depth,
                        node: neighbor.clone(),
                    });
                }
            }
        }
    }

    max_strength.remove(start);
    max_strength
}

fn walk_neighbors(
    edges: &HashMap<String, HashSet<String>>,
    start: &str,
    depth: usize,
) -> HashMap<String, usize> {
    let mut found = HashMap::new();
    let mut frontier = HashSet::new();
    frontier.insert(start.to_string());
    let mut visited = HashSet::new();
    visited.insert(start.to_string());

    for distance in 1..=depth {
        let mut next_frontier = HashSet::new();
        for item in frontier {
            if let Some(neighbors) = edges.get(&item) {
                for neighbor in neighbors {
                    if visited.contains(neighbor) {
                        continue;
                    }
                    visited.insert(neighbor.clone());
                    found.insert(neighbor.clone(), distance);
                    next_frontier.insert(neighbor.clone());
                }
            }
        }
        frontier = next_frontier;
        if frontier.is_empty() {
            break;
        }
    }
    found
}

fn support_base_score(file: &NativeFileInfo, options: &NativePackOptions) -> i32 {
    let cat = file.support_category.as_deref().unwrap_or("support file");
    match cat {
        "project config" => options.project_config_score,
        "dependency file" => options.dependency_file_score,
        "runtime support" | "runtime config" | "ci support" | "tooling config" => {
            options.runtime_support_score
        }
        "documentation" => options.documentation_score,
        _ => options.documentation_score,
    }
}

fn matches_entrypoint(rel: &str, entrypoint_patterns: &[String]) -> bool {
    let name = Path::new(rel)
        .file_name()
        .unwrap_or(std::ffi::OsStr::new(""))
        .to_string_lossy()
        .to_string();
    // Simple glob matcher for entrypoints
    for pat in entrypoint_patterns {
        let pat_clean = pat.replace("*", "");
        if pat.starts_with('*') && pat.ends_with('*') {
            if name.contains(&pat_clean) {
                return true;
            }
        } else if pat.starts_with('*') {
            if name.ends_with(&pat_clean) {
                return true;
            }
        } else if pat.ends_with('*') {
            if name.starts_with(&pat_clean) {
                return true;
            }
        } else if name == *pat {
            return true;
        }
    }
    false
}

#[pyfunction]
pub fn score_candidates_native(
    files: Vec<NativeFileInfo>,
    seeds_list: Vec<String>,
    edges: Vec<NativeRelationEdge>,
    options: NativePackOptions,
) -> PyResult<Vec<NativeCandidate>> {
    let mut mapped_files = HashMap::new();
    for f in files {
        mapped_files.insert(
            f.relative.clone(),
            ScoringCandidate {
                info: f.clone(),
                score: 0,
                reasons: Vec::new(),
                reason_counts: HashMap::new(),
                reason_examples: HashMap::new(),
                seed_sources: HashSet::new(),
            },
        );
    }

    // Build graph edges maps
    let mut graph_imports: HashMap<String, HashSet<String>> = HashMap::new();
    let mut graph_imported_by: HashMap<String, HashSet<String>> = HashMap::new();
    for edge in &edges {
        if edge.kind == "import" || edge.kind == "reexport" {
            graph_imports
                .entry(edge.source.clone())
                .or_default()
                .insert(edge.target.clone());
            graph_imported_by
                .entry(edge.target.clone())
                .or_default()
                .insert(edge.source.clone());
        }
    }

    if options.mode == "project_snapshot" {
        for (rel, c) in &mut mapped_files {
            if c.info.kind == "code" {
                if matches_entrypoint(rel, &options.entrypoint_patterns) {
                    c.score = 90;
                    add_reason(c, "entrypoint", "entrypoint file", None);
                } else if is_test_file(rel, &options.test_roots) {
                    c.score = 60;
                    add_reason(c, "test_file", "test file", None);
                } else {
                    c.score = 80;
                    add_reason(c, "code_file", "code file", None);
                }
            } else if c.info.kind == "support" && options.support_enabled {
                let base = support_base_score(&c.info, &options);
                let cat = c
                    .info
                    .support_category
                    .clone()
                    .unwrap_or("support file".to_string());
                c.score = base;
                add_reason(c, "project_support", &cat, None);
            }
        }
    } else {
        // Focused mode scoring
        let mut seed_files = Vec::new();
        for s in &seeds_list {
            // Find all files matching or under seed paths
            for rel in mapped_files.keys() {
                if rel == s || rel.starts_with(&format!("{}/", s)) {
                    seed_files.push(rel.clone());
                }
            }
        }
        let seed_set: HashSet<String> = seed_files.iter().cloned().collect();

        // 1. Seed paths scores
        for s in &seeds_list {
            for rel in &seed_files {
                if rel == s || rel.starts_with(&format!("{}/", s)) {
                    let is_dir = rel != s;
                    let (score, key, reason) = if is_dir {
                        (
                            options.seed_folder_file_score,
                            "seed_folder_file",
                            format!("file inside seed folder `{}`", s),
                        )
                    } else {
                        (
                            options.seed_file_score,
                            "seed_file",
                            "seed file".to_string(),
                        )
                    };
                    if let Some(c) = mapped_files.get_mut(rel) {
                        c.score = std::cmp::max(c.score, score);
                        let r_clone = rel.clone();
                        add_reason(c, key, &reason, Some(&r_clone));
                        c.seed_sources.insert(r_clone);
                    }
                }
            }
        }

        // 2. Dependencies / Related files scores
        if options.modules_enabled {
            for seed_rel in &seed_files {
                // Direct dependencies
                if options.include_direct_dependencies {
                    for (dep, strength) in walk_weighted_neighbors(&edges, seed_rel, options.depth as usize, false) {
                        let score = std::cmp::max(
                            options.tree_min_score,
                            (options.direct_dependency_score as f64 * strength) as i32,
                        );
                        if let Some(c) = mapped_files.get_mut(&dep) {
                            c.score = std::cmp::max(c.score, score);
                            add_reason(
                                c,
                                "direct_dependency",
                                &format!("direct dependency of `{}`", seed_rel),
                                Some(seed_rel),
                            );
                            c.seed_sources.insert(seed_rel.clone());
                        }
                    }
                }

                // Reverse dependencies
                if options.include_reverse_dependencies {
                    for (dep, strength) in walk_weighted_neighbors(&edges, seed_rel, options.depth as usize, true) {
                        let score = std::cmp::max(
                            options.tree_min_score,
                            (options.reverse_dependency_score as f64 * strength) as i32,
                        );
                        if let Some(c) = mapped_files.get_mut(&dep) {
                            c.score = std::cmp::max(c.score, score);
                            add_reason(
                                c,
                                "reverse_dependency",
                                &format!("imports seed `{}`", seed_rel),
                                Some(seed_rel),
                            );
                            c.seed_sources.insert(seed_rel.clone());
                        }
                    }
                }

                // Same package
                if options.include_same_package {
                    let seed_parent = Path::new(seed_rel)
                        .parent()
                        .unwrap_or(Path::new(""))
                        .to_string_lossy()
                        .to_string();
                    for (rel, c) in &mut mapped_files {
                        if c.info.kind == "code" && !seed_set.contains(rel) {
                            let rel_parent = Path::new(rel)
                                .parent()
                                .unwrap_or(Path::new(""))
                                .to_string_lossy()
                                .to_string();
                            if rel_parent == seed_parent {
                                c.score = std::cmp::max(c.score, options.same_package_score);
                                add_reason(
                                    c,
                                    "same_package",
                                    &format!("same package as `{}`", seed_rel),
                                    Some(seed_rel),
                                );
                                c.seed_sources.insert(seed_rel.clone());
                            }
                        }
                    }
                }

                // Parent entrypoints
                if options.include_parent_entrypoints {
                    for (rel, c) in &mut mapped_files {
                        if c.info.kind == "code"
                            && matches_entrypoint(rel, &options.entrypoint_patterns)
                        {
                            let rel_p = Path::new(rel);
                            let seed_p = Path::new(seed_rel);
                            let is_parent = rel_p.parent() == Some(Path::new(""))
                                || seed_p.starts_with(rel_p.parent().unwrap())
                                || rel_p.starts_with(seed_p.parent().unwrap());
                            if is_parent {
                                c.score = std::cmp::max(c.score, options.parent_entrypoint_score);
                                add_reason(
                                    c,
                                    "parent_entrypoint",
                                    &format!("parent/entrypoint near `{}`", seed_rel),
                                    Some(seed_rel),
                                );
                                c.seed_sources.insert(seed_rel.clone());
                            }
                        }
                    }
                }

                // Related tests
                if options.include_tests {
                    for (rel, c) in &mut mapped_files {
                        if c.info.kind == "code" && is_test_file(rel, &options.test_roots) {
                            let matches_name = name_related(rel, seed_rel);
                            let is_dep = graph_imports
                                .get(rel)
                                .is_some_and(|deps| deps.contains(seed_rel));
                            if matches_name || is_dep {
                                c.score = std::cmp::max(c.score, options.related_test_score);
                                add_reason(
                                    c,
                                    "related_test",
                                    &format!("related test for `{}`", seed_rel),
                                    Some(seed_rel),
                                );
                                c.seed_sources.insert(seed_rel.clone());
                            }
                        }
                    }
                }

                // Name similarity
                for (rel, c) in &mut mapped_files {
                    if c.info.kind == "code"
                        && !seed_set.contains(rel)
                        && name_related(rel, seed_rel)
                    {
                        c.score = std::cmp::max(c.score, options.name_similarity_score);
                        add_reason(
                            c,
                            "name_similarity",
                            &format!("name similarity with `{}`", seed_rel),
                            Some(seed_rel),
                        );
                        c.seed_sources.insert(seed_rel.clone());
                    }
                }
            }

            // Support files
            if options.support_enabled {
                for (rel, c) in &mut mapped_files {
                    if c.info.kind == "support" {
                        let base = support_base_score(&c.info, &options);
                        let cat = c
                            .info
                            .support_category
                            .clone()
                            .unwrap_or("support file".to_string());
                        if rel == "pyproject.toml" {
                            c.score = std::cmp::max(c.score, options.project_config_score);
                            add_reason(c, "project_support", "project config/root file", None);
                            continue;
                        }

                        let mut added = false;
                        for seed_rel in &seed_files {
                            if is_near_seed(rel, seed_rel) {
                                c.score = std::cmp::max(
                                    c.score,
                                    std::cmp::max(base, options.support_near_seed_score),
                                );
                                add_reason(
                                    c,
                                    "support_near_seed",
                                    &format!("{} near `{}`", cat, seed_rel),
                                    Some(seed_rel),
                                );
                                c.seed_sources.insert(seed_rel.clone());
                                added = true;
                            }
                        }

                        if !added
                            && Path::new(rel).parent() == Some(Path::new(""))
                            && options.include_project_configs
                        {
                            c.score = std::cmp::max(c.score, base);
                            add_reason(c, "project_support", &cat, None);
                        }
                    }
                }
            }
        } else {
            // Modules disabled fallback
            if options.support_enabled {
                if let Some(c) = mapped_files.get_mut("pyproject.toml") {
                    c.score = std::cmp::max(c.score, options.project_config_score);
                    add_reason(c, "project_support", "project config/root file", None);
                }
            }
        }

        // Shared dependency bonus
        for c in mapped_files.values_mut() {
            if c.seed_sources.len() > 1 {
                c.score = std::cmp::min(100, c.score + options.shared_dependency_bonus);
                add_reason(
                    c,
                    "shared_dependency",
                    "shared by multiple seed paths",
                    None,
                );
            }
        }
    }

    // Build summaries & NativeCandidate objects
    let mut candidates = Vec::new();
    let seed_set: HashSet<String> = seeds_list.iter().cloned().collect();

    for c in mapped_files.values() {
        let is_seed = seed_set.contains(&c.info.relative)
            || seeds_list
                .iter()
                .any(|s| c.info.relative.starts_with(&format!("{}/", s)));
        let is_valid_score = c.score >= options.min_score || c.score >= options.tree_min_score;
        if is_seed || is_valid_score {
            let summary = build_reason_summary(c);
            candidates.push(NativeCandidate {
                path: c.info.relative.clone(),
                kind: c.info.kind.clone(),
                score: c.score,
                reasons: c.reasons.clone(),
                reason_summary: summary,
                include_content: true,
                omitted_reason: None,
            });
        }
    }

    // Sort by score desc, kind desc (code first), relative path asc
    candidates.sort_by(|a, b| {
        let score_cmp = b.score.cmp(&a.score);
        if score_cmp != std::cmp::Ordering::Equal {
            return score_cmp;
        }
        let kind_cmp = (b.kind == "code").cmp(&(a.kind == "code"));
        if kind_cmp != std::cmp::Ordering::Equal {
            return kind_cmp;
        }
        a.path.cmp(&b.path)
    });

    // Enforce max files limit
    if options.max_files > 0 && candidates.len() > options.max_files {
        let is_snap = options.mode == "project_snapshot";

        let mut seeds_first = Vec::new();
        let mut rest = Vec::new();
        for cand in candidates {
            let belongs_in_seeds = if is_snap {
                cand.path == "pyproject.toml" || cand.path == "README.md"
            } else {
                let is_seed = seed_set.contains(&cand.path)
                    || seeds_list
                        .iter()
                        .any(|s| cand.path.starts_with(&format!("{}/", s)));
                is_seed || cand.path == "pyproject.toml" || cand.path == "README.md"
            };
            if belongs_in_seeds {
                seeds_first.push(cand);
            } else {
                rest.push(cand);
            }
        }
        let remaining = if options.max_files > seeds_first.len() {
            options.max_files - seeds_first.len()
        } else {
            0
        };
        seeds_first.extend(rest.into_iter().take(remaining));
        candidates = seeds_first;

        // Resort final list
        candidates.sort_by(|a, b| {
            let score_cmp = b.score.cmp(&a.score);
            if score_cmp != std::cmp::Ordering::Equal {
                return score_cmp;
            }
            let kind_cmp = (b.kind == "code").cmp(&(a.kind == "code"));
            if kind_cmp != std::cmp::Ordering::Equal {
                return kind_cmp;
            }
            a.path.cmp(&b.path)
        });
    }

    Ok(candidates)
}
