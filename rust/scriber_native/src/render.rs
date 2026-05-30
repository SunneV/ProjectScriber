use pyo3::prelude::*;
use std::collections::BTreeMap;

#[derive(Default)]
struct TreeNode {
    children: BTreeMap<String, TreeNode>,
}

fn walk(node: &TreeNode, prefix: &str) -> Vec<String> {
    let mut lines = Vec::new();
    let items: Vec<(&String, &TreeNode)> = node.children.iter().collect();
    for (index, (name, child)) in items.iter().enumerate() {
        let is_last = index == items.len() - 1;
        let branch = if is_last { "└── " } else { "├── " };
        lines.push(format!("{}{}{}", prefix, branch, name));
        let extension = if is_last { "    " } else { "│   " };
        lines.extend(walk(child, &format!("{}{}", prefix, extension)));
    }
    lines
}

#[pyfunction]
pub fn render_tree(paths: Vec<String>) -> PyResult<String> {
    let mut root = TreeNode::default();
    for path_str in paths {
        let mut curr = &mut root;
        // Support both backslash and forward slash
        let clean_path = path_str.replace("\\", "/");
        for part in clean_path.split('/') {
            if part.is_empty() || part == "." {
                continue;
            }
            curr = curr.children.entry(part.to_string()).or_default();
        }
    }

    if root.children.is_empty() {
        Ok(".".to_string())
    } else {
        Ok(format!(".\n{}", walk(&root, "").join("\n")))
    }
}
