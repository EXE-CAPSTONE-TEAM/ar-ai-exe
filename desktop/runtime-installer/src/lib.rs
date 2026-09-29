//! Installs a zipped runtime dependency (the Blender preview renderer) for the desktop shell:
//! stream the archive to disk while hashing it, refuse it unless the SHA-256 matches, unpack it
//! into a staging directory and only then swap it into place. Progress is reported through a
//! callback so the shell can drive a progress bar.

use sha2::{Digest, Sha256};
use std::{
    fmt, fs,
    io::{self, Read, Write},
    path::{Path, PathBuf},
    time::Duration,
};

/// Read/write chunk for the download and unpack loops.
const CHUNK_BYTES: usize = 256 * 1024;
/// Report at most ~200 steps per stage (0.5 %), but never less than every 1 MiB, so a
/// ~400 MB download emits a few hundred events rather than one per chunk.
const REPORT_STEPS: u64 = 200;
const MIN_REPORT_BYTES: u64 = 1024 * 1024;
const CONNECT_TIMEOUT: Duration = Duration::from_secs(30);
/// Longest silence tolerated between two reads of the body before the download is abandoned.
const READ_TIMEOUT: Duration = Duration::from_secs(60);

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Stage {
    Downloading,
    Verifying,
    Extracting,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Progress {
    pub stage: Stage,
    pub done: u64,
    /// 0 when the server did not announce a length.
    pub total: u64,
}

impl Progress {
    pub fn percent(&self) -> u8 {
        if self.total == 0 {
            return 0;
        }
        ((self.done.min(self.total) * 100) / self.total) as u8
    }
}

#[derive(Debug)]
pub enum InstallError {
    Http(String),
    Io(io::Error),
    Checksum { expected: String, actual: String },
    Archive(String),
    UnsafePath(String),
    MissingExecutable(PathBuf),
}

impl fmt::Display for InstallError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Http(message) => write!(f, "download failed: {message}"),
            Self::Io(error) => write!(f, "file error: {error}"),
            Self::Checksum { expected, actual } => {
                write!(f, "checksum mismatch: expected {expected}, got {actual}")
            }
            Self::Archive(message) => write!(f, "invalid archive: {message}"),
            Self::UnsafePath(name) => write!(f, "archive entry escapes the install folder: {name}"),
            Self::MissingExecutable(path) => {
                write!(f, "archive did not contain {}", path.display())
            }
        }
    }
}

impl std::error::Error for InstallError {}

impl From<io::Error> for InstallError {
    fn from(error: io::Error) -> Self {
        Self::Io(error)
    }
}

pub struct Artifact<'a> {
    pub url: &'a str,
    /// Lower- or upper-case hex SHA-256 of the zip.
    pub sha256: &'a str,
}

/// Download (or reuse an already verified) `artifact` at `download_path`, unpack it to
/// `install_root` and return the path of `exe_relative` inside it.
///
/// `install_root` is replaced only after the new tree is fully unpacked and contains the
/// executable, so a failed or interrupted install never leaves a half-written renderer behind.
/// The archive is deleted after a successful install.
pub fn install_zip(
    artifact: &Artifact<'_>,
    download_path: &Path,
    install_root: &Path,
    exe_relative: &Path,
    on_progress: &mut dyn FnMut(Progress),
) -> Result<PathBuf, InstallError> {
    let expected = artifact.sha256.trim().to_ascii_lowercase();
    if let Some(parent) = download_path.parent() {
        fs::create_dir_all(parent)?;
    }

    let reusable = download_path.is_file() && {
        on_progress(Progress { stage: Stage::Verifying, done: 0, total: 0 });
        sha256_file(download_path)? == expected
    };
    if !reusable {
        download(artifact.url, &expected, download_path, on_progress)?;
    }

    let exe = extract(download_path, install_root, exe_relative, on_progress)?;
    let _ = fs::remove_file(download_path);
    Ok(exe)
}

