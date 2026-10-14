use anyhow::{bail, Context, Result};
use serde::{Deserialize, Serialize};
use std::fs::{self, File};
use std::io::Write;
use std::os::unix::fs::symlink;
use std::os::unix::fs::PermissionsExt;
use std::path::{Component, Path};
use std::process::{Command, Stdio};

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct InstallAnswers {
    pub hostname: String,
    pub locale: String,
    pub timezone: String,
    pub keyboard_layout: String,
    pub username: String,
    pub full_name: String,
}

impl InstallAnswers {
    pub fn load(path: &Path) -> Result<Self> {
        let data = fs::read(path)
            .with_context(|| format!("reading installer answers from {}", path.display()))?;
        let answers: Self = serde_json::from_slice(&data)
            .with_context(|| format!("parsing installer answers from {}", path.display()))?;
        answers.validate_syntax()?;
        Ok(answers)
    }

    pub fn validate_syntax(&self) -> Result<()> {
        validate_hostname(&self.hostname)?;
        validate_username(&self.username)?;
        validate_full_name(&self.full_name)?;
        validate_token("locale", &self.locale, "_.@-")?;
        validate_token("keyboard layout", &self.keyboard_layout, "_-")?;
        validate_relative_path("timezone", &self.timezone)?;
        Ok(())
    }

    pub fn validate_resources(&self, root: &Path) -> Result<()> {
        self.validate_syntax()?;
        let locale_source = self
            .locale
            .split(['.', '@'])
            .next()
            .context("locale has no source name")?;
        require_file(
            &root.join("usr/share/i18n/locales").join(locale_source),
            "locale source",
        )?;
        require_file(
            &root.join("usr/share/zoneinfo").join(&self.timezone),
            "time zone",
        )?;
        require_file(
            &root
                .join("usr/share/X11/xkb/symbols")
                .join(&self.keyboard_layout),
            "XKB keyboard layout",
        )?;
        Ok(())
    }
}

pub fn validate_password(password: &[u8]) -> Result<()> {
    if password.len() < 8 {
        bail!("password must contain at least 8 bytes");
    }
    if password.len() > 1024 {
        bail!("password exceeds the 1024-byte safety limit");
    }
    if password
        .iter()
        .any(|byte| matches!(byte, b'\0' | b'\n' | b'\r' | b':'))
    {
        bail!("password contains a character unsupported by chpasswd input");
    }
    Ok(())
}

pub fn apply(root: &Path, answers: &InstallAnswers, password: &[u8]) -> Result<()> {
    answers.validate_resources(root)?;
    validate_password(password)?;

    configure_locale(root, &answers.locale)?;
    atomic_write(
        &root.join("etc/hostname"),
        format!("{}\n", answers.hostname).as_bytes(),
    )?;
    atomic_write(
        &root.join("etc/locale.conf"),
        format!("LANG={}\n", answers.locale).as_bytes(),
    )?;
    atomic_write(
        &root.join("etc/vconsole.conf"),
        format!(
            "KEYMAP={}\nXKBLAYOUT={}\n",
            console_keymap(&answers.keyboard_layout),
            answers.keyboard_layout
        )
        .as_bytes(),
    )?;
    replace_symlink(
        &root.join("etc/localtime"),
        Path::new("../usr/share/zoneinfo")
            .join(&answers.timezone)
            .as_path(),
    )?;

    configure_account(root, answers, password)?;
    configure_niri(root, answers)?;
    configure_runtime_rules(root, answers)?;
    Ok(())
}

fn configure_locale(root: &Path, locale: &str) -> Result<()> {
    let source = locale
        .split(['.', '@'])
        .next()
        .context("locale has no source name")?;
    let i18n_path = root.join("usr/share/i18n");
    let result = Command::new(root.join("usr/bin/localedef"))
        .arg(format!("--prefix={}", root.display()))
        .arg("--no-archive")
        .args(["-i", source, "-f", "UTF-8", locale])
        .env("I18NPATH", &i18n_path)
        .output()
        .context("running localedef for the installed system")?;
    if !result.status.success() {
        bail!(
            "localedef failed: {}",
            String::from_utf8_lossy(&result.stderr).trim()
        );
    }
    Ok(())
}

fn configure_account(root: &Path, answers: &InstallAnswers, password: &[u8]) -> Result<()> {
    if answers.username != "blaze" {
        let root_s = root.to_str().context("installed root is not valid UTF-8")?;
        let home = format!("/home/{}", answers.username);
        run_checked(
            &root.join("usr/bin/usermod"),
            &[
                "--root",
                root_s,
                "--login",
                &answers.username,
                "--home",
                &home,
                "--move-home",
                "--comment",
                &answers.full_name,
                "blaze",
            ],
        )?;
    } else {
        update_gecos(root, &answers.full_name)?;
    }

    let root_s = root.to_str().context("installed root is not valid UTF-8")?;
    let mut payload = Vec::with_capacity(answers.username.len() + password.len() + 2);
    payload.extend_from_slice(answers.username.as_bytes());
    payload.push(b':');
    payload.extend_from_slice(password);
    payload.push(b'\n');
    let result = run_checked_with_input(
        &root.join("usr/bin/chpasswd"),
        &["--root", root_s, "--crypt-method", "SHA512"],
        &payload,
    );
    payload.fill(0);
    result?;

    // SquashFS is intentionally generated with a single root owner. Restore
    // ownership here rather than relying on tmpfiles during the first boot, so
    // the account is usable even in recovery mode before systemd finishes.
    let home = format!("{root_s}/home/{}", answers.username);
    run_checked(
        &root.join("usr/bin/chown"),
        &["--recursive", "--no-dereference", "1000:1000", &home],
    )
}

