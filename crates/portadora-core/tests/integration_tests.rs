use std::fs::{self, File};
use std::io::Write;
use std::os::unix::fs::PermissionsExt;

use portadora_core::{
    BlzReader, BlzWriter, Database, Dependencies, Manifest, PackageMeta, Triggers,
};
use tempfile::tempdir;

#[test]
fn test_blz_lifecycle_pack_install_verify_remove() -> anyhow::Result<()> {
    let temp = tempdir()?;
    let destdir = temp.path().join("destdir");
    fs::create_dir_all(destdir.join("usr/bin"))?;

    // Create a dummy binary file
    let binary_path = destdir.join("usr/bin/hello");
    {
        let mut f = File::create(&binary_path)?;
        f.write_all(b"#!/bin/sh\necho 'Hello BlazeOS!'\n")?;
        let mut perms = f.metadata()?.permissions();
        perms.set_mode(0o755);
        f.set_permissions(perms)?;
    }

    // Create a symlink
    let symlink_path = destdir.join("usr/bin/hi");
    std::os::unix::fs::symlink("hello", &symlink_path)?;

    // Create manifest
    let manifest = Manifest {
        package: PackageMeta {
            name: "hello-blaze".into(),
            version: "1.0.0".into(),
            release: 1,
            architecture: "x86_64".into(),
            summary: "Hello World package for BlazeOS".into(),
            description: "Test description".into(),
            license: "MIT".into(),
            maintainer: "Tester <test@blaze.org>".into(),
            url: "https://blazeos.org".into(),
            installed_size: 0,
        },
        dependencies: Dependencies {
            requires: vec!["bash".into()],
            provides: vec!["cmd:hello".into()],
            conflicts: vec![],
        },
        build: None,
        triggers: Triggers::default(),
        sysusers: None,
        tmpfiles: None,
        services: None,
    };

    let pkg_file = temp.path().join("hello-blaze-1.0.0-1.x86_64.blz");

    // 1. Pack
    let (final_manifest, files) = BlzWriter::create_package(&pkg_file, &manifest, &destdir, 3)?;
    assert_eq!(files.len(), 4); // usr (dir), usr/bin (dir), usr/bin/hello (file), usr/bin/hi (symlink)
    assert!(pkg_file.exists());

    // 2. Read package metadata without extracting
    let reader = BlzReader::open(&pkg_file)?;
    let read_manifest = reader.read_manifest()?;
    assert_eq!(read_manifest.package.name, "hello-blaze");
    let read_files = reader.read_files()?;
    assert_eq!(read_files.len(), 4);

    // 3. Install into a target rootfs
    let target_root = temp.path().join("target_root");
    fs::create_dir_all(&target_root)?;

    reader.extract_payload(&target_root)?;
    let installed_bin = target_root.join("usr/bin/hello");
    assert!(installed_bin.exists());

    // Verify permissions preserved
    let meta = fs::metadata(&installed_bin)?;
    assert_eq!(meta.permissions().mode() & 0o777, 0o755);

    // 4. Record into DB
    let db_path = target_root.join("var/lib/portadora/db.sqlite");
    let mut db = Database::open_or_create(&db_path)?;
    db.record_installed(&final_manifest, &files, &target_root)?;

    // 5. Query DB
    let pkgs = db.list_packages()?;
    assert_eq!(pkgs.len(), 1);
    assert_eq!(pkgs[0].name, "hello-blaze");

    // 6. Verify files - Clean state
    let issues = db.verify_files(&target_root, None)?;
    assert!(issues.is_empty(), "Issues found: {:?}", issues);

    // 7. Verify files - Tampered state
    {
        let mut f = File::create(&installed_bin)?;
        f.write_all(b"tampered content")?;
    }
    let issues = db.verify_files(&target_root, None)?;
    assert_eq!(issues.len(), 1);
    assert_eq!(issues[0].issue_type, "CHECKSUM_MISMATCH");

    // 8. Remove package
    db.remove_package("hello-blaze", &target_root)?;
    assert!(!installed_bin.exists());
    let pkgs_after = db.list_packages()?;
    assert!(pkgs_after.is_empty());

    Ok(())
}