fn download(
    url: &str,
    expected: &str,
    download_path: &Path,
    on_progress: &mut dyn FnMut(Progress),
) -> Result<(), InstallError> {
    let agent = ureq::AgentBuilder::new()
        .timeout_connect(CONNECT_TIMEOUT)
        .timeout_read(READ_TIMEOUT)
        .build();
    let response = agent.get(url).call().map_err(|error| match error {
        ureq::Error::Status(code, _) => InstallError::Http(format!("HTTP {code} from {url}")),
        other => InstallError::Http(other.to_string()),
    })?;
    let total = response
        .header("Content-Length")
        .and_then(|value| value.parse::<u64>().ok())
        .unwrap_or(0);

    let part_path = part_path(download_path);
    let result = (|| {
        let mut reader = response.into_reader();
        let mut file = fs::File::create(&part_path)?;
        let mut hasher = Sha256::new();
        let mut buffer = vec![0u8; CHUNK_BYTES];
        let mut reporter = Reporter::new(Stage::Downloading, total);
        let mut done = 0u64;
        reporter.report(0, on_progress);
        loop {
            let read = reader.read(&mut buffer)?;
            if read == 0 {
                break;
            }
            file.write_all(&buffer[..read])?;
            hasher.update(&buffer[..read]);
            done += read as u64;
            reporter.report(done, on_progress);
        }
        file.flush()?;
        drop(file);
        reporter.finish(done, on_progress);
        if total != 0 && done != total {
            return Err(InstallError::Http(format!(
                "connection closed after {done} of {total} bytes"
            )));
        }
        let actual = hex::encode(hasher.finalize());
        if actual != expected {
            return Err(InstallError::Checksum { expected: expected.to_string(), actual });
        }
        fs::rename(&part_path, download_path)?;
        Ok(())
    })();
    if result.is_err() {
        let _ = fs::remove_file(&part_path);
    }
    result
}

fn extract(
    archive_path: &Path,
    install_root: &Path,
    exe_relative: &Path,
    on_progress: &mut dyn FnMut(Progress),
) -> Result<PathBuf, InstallError> {
    let staging = sibling_with_suffix(install_root, ".partial");
    if staging.exists() {
        fs::remove_dir_all(&staging)?;
    }
    let result = (|| {
        let file = fs::File::open(archive_path)?;
        let mut archive =
            zip::ZipArchive::new(file).map_err(|error| InstallError::Archive(error.to_string()))?;

        let mut total = 0u64;
        for index in 0..archive.len() {
            let entry = archive
                .by_index_raw(index)
                .map_err(|error| InstallError::Archive(error.to_string()))?;
            total += entry.size();
        }

        fs::create_dir_all(&staging)?;
        let mut reporter = Reporter::new(Stage::Extracting, total);
        let mut done = 0u64;
        let mut buffer = vec![0u8; CHUNK_BYTES];
        reporter.report(0, on_progress);
        for index in 0..archive.len() {
            let mut entry = archive
                .by_index(index)
                .map_err(|error| InstallError::Archive(error.to_string()))?;
            let relative = entry
                .enclosed_name()
                .ok_or_else(|| InstallError::UnsafePath(entry.name().to_string()))?;
            let target = staging.join(relative);
            if entry.is_dir() {
                fs::create_dir_all(&target)?;
                continue;
            }
            if let Some(parent) = target.parent() {
                fs::create_dir_all(parent)?;
            }
            let mut output = fs::File::create(&target)?;
            loop {
                let read = entry.read(&mut buffer)?;
                if read == 0 {
                    break;
                }
                output.write_all(&buffer[..read])?;
                done += read as u64;
                reporter.report(done, on_progress);
            }
        }
        reporter.finish(done, on_progress);

        if !staging.join(exe_relative).is_file() {
            return Err(InstallError::MissingExecutable(exe_relative.to_path_buf()));
        }
        if install_root.exists() {
            fs::remove_dir_all(install_root)?;
        }
        fs::rename(&staging, install_root)?;
        Ok(install_root.join(exe_relative))
    })();
    if result.is_err() {
        let _ = fs::remove_dir_all(&staging);
    }
    result
}

pub fn sha256_file(path: &Path) -> Result<String, InstallError> {
    let mut file = fs::File::open(path)?;
    let mut hasher = Sha256::new();
    let mut buffer = vec![0u8; CHUNK_BYTES];
    loop {
        let read = file.read(&mut buffer)?;
        if read == 0 {
            break;
        }
        hasher.update(&buffer[..read]);
    }
    Ok(hex::encode(hasher.finalize()))
}

fn part_path(download_path: &Path) -> PathBuf {
    sibling_with_suffix(download_path, ".part")
}