fn update_gecos(root: &Path, full_name: &str) -> Result<()> {
    let path = root.join("etc/passwd");
    let content = fs::read_to_string(&path)?;
    let mut found = false;
    let mut output = String::new();
    for line in content.lines() {
        let mut fields = line.split(':').collect::<Vec<_>>();
        if fields.first() == Some(&"blaze") {
            if fields.len() != 7 {
                bail!("invalid blaze entry in /etc/passwd");
            }
            fields[4] = full_name;
            found = true;
        }
        output.push_str(&fields.join(":"));
        output.push('\n');
    }
    if !found {
        bail!("the template blaze user is missing from /etc/passwd");
    }
    atomic_write(&path, output.as_bytes())
}

fn configure_niri(root: &Path, answers: &InstallAnswers) -> Result<()> {
    let layout = format!("{},us", answers.keyboard_layout);
    for path in [
        root.join("etc/niri/config.kdl"),
        root.join("home")
            .join(&answers.username)
            .join(".config/niri/config.kdl"),
    ] {
        if !path.is_file() {
            continue;
        }
        let content = fs::read_to_string(&path)?;
        let mut replaced = false;
        let mut output = String::new();
        for line in content.lines() {
            if !replaced && line.trim_start().starts_with("layout \"") {
                let indentation = &line[..line.len() - line.trim_start().len()];
                output.push_str(indentation);
                output.push_str(&format!("layout \"{layout}\"\n"));
                replaced = true;
            } else {
                output.push_str(line);
                output.push('\n');
            }
        }
        if !replaced {
            bail!("Niri XKB layout entry is missing: {}", path.display());
        }
        atomic_write(&path, output.as_bytes())?;
    }
    Ok(())
}

fn configure_runtime_rules(root: &Path, answers: &InstallAnswers) -> Result<()> {
    let username = &answers.username;
    let home = format!("/home/{username}");
    let tmpfiles = format!(
        "d /run/user/1000 0700 {username} blaze -\n\
         Z {home} 0755 {username} blaze -\n\
         d {home}/.config 0755 {username} blaze -\n\
         d {home}/.local 0755 {username} blaze -\n\
         d {home}/.local/state 0755 {username} blaze -\n\
         d {home}/.local/state/noctalia 0755 {username} blaze -\n\
         d {home}/.local/share 0755 {username} blaze -\n\
         d {home}/.cache 0755 {username} blaze -\n"
    );
    atomic_write(
        &root.join("usr/lib/tmpfiles.d/blaze-user.conf"),
        tmpfiles.as_bytes(),
    )?;

    let getty = root.join("etc/systemd/system/getty@tty1.service.d/autologin.conf");
    let content = fs::read_to_string(&getty)?;
    let configured = content.replace("--autologin blaze ", &format!("--autologin {username} "));
    if configured == content && username != "blaze" {
        bail!("tty1 autologin template did not contain the blaze user");
    }
    atomic_write(&getty, configured.as_bytes())?;

    let seatd = root.join("usr/lib/systemd/system/seatd.service");
    let content = fs::read_to_string(&seatd)?;
    let configured = content.replace("-u blaze -g blaze", &format!("-u {username} -g blaze"));
    if configured == content && username != "blaze" {
        bail!("seatd service template did not contain the blaze user");
    }
    atomic_write(&seatd, configured.as_bytes())
}

fn replace_symlink(path: &Path, target: &Path) -> Result<()> {
    match fs::symlink_metadata(path) {
        Ok(_) => fs::remove_file(path)?,
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => {}
        Err(error) => return Err(error.into()),
    }
    symlink(target, path)?;
    File::open(path.parent().context("symlink has no parent")?)?.sync_all()?;
    Ok(())
}

fn atomic_write(path: &Path, data: &[u8]) -> Result<()> {
    let parent = path.parent().context("configuration path has no parent")?;
    fs::create_dir_all(parent)?;
    let temporary = path.with_extension("solar-installer-new");
    let mut file = File::create(&temporary)?;
    file.set_permissions(fs::Permissions::from_mode(0o644))?;
    file.write_all(data)?;
    file.sync_all()?;
    fs::rename(&temporary, path)?;
    File::open(parent)?.sync_all()?;
    Ok(())
}

