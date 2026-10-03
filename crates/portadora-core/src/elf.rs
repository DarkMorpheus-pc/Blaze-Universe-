use std::fs::File;
use std::io::Read;
use std::path::Path;

use anyhow::Result;
use goblin::elf::Elf;

#[derive(Debug, Clone, Default)]
pub struct ElfInfo {
    pub is_elf: bool,
    pub is_shared_lib: bool,
    pub is_executable: bool,
    pub architecture: String,
    pub soname: Option<String>,
    pub needed: Vec<String>,
    pub interpreter: Option<String>,
}

pub fn scan_elf<P: AsRef<Path>>(path: P) -> Result<Option<ElfInfo>> {
    let path = path.as_ref();
    let mut file = match File::open(path) {
        Ok(f) => f,
        Err(_) => return Ok(None),
    };

    let mut buffer = Vec::new();
    file.read_to_end(&mut buffer)?;

    if buffer.len() < 4 || &buffer[0..4] != b"\x7fELF" {
        return Ok(None);
    }

    let elf = match Elf::parse(&buffer) {
        Ok(e) => e,
        Err(_) => return Ok(None),
    };

    let arch = match elf.header.e_machine {
        goblin::elf::header::EM_X86_64 => "x86_64",
        goblin::elf::header::EM_AARCH64 => "aarch64",
        goblin::elf::header::EM_386 => "i686",
        _ => "unknown",
    };

    let soname = elf.soname.map(|s| s.to_string());
    let needed: Vec<String> = elf.libraries.into_iter().map(|s| s.to_string()).collect();
    let interpreter = elf.interpreter.map(|s| s.to_string());

    let is_shared_lib = elf.header.e_type == goblin::elf::header::ET_DYN && soname.is_some();
    let is_executable = elf.header.e_type == goblin::elf::header::ET_EXEC
        || (elf.header.e_type == goblin::elf::header::ET_DYN && interpreter.is_some());

    Ok(Some(ElfInfo {
        is_elf: true,
        is_shared_lib,
        is_executable,
        architecture: arch.to_string(),
        soname,
        needed,
        interpreter,
    }))
}
