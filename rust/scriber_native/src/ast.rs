//! AST-based relation extraction via tree-sitter (audit feature 1).
//!
//! Only compiled when the `treesitter` Cargo feature is enabled. Walks the
//! AST to emit structural edges (type_reference, inherits) that the regex-based
//! importer cannot detect. When the feature is absent, the module is empty and
//! the Python side falls back to the regex importers.
//!
//! Currently supports Python (recovers parity with the dead Python symbol
//! extractor). Additional grammars can be added behind the same feature.

#[cfg(feature = "treesitter")]
use crate::import::NativeRelationEdge;

/// Collect class names and their base classes from a Python AST.
///
/// Emits:
/// - `type_reference` edges for imported names that reference a class defined
///   in another file (resolved by the caller against a name→path map).
/// - `inherits` edges for base classes referencing a class defined elsewhere.
///
/// `rel` is the source file's posix-relative path; `name_to_rel` maps a
/// symbol name to its defining file's posix-relative path.
#[cfg(feature = "treesitter")]
pub fn extract_python_ast_edges(
    source: &str,
    rel: &str,
    name_to_rel: &std::collections::HashMap<String, String>,
) -> Vec<NativeRelationEdge> {
    use std::collections::HashSet;
    use tree_sitter::Parser;

    let mut parser = Parser::new();
    // tree-sitter-python 0.25 exposes the LANGUAGE const (not a language() fn).
    if parser
        .set_language(&tree_sitter_python::LANGUAGE.into())
        .is_err()
    {
        return Vec::new();
    }
    let tree = match parser.parse(source, None) {
        Some(t) => t,
        None => return Vec::new(),
    };

    let root = tree.root_node();
    let mut defined_classes: HashSet<String> = HashSet::new();
    let mut bases: Vec<(String, usize)> = Vec::new(); // (base_name, line)
    let mut imported_names: HashSet<String> = HashSet::new();

    // Walk the tree once collecting the interesting nodes.
    walk_python(
        root,
        source,
        &mut defined_classes,
        &mut bases,
        &mut imported_names,
    );

    let mut edges = Vec::new();

    // Register this file's classes in the caller's map (done by caller).
    // Emit inherits edges: a class here whose base is defined in another file.
    for (base_name, line) in &bases {
        if let Some(target) = name_to_rel.get(base_name) {
            if target != rel {
                edges.push(NativeRelationEdge {
                    source: rel.to_string(),
                    target: target.clone(),
                    kind: "inherits".to_string(),
                    weight: 0.7,
                    confidence: 0.75,
                    evidence: Some(format!("inherits {}", base_name)),
                    line: Some(*line),
                    analyzer: "ast:python".to_string(),
                });
            }
        }
    }

    // Emit type_reference edges: imported names referencing a class elsewhere.
    for name in &imported_names {
        if let Some(target) = name_to_rel.get(name) {
            if target != rel {
                edges.push(NativeRelationEdge {
                    source: rel.to_string(),
                    target: target.clone(),
                    kind: "type_reference".to_string(),
                    weight: 0.55,
                    confidence: 0.7,
                    evidence: Some(format!("references {}", name)),
                    line: None,
                    analyzer: "ast:python".to_string(),
                });
            }
        }
    }

    edges
}

/// Collect this file's class definitions (name → line) so the caller can build
/// the global name→path map.
#[cfg(feature = "treesitter")]
pub fn collect_python_class_defs(source: &str) -> Vec<(String, usize)> {
    use tree_sitter::Parser;
    let mut parser = Parser::new();
    if parser
        .set_language(&tree_sitter_python::LANGUAGE.into())
        .is_err()
    {
        return Vec::new();
    }
    let tree = match parser.parse(source, None) {
        Some(t) => t,
        None => return Vec::new(),
    };
    let mut defs = Vec::new();
    collect_class_defs_recursive(tree.root_node(), source, &mut defs);
    defs
}

#[cfg(feature = "treesitter")]
fn collect_class_defs_recursive(
    node: tree_sitter::Node,
    source: &str,
    out: &mut Vec<(String, usize)>,
) {
    if node.kind() == "class_definition" {
        // child by field name "name"
        if let Some(name_node) = node.child_by_field_name("name") {
            if let Ok(name) = name_node.utf8_text(source.as_bytes()) {
                out.push((name.to_string(), node.start_position().row + 1));
            }
        }
    }
    for i in 0..node.child_count() {
        if let Some(child) = node.child(i) {
            collect_class_defs_recursive(child, source, out);
        }
    }
}

/// Recursively collect identifiers (tree-sitter 0.25 has no descendants()).
/// Walks children by index to avoid cursor lifetime issues.
#[cfg(feature = "treesitter")]
fn collect_identifiers(
    node: tree_sitter::Node,
    source: &str,
    out: &mut Vec<(String, usize)>,
    line: usize,
) {
    if node.kind() == "identifier" {
        if let Ok(name) = node.utf8_text(source.as_bytes()) {
            out.push((name.to_string(), line));
        }
    }
    for i in 0..node.child_count() {
        if let Some(child) = node.child(i) {
            collect_identifiers(child, source, out, line);
        }
    }
}

#[cfg(feature = "treesitter")]
fn walk_python(
    node: tree_sitter::Node,
    source: &str,
    defined_classes: &mut std::collections::HashSet<String>,
    bases: &mut Vec<(String, usize)>,
    imported_names: &mut std::collections::HashSet<String>,
) {
    match node.kind() {
        "class_definition" => {
            if let Some(name_node) = node.child_by_field_name("name") {
                if let Ok(name) = name_node.utf8_text(source.as_bytes()) {
                    defined_classes.insert(name.to_string());
                }
            }
            // Collect superclasses (argument_list of bases).
            if let Some(supercls) = node.child_by_field_name("superclasses") {
                extract_identifiers(supercls, source, bases, node.start_position().row + 1);
            }
        }
        "import_statement" | "import_from_statement" => {
            // Capture imported names (aliased imports included).
            extract_imported_names(node, source, imported_names);
        }
        _ => {}
    }
    for i in 0..node.child_count() {
        if let Some(child) = node.child(i) {
            walk_python(child, source, defined_classes, bases, imported_names);
        }
    }
}

#[cfg(feature = "treesitter")]
fn extract_identifiers(
    node: tree_sitter::Node,
    source: &str,
    out: &mut Vec<(String, usize)>,
    line: usize,
) {
    collect_identifiers(node, source, out, line);
}

#[cfg(feature = "treesitter")]
fn extract_imported_names(
    node: tree_sitter::Node,
    source: &str,
    out: &mut std::collections::HashSet<String>,
) {
    let kind = node.kind();
    if kind == "dotted_name" || kind == "identifier" {
        if let Ok(name) = node.utf8_text(source.as_bytes()) {
            let last = name.rsplit('.').next().unwrap_or(name);
            if last != "*" && !last.is_empty() {
                out.insert(last.to_string());
            }
        }
    }
    // Walk children by index (tree-sitter 0.25: no descendants() method, and
    // sharing a TreeCursor across recursion causes lifetime errors).
    for i in 0..node.child_count() {
        if let Some(child) = node.child(i) {
            extract_imported_names(child, source, out);
        }
    }
}