#[test]
fn test_ownership_conflict_prevention() -> anyhow::Result<()> {
    let temp = tempdir()?;
    let db_path = temp.path().join("db.sqlite");
    let mut db = Database::open_or_create(&db_path)?;

    let manifest_a = Manifest {
        package: PackageMeta {
            name: "pkg-a".into(),
            version: "1.0.0".into(),
            release: 1,
            architecture: "x86_64".into(),
            summary: "Package A".into(),
            description: "".into(),
            license: "MIT".into(),
            maintainer: "".into(),
            url: "".into(),
            installed_size: 100,
        },
        dependencies: Dependencies::default(),
        build: None,
        triggers: Triggers::default(),
        sysusers: None,
        tmpfiles: None,
        services: None,
    };

    let files_a = vec![
        portadora_core::FileEntry {
            path: "usr/bin/shared_tool".into(),
            file_type: portadora_core::FileType::File,
            mode: "0755".into(),
            size: 100,
            sha256: Some("abcd".into()),
            symlink_target: None,
        }
    ];

    // Install package A
    db.record_installed(&manifest_a, &files_a, temp.path())?;

    // Now try to install package B owning the EXACT SAME file
    let manifest_b = Manifest {
        package: PackageMeta {
            name: "pkg-b".into(),
            version: "1.0.0".into(),
            release: 1,
            architecture: "x86_64".into(),
            summary: "Package B".into(),
            description: "".into(),
            license: "MIT".into(),
            maintainer: "".into(),
            url: "".into(),
            installed_size: 100,
        },
        dependencies: Dependencies::default(),
        build: None,
        triggers: Triggers::default(),
        sysusers: None,
        tmpfiles: None,
        services: None,
    };

    let files_b = vec![
        portadora_core::FileEntry {
            path: "usr/bin/shared_tool".into(),
            file_type: portadora_core::FileType::File,
            mode: "0755".into(),
            size: 100,
            sha256: Some("efgh".into()),
            symlink_target: None,
        }
    ];

    let result = db.record_installed(&manifest_b, &files_b, temp.path());
    assert!(result.is_err(), "Expected ownership conflict error!");
    let err_msg = result.unwrap_err().to_string();
    assert!(err_msg.contains("Package ownership conflict"), "Actual error: {}", err_msg);

    Ok(())
}

#[test]
fn test_verify_detects_missing_and_mode_changes() -> anyhow::Result<()> {
    let temp = tempdir()?;
    let root = temp.path().join("root");
    fs::create_dir_all(root.join("usr/bin"))?;

    let file_path = root.join("usr/bin/tool");
    {
        let mut f = File::create(&file_path)?;
        f.write_all(b"code")?;
        let mut perms = f.metadata()?.permissions();
        perms.set_mode(0o755);
        f.set_permissions(perms)?;
    }

    let db_path = root.join("var/lib/portadora/db.sqlite");
    let mut db = Database::open_or_create(&db_path)?;

    let manifest = Manifest {
        package: PackageMeta {
            name: "test-pkg".into(),
            version: "1.0.0".into(),
            release: 1,
            architecture: "x86_64".into(),
            summary: "".into(),
            description: "".into(),
            license: "".into(),
            maintainer: "".into(),
            url: "".into(),
            installed_size: 4,
        },
        dependencies: Dependencies::default(),
        build: None,
        triggers: Triggers::default(),
        sysusers: None,
        tmpfiles: None,
        services: None,
    };

    let files = vec![
        portadora_core::FileEntry {
            path: "usr/bin/tool".into(),
            file_type: portadora_core::FileType::File,
            mode: "0755".into(),
            size: 4,
            sha256: Some("5694d08a2e53ffcae0c3103e5ad6f6076abd960eb1f8a56577040bc1028f702b".into()),
            symlink_target: None,
        }
    ];

    db.record_installed(&manifest, &files, &root)?;

    // 1. Clean check
    let issues = db.verify_files(&root, None)?;
    assert!(issues.is_empty());

    // 2. Mode mismatch check (chmod 0644)
    {
        let mut perms = fs::metadata(&file_path)?.permissions();
        perms.set_mode(0o644);
        fs::set_permissions(&file_path, perms)?;
    }
    let issues = db.verify_files(&root, None)?;
    assert_eq!(issues.len(), 1);
    assert_eq!(issues[0].issue_type, "MODE_MISMATCH");

    // 3. Missing file check
    fs::remove_file(&file_path)?;
    let issues = db.verify_files(&root, None)?;
    assert_eq!(issues.len(), 1);
    assert_eq!(issues[0].issue_type, "MISSING");

    Ok(())
}
