use std::collections::{HashMap, HashSet, VecDeque};

use anyhow::{bail, Context, Result};
use crate::tuf::{TargetsMetadata, TargetFile};

#[derive(Debug, Clone)]
pub struct DependencyNode {
    pub name: String,
    pub version: String,
    pub release: u32,
    pub requires: Vec<String>,
    pub provides: Vec<String>,
    pub conflicts: Vec<String>,
    pub replaces: Vec<String>,
    pub filename: String,
    pub target_file: TargetFile,
}

pub struct DependencyResolver<'a> {
    pub targets: &'a TargetsMetadata,
    pub installed: HashSet<String>,
    pub installed_provides: HashMap<String, String>, // capability -> providing_package
}

impl<'a> DependencyResolver<'a> {
    pub fn new(
        targets: &'a TargetsMetadata,
        installed: HashSet<String>,
        installed_provides: HashMap<String, String>,
    ) -> Self {
        Self {
            targets,
            installed,
            installed_provides,
        }
    }

    pub fn resolve(&self, requested_packages: &[String]) -> Result<Vec<DependencyNode>> {
        let mut resolved_map: HashMap<String, DependencyNode> = HashMap::new();
        let mut queue: VecDeque<String> = VecDeque::new();
        let mut visited: HashSet<String> = HashSet::new();

        // 1. Build capability -> target filename mapping
        let mut cap_map: HashMap<String, (String, DependencyNode)> = HashMap::new();
        for (filename, target_file) in &self.targets.targets {
            if let Some(ref custom) = target_file.custom {
                let node = DependencyNode {
                    name: custom.name.clone(),
                    version: custom.version.clone(),
                    release: custom.release,
                    requires: custom.requires.clone(),
                    provides: custom.provides.clone(),
                    conflicts: custom.conflicts.clone(),
                    replaces: custom.replaces.clone(),
                    filename: filename.clone(),
                    target_file: target_file.clone(),
                };
                let should_insert = match cap_map.get(&custom.name) {
                    Some((_, existing)) => is_node_newer(&node, existing),
                    None => true,
                };
                if should_insert {
                    cap_map.insert(custom.name.clone(), (filename.clone(), node.clone()));
                }
                for prov in &custom.provides {
                    let cap_name = prov.split_whitespace().next().unwrap_or(prov).to_string();
                    let should_insert_cap = match cap_map.get(&cap_name) {
                        Some((_, existing)) => is_node_newer(&node, existing),
                        None => true,
                    };
                    if should_insert_cap {
                        cap_map.insert(cap_name, (filename.clone(), node.clone()));
                    }
                }
            }
        }

        // 2. Enqueue requested packages
        for req in requested_packages {
            queue.push_back(req.clone());
        }

        while let Some(current_req) = queue.pop_front() {
            let cap_name = current_req.split_whitespace().next().unwrap_or(&current_req);
            
            // Check if already installed
            if self.installed.contains(cap_name) || self.installed_provides.contains_key(cap_name) {
                // If explicitly requested, install or upgrade
                if requested_packages.contains(&current_req) {
                    // fallthrough to find in cap_map
                } else {
                    continue;
                }
            }

            if visited.contains(cap_name) {
                continue;
            }

            let (_filename, node) = cap_map.get(cap_name)
                .with_context(|| format!("Unresolvable dependency: cannot find package or capability '{}'", cap_name))?;

            visited.insert(node.name.clone());
            visited.insert(cap_name.to_string());

            // Check conflicts against already selected and installed
            for conflict in &node.conflicts {
                let conf_name = conflict.split_whitespace().next().unwrap_or(conflict);
                if self.installed.contains(conf_name) && !node.replaces.contains(&conf_name.to_string()) {
                    bail!("PackageConflictError: '{}' conflicts with installed package '{}'", node.name, conf_name);
                }
                if resolved_map.contains_key(conf_name) {
                    bail!("PackageConflictError: cannot install mutually conflicting packages '{}' and '{}'", node.name, conf_name);
                }
            }

            for dep in &node.requires {
                let dep_cap = dep.split_whitespace().next().unwrap_or(dep);
                if !visited.contains(dep_cap) && !self.installed.contains(dep_cap) && !self.installed_provides.contains_key(dep_cap) {
                    queue.push_back(dep.clone());
                }
            }

            resolved_map.insert(node.name.clone(), node.clone());
        }

        // 3. Cycle Detection & Topological Sorting
        let mut adj: HashMap<String, Vec<String>> = HashMap::new();
        for (pkg_name, node) in &resolved_map {
            let mut edges = Vec::new();
            for req in &node.requires {
                let req_cap = req.split_whitespace().next().unwrap_or(req);
                if let Some((_, dep_node)) = cap_map.get(req_cap) {
                    if resolved_map.contains_key(&dep_node.name) && dep_node.name != *pkg_name {
                        edges.push(dep_node.name.clone());
                    }
                }
            }
            adj.insert(pkg_name.clone(), edges);
        }

        // Cycle check using DFS colors
        // 0 = unvisited, 1 = visiting, 2 = visited
        let mut color: HashMap<String, u8> = HashMap::new();
        let mut path: Vec<String> = Vec::new();
        for node in resolved_map.keys() {
            if color.get(node).copied().unwrap_or(0) == 0 {
                dfs_cycle(node, &adj, &mut color, &mut path)?;
            }
        }

        // Topological Sort (dependencies before dependents)
        let mut visited_sort = HashSet::new();
        let mut ordered_names = Vec::new();
        for node in resolved_map.keys() {
            if !visited_sort.contains(node) {
                topo_sort(node, &adj, &mut visited_sort, &mut ordered_names);
            }
        }

        let mut result = Vec::new();
        for name in ordered_names {
            if let Some(node) = resolved_map.get(&name) {
                result.push(node.clone());
            }
        }

        Ok(result)
    }
}