fn run_checked(program: &Path, args: &[&str]) -> Result<()> {
    let result = Command::new(program).args(args).output()?;
    if !result.status.success() {
        bail!(
            "{} failed: {}",
            program.display(),
            String::from_utf8_lossy(&result.stderr).trim()
        );
    }
    Ok(())
}

fn run_checked_with_input(program: &Path, args: &[&str], input: &[u8]) -> Result<()> {
    let mut child = Command::new(program)
        .args(args)
        .stdin(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()?;
    child
        .stdin
        .take()
        .context("opening configuration command stdin")?
        .write_all(input)?;
    let result = child.wait_with_output()?;
    if !result.status.success() {
        bail!(
            "{} failed: {}",
            program.display(),
            String::from_utf8_lossy(&result.stderr).trim()
        );
    }
    Ok(())
}

fn require_file(path: &Path, description: &str) -> Result<()> {
    if !path.is_file() {
        bail!("unsupported {description}: {}", path.display());
    }
    Ok(())
}

fn validate_hostname(hostname: &str) -> Result<()> {
    if hostname.is_empty() || hostname.len() > 253 {
        bail!("hostname must contain between 1 and 253 ASCII characters");
    }
    for label in hostname.split('.') {
        if label.is_empty()
            || label.len() > 63
            || label.starts_with('-')
            || label.ends_with('-')
            || !label
                .bytes()
                .all(|byte| byte.is_ascii_alphanumeric() || byte == b'-')
        {
            bail!("hostname contains an invalid DNS label");
        }
    }
    Ok(())
}

fn validate_username(username: &str) -> Result<()> {
    if username.is_empty() || username.len() > 32 || username == "root" {
        bail!("username must contain 1-32 characters and cannot be root");
    }
    let mut bytes = username.bytes();
    let first = bytes.next().context("username is empty")?;
    if !(first.is_ascii_lowercase() || first == b'_')
        || !bytes
            .all(|byte| byte.is_ascii_lowercase() || byte.is_ascii_digit() || b"_-".contains(&byte))
    {
        bail!("username must match [a-z_][a-z0-9_-]*");
    }
    Ok(())
}

fn validate_full_name(full_name: &str) -> Result<()> {
    if full_name.is_empty()
        || full_name.len() > 64
        || full_name
            .chars()
            .any(|character| character.is_control() || character == ':')
    {
        bail!("full name must contain 1-64 printable characters without ':'");
    }
    Ok(())
}

fn validate_token(name: &str, value: &str, punctuation: &str) -> Result<()> {
    if value.is_empty()
        || value.len() > 64
        || !value
            .chars()
            .all(|character| character.is_ascii_alphanumeric() || punctuation.contains(character))
    {
        bail!("{name} contains unsupported characters");
    }
    Ok(())
}

fn validate_relative_path(name: &str, value: &str) -> Result<()> {
    if value.is_empty()
        || value.len() > 128
        || Path::new(value).is_absolute()
        || Path::new(value)
            .components()
            .any(|component| !matches!(component, Component::Normal(_)))
    {
        bail!("{name} must be a normalized relative path");
    }
    validate_token(name, &value.replace('/', ""), "+_-")
}

fn console_keymap(layout: &str) -> &str {
    match layout {
        "tr" => "trq",
        "us" => "us",
        "de" => "de-latin1",
        "fr" => "fr-latin9",
        "gb" => "uk",
        other => other,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    fn valid_answers() -> InstallAnswers {
        InstallAnswers {
            hostname: "blaze-workstation".into(),
            locale: "tr_TR.UTF-8".into(),
            timezone: "Europe/Istanbul".into(),
            keyboard_layout: "tr".into(),
            username: "morpheus".into(),
            full_name: "Dark Morpheus".into(),
        }
    }

    #[test]
    fn rejects_path_traversal_and_unsafe_identity_fields() {
        let mut answers = valid_answers();
        answers.timezone = "../etc/shadow".into();
        assert!(answers.validate_syntax().is_err());
        answers = valid_answers();
        answers.username = "Root User".into();
        assert!(answers.validate_syntax().is_err());
        answers = valid_answers();
        answers.hostname = "-invalid.example".into();
        assert!(answers.validate_syntax().is_err());
    }

    #[test]
    fn validates_resources_inside_the_target_root() {
        let root = tempdir().unwrap();
        for path in [
            "usr/share/i18n/locales/tr_TR",
            "usr/share/zoneinfo/Europe/Istanbul",
            "usr/share/X11/xkb/symbols/tr",
        ] {
            let path = root.path().join(path);
            fs::create_dir_all(path.parent().unwrap()).unwrap();
            fs::write(path, b"fixture").unwrap();
        }
        valid_answers().validate_resources(root.path()).unwrap();
    }

    #[test]
    fn password_never_accepts_line_or_field_injection() {
        assert!(validate_password(b"correct horse battery staple").is_ok());
        assert!(validate_password(b"short").is_err());
        assert!(validate_password(b"password\nroot:hijack").is_err());
        assert!(validate_password(b"password:field").is_err());
    }
}