fn sibling_with_suffix(path: &Path, suffix: &str) -> PathBuf {
    let mut name = path.file_name().unwrap_or_default().to_os_string();
    name.push(suffix);
    path.with_file_name(name)
}

struct Reporter {
    stage: Stage,
    total: u64,
    step: u64,
    last: Option<u64>,
}

impl Reporter {
    fn new(stage: Stage, total: u64) -> Self {
        Self { stage, total, step: (total / REPORT_STEPS).max(MIN_REPORT_BYTES), last: None }
    }

    fn report(&mut self, done: u64, on_progress: &mut dyn FnMut(Progress)) {
        let due = match self.last {
            None => true,
            Some(last) => done >= last + self.step,
        };
        if due {
            self.last = Some(done);
            on_progress(Progress { stage: self.stage, done, total: self.total });
        }
    }

    fn finish(&mut self, done: u64, on_progress: &mut dyn FnMut(Progress)) {
        if self.last != Some(done) {
            self.last = Some(done);
            on_progress(Progress { stage: self.stage, done, total: self.total });
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::{
        io::{BufRead, BufReader, Cursor},
        net::TcpListener,
        sync::atomic::{AtomicUsize, Ordering},
        sync::Arc,
        thread,
    };
    use zip::write::SimpleFileOptions;

    const EXE: &str = "blender-x/blender.exe";

    fn zip_with(entries: &[(&str, &[u8])]) -> Vec<u8> {
        let mut writer = zip::ZipWriter::new(Cursor::new(Vec::new()));
        let options =
            SimpleFileOptions::default().compression_method(zip::CompressionMethod::Deflated);
        for (name, data) in entries {
            writer.start_file(*name, options).unwrap();
            writer.write_all(data).unwrap();
        }
        writer.finish().unwrap().into_inner()
    }

    fn sha(bytes: &[u8]) -> String {
        hex::encode(Sha256::digest(bytes))
    }

    /// Serves `body` with the given status to every request; returns the URL and a hit counter.
    fn serve(status: u16, body: Vec<u8>) -> (String, Arc<AtomicUsize>) {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let url = format!("http://{}/artifact.zip", listener.local_addr().unwrap());
        let hits = Arc::new(AtomicUsize::new(0));
        let counter = hits.clone();
        thread::spawn(move || {
            for stream in listener.incoming() {
                let mut stream = stream.unwrap();
                let mut reader = BufReader::new(stream.try_clone().unwrap());
                let mut line = String::new();
                while reader.read_line(&mut line).unwrap() > 2 {
                    line.clear();
                }
                counter.fetch_add(1, Ordering::SeqCst);
                let head = format!(
                    "HTTP/1.1 {status} X\r\nContent-Length: {}\r\nConnection: close\r\n\r\n",
                    body.len()
                );
                stream.write_all(head.as_bytes()).unwrap();
                stream.write_all(&body).unwrap();
            }
        });
        (url, hits)
    }

    struct Dirs {
        _root: tempdir::TempDirGuard,
        download: PathBuf,
        install: PathBuf,
    }

    mod tempdir {
        use std::path::PathBuf;
        pub struct TempDirGuard(pub PathBuf);
        impl Drop for TempDirGuard {
            fn drop(&mut self) {
                let _ = std::fs::remove_dir_all(&self.0);
            }
        }
    }

    fn dirs(tag: &str) -> Dirs {
        let root = std::env::temp_dir().join(format!(
            "runtime-installer-{tag}-{}-{:?}",
            std::process::id(),
            thread::current().id()
        ));
        let _ = fs::remove_dir_all(&root);
        fs::create_dir_all(&root).unwrap();
        Dirs {
            download: root.join("downloads").join("blender.zip"),
            install: root.join("tools").join("blender"),
            _root: tempdir::TempDirGuard(root),
        }
    }

    #[test]
    fn downloads_verifies_and_unpacks_with_progress() {
        let archive = zip_with(&[(EXE, b"exe"), ("blender-x/data/a.txt", &[7u8; 3_000_000])]);
        let (url, hits) = serve(200, archive.clone());
        let d = dirs("ok");
        let mut events = Vec::new();

        let exe = install_zip(
            &Artifact { url: &url, sha256: &sha(&archive).to_uppercase() },
            &d.download,
            &d.install,
            Path::new(EXE),
            &mut |p| events.push(p),
        )
        .unwrap();

        assert_eq!(fs::read(&exe).unwrap(), b"exe");
        assert_eq!(fs::read(d.install.join("blender-x/data/a.txt")).unwrap().len(), 3_000_000);
        assert_eq!(hits.load(Ordering::SeqCst), 1);
        assert!(!d.download.exists(), "archive is removed after install");
        let last_download = events.iter().rev().find(|p| p.stage == Stage::Downloading).unwrap();
        assert_eq!((last_download.done, last_download.percent()), (archive.len() as u64, 100));
        let last_extract = events.iter().rev().find(|p| p.stage == Stage::Extracting).unwrap();
        assert_eq!(last_extract.percent(), 100);
        assert!(events.len() < 50, "progress is throttled, got {} events", events.len());
    }

    #[test]
    fn rejects_a_checksum_mismatch_and_leaves_nothing_behind() {
        let archive = zip_with(&[(EXE, b"exe")]);
        let (url, _) = serve(200, archive);
        let d = dirs("sha");

        let error = install_zip(
            &Artifact { url: &url, sha256: &"0".repeat(64) },
            &d.download,
            &d.install,
            Path::new(EXE),
            &mut |_| {},
        )
        .unwrap_err();

        assert!(matches!(error, InstallError::Checksum { .. }), "{error}");
        assert!(!d.download.exists());
        assert!(!part_path(&d.download).exists());
        assert!(!d.install.exists());
    }

    #[test]
    fn refuses_entries_that_escape_the_install_folder() {
        let archive = zip_with(&[(EXE, b"exe"), ("../evil.txt", b"x")]);
        let (url, _) = serve(200, archive.clone());
        let d = dirs("slip");

        let error = install_zip(
            &Artifact { url: &url, sha256: &sha(&archive) },
            &d.download,
            &d.install,
            Path::new(EXE),
            &mut |_| {},
        )
        .unwrap_err();

        assert!(matches!(error, InstallError::UnsafePath(_)), "{error}");
        assert!(!d.install.exists());
        assert!(!sibling_with_suffix(&d.install, ".partial").exists());
        assert!(!d.install.parent().unwrap().join("evil.txt").exists());
    }

    #[test]
    fn reuses_an_already_verified_download_without_http() {
        let archive = zip_with(&[(EXE, b"exe")]);
        let d = dirs("reuse");
        fs::create_dir_all(d.download.parent().unwrap()).unwrap();
        fs::write(&d.download, &archive).unwrap();
        let (url, hits) = serve(500, Vec::new());

        install_zip(
            &Artifact { url: &url, sha256: &sha(&archive) },
            &d.download,
            &d.install,
            Path::new(EXE),
            &mut |_| {},
        )
        .unwrap();

        assert_eq!(hits.load(Ordering::SeqCst), 0);
        assert!(d.install.join(EXE).is_file());
    }

    #[test]
    fn keeps_the_previous_install_when_the_executable_is_missing() {
        let archive = zip_with(&[("blender-x/readme.txt", b"no exe")]);
        let (url, _) = serve(200, archive.clone());
        let d = dirs("noexe");
        fs::create_dir_all(d.install.join("blender-x")).unwrap();
        fs::write(d.install.join(EXE), b"old").unwrap();

        let error = install_zip(
            &Artifact { url: &url, sha256: &sha(&archive) },
            &d.download,
            &d.install,
            Path::new(EXE),
            &mut |_| {},
        )
        .unwrap_err();

        assert!(matches!(error, InstallError::MissingExecutable(_)), "{error}");
        assert_eq!(fs::read(d.install.join(EXE)).unwrap(), b"old");
        assert!(!sibling_with_suffix(&d.install, ".partial").exists());
    }

    #[test]
    fn reports_http_errors() {
        let (url, _) = serve(404, b"missing".to_vec());
        let d = dirs("404");

        let error = install_zip(
            &Artifact { url: &url, sha256: &"0".repeat(64) },
            &d.download,
            &d.install,
            Path::new(EXE),
            &mut |_| {},
        )
        .unwrap_err();

        assert!(matches!(&error, InstallError::Http(message) if message.contains("404")), "{error}");
    }
}
