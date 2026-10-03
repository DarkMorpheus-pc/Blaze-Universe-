use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Manifest {
    pub package: PackageMeta,
    #[serde(default)]
    pub dependencies: Dependencies,
    #[serde(default)]
    pub build: Option<BuildMeta>,
    #[serde(default)]
    pub triggers: Triggers,
    #[serde(default)]
    pub sysusers: Option<SysusersConfig>,
    #[serde(default)]
    pub tmpfiles: Option<TmpfilesConfig>,
    #[serde(default)]
    pub services: Option<ServicesConfig>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct PackageMeta {
    pub name: String,
    pub version: String,
    pub release: u32,
    pub architecture: String,
    pub summary: String,
    #[serde(default)]
    pub description: String,
    #[serde(default)]
    pub license: String,
    #[serde(default)]
    pub maintainer: String,
    #[serde(default)]
    pub url: String,
    #[serde(default)]
    pub installed_size: u64,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize, PartialEq)]
pub struct Dependencies {
    #[serde(default)]
    pub requires: Vec<String>,
    #[serde(default)]
    pub provides: Vec<String>,
    #[serde(default)]
    pub conflicts: Vec<String>,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize, PartialEq)]
pub struct BuildMeta {
    #[serde(default)]
    pub builder: String,
    #[serde(default)]
    pub timestamp: u64,
    #[serde(default)]
    pub source_url: String,
    #[serde(default)]
    pub source_sha256: String,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize, PartialEq)]
pub struct Triggers {
    #[serde(default)]
    pub run_ldconfig: bool,
    #[serde(default)]
    pub update_icon_cache: bool,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize, PartialEq)]
pub struct SysusersConfig {
    #[serde(default)]
    pub files: Vec<String>,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize, PartialEq)]
pub struct TmpfilesConfig {
    #[serde(default)]
    pub files: Vec<String>,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize, PartialEq)]
pub struct ServicesConfig {
    #[serde(default)]
    pub preset: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum FileType {
    #[serde(rename = "file")]
    File,
    #[serde(rename = "dir")]
    Directory,
    #[serde(rename = "symlink")]
    Symlink,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct FileEntry {
    pub path: String,
    pub file_type: FileType,
    pub mode: String, // e.g. "0755"
    pub size: u64,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub sha256: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub symlink_target: Option<String>,
}

impl Manifest {
    pub fn from_toml(content: &str) -> anyhow::Result<Self> {
        Ok(toml::from_str(content)?)
    }

    pub fn to_toml(&self) -> anyhow::Result<String> {
        Ok(toml::to_string_pretty(self)?)
    }
}
