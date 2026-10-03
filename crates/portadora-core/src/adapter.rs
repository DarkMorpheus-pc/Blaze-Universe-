use std::path::Path;
use anyhow::Result;

/// Future interface specification for Foreign Package Adapters (.deb, .rpm)
/// Note: Implementation is strictly postponed until after Milestone 1.

#[derive(Debug, Clone)]
pub struct ForeignPackageInfo {
    pub name: String,
    pub version: String,
    pub release: String,
    pub architecture: String,
    pub summary: String,
    pub format: String, // "deb" or "rpm"
}

#[derive(Debug, Clone)]
pub struct ElfRequirement {
    pub binary_path: String,
    pub needed_sonames: Vec<String>,
    pub required_glibc_versions: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum CapabilityResolution {
    /// All SONAMEs and glibc symbols are natively available in Blaze Base.
    /// Install directly as native binaries without modifications.
    CompatibleNative,

    /// Minor path or loader differences that can be safely normalized/translated.
    Translatable {
        reason: String,
    },

    /// Hard ABI mismatch (incompatible libc version or missing proprietary libraries).
    /// Must run inside an isolated Bubblewrap / OverlayFS capsule.
    CapsuleRequired {
        reason: String,
    },
}

pub trait ForeignPackageAdapter {
    /// Returns true if this adapter can handle the given foreign archive file.
    fn can_handle(&self, path: &Path) -> bool;

    /// Parses package metadata without extracting or installing.
    fn parse_metadata(&self, path: &Path) -> Result<ForeignPackageInfo>;

    /// Scans the internal ELF binaries inside the foreign archive for SONAME requirements.
    fn inspect_elf_requirements(&self, path: &Path) -> Result<Vec<ElfRequirement>>;
}
