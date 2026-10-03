use serde::{Deserialize, Serialize};
use std::path::Path;
use anyhow::{Context, Result};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Recipe {
    pub package: RecipePackage,
    #[serde(default)]
    pub source: Option<RecipeSource>,
    #[serde(default)]
    pub dependencies: RecipeDependencies,
    #[serde(default)]
    pub sysusers: Option<portadora_core::manifest::SysusersConfig>,
    #[serde(default)]
    pub tmpfiles: Option<portadora_core::manifest::TmpfilesConfig>,
    #[serde(default)]
    pub services: Option<portadora_core::manifest::ServicesConfig>,
    pub build: RecipeBuild,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RecipePackage {
    pub name: String,
    pub version: String,
    pub release: u32,
    #[serde(default = "default_arch")]
    pub architecture: String,
    pub summary: String,
    #[serde(default)]
    pub description: String,
    #[serde(default)]
    pub license: String,
    #[serde(default = "default_maintainer")]
    pub maintainer: String,
    #[serde(default)]
    pub url: String,
}

fn default_arch() -> String {
    "x86_64".into()
}

fn default_maintainer() -> String {
    "BlazeOS Core Team <core@blazeos.org>".into()
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RecipeSource {
    pub url: String,
    pub sha256: String,
    #[serde(default)]
    pub filename: Option<String>,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct RecipeDependencies {
    #[serde(default)]
    pub requires: Vec<String>,
    #[serde(default)]
    pub provides: Vec<String>,
    #[serde(default)]
    pub conflicts: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RecipeBuild {
    pub script: String,
}

impl Recipe {
    pub fn load_from_file<P: AsRef<Path>>(path: P) -> Result<Self> {
        let content = std::fs::read_to_string(path.as_ref())
            .with_context(|| format!("Failed to read recipe at {}", path.as_ref().display()))?;
        let recipe: Recipe = toml::from_str(&content)
            .with_context(|| "Failed to parse recipe TOML")?;
        Ok(recipe)
    }
}