fn dfs_cycle(
    u: &str,
    adj: &HashMap<String, Vec<String>>,
    color: &mut HashMap<String, u8>,
    path: &mut Vec<String>,
) -> Result<()> {
    color.insert(u.to_string(), 1);
    path.push(u.to_string());

    if let Some(neighbors) = adj.get(u) {
        for v in neighbors {
            let c = color.get(v).copied().unwrap_or(0);
            if c == 1 {
                path.push(v.to_string());
                bail!("DependencyCycleDetected: circular dependency found: {}", path.join(" -> "));
            } else if c == 0 {
                dfs_cycle(v, adj, color, path)?;
            }
        }
    }

    path.pop();
    color.insert(u.to_string(), 2);
    Ok(())
}

fn topo_sort(
    u: &str,
    adj: &HashMap<String, Vec<String>>,
    visited: &mut HashSet<String>,
    result: &mut Vec<String>,
) {
    visited.insert(u.to_string());
    if let Some(neighbors) = adj.get(u) {
        for v in neighbors {
            if !visited.contains(v) {
                topo_sort(v, adj, visited, result);
            }
        }
    }
    result.push(u.to_string());
}

fn is_node_newer(candidate: &DependencyNode, existing: &DependencyNode) -> bool {
    is_version_release_newer(
        &candidate.version,
        candidate.release,
        &existing.version,
        existing.release,
    )
}

pub fn is_version_release_newer(
    candidate_version: &str,
    candidate_release: u32,
    current_version: &str,
    current_release: u32,
) -> bool {
    match compare_versions(candidate_version, current_version) {
        std::cmp::Ordering::Greater => true,
        std::cmp::Ordering::Less => false,
        std::cmp::Ordering::Equal => candidate_release > current_release,
    }
}

pub fn compare_versions(v1: &str, v2: &str) -> std::cmp::Ordering {
    let p1: Vec<u64> = v1.split('.').filter_map(|s| s.parse().ok()).collect();
    let p2: Vec<u64> = v2.split('.').filter_map(|s| s.parse().ok()).collect();
    for (a, b) in p1.iter().zip(p2.iter()) {
        if a != b {
            return a.cmp(b);
        }
    }
    p1.len().cmp(&p2.len())
}

#[cfg(test)]
mod version_tests {
    use super::*;

    #[test]
    fn upgrades_only_to_a_strictly_newer_version_release_pair() {
        assert!(is_version_release_newer("2.0.0", 1, "1.9.9", 9));
        assert!(is_version_release_newer("1.0.0", 2, "1.0.0", 1));
        assert!(!is_version_release_newer("1.0.0", 1, "1.0.0", 1));
        assert!(!is_version_release_newer("1.0.0", 99, "2.0.0", 1));
        assert!(!is_version_release_newer("6.8.12", 9, "7.2.8", 1));
    }
}
