#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::{Deserialize, Serialize};
use std::{
    env,
    fs,
    io::{Read, Write},
    net::{TcpListener, TcpStream},
    path::{Path, PathBuf},
    process::{Child, Command, Stdio},
    sync::Mutex,
    thread,
    time::{Duration, Instant},
};
use tauri::{AppHandle, Manager, State, WindowEvent};

const DEFAULT_BACKEND_PORT: u16 = 8000;
const DESKTOP_PORT_START: u16 = 8765;
const DESKTOP_PORT_END: u16 = 8795;
const DEMO_PROJECT_ID: &str = "proj_desktop_demo";
const BLENDER_EXE_RELATIVE_PATH: &[&str] = &["blender-4.5.1-windows-x64", "blender.exe"];
const BLENDER_ARTIFACT_PATH_ENV: &str = "KUSSHOES_BLENDER_ARTIFACT_PATH";
const BLENDER_ARTIFACT_URL_ENV: &str = "KUSSHOES_BLENDER_ARTIFACT_URL";
const BLENDER_ARTIFACT_SHA_ENV: &str = "KUSSHOES_BLENDER_SHA256";
const AUTO_INSTALL_BLENDER_ENV: &str = "KUSSHOES_DESKTOP_AUTO_INSTALL_BLENDER";

#[derive(Default)]
struct RuntimeState {
    runtime: Option<DesktopRuntime>,
    backend_child: Option<Child>,
}

#[derive(Clone, Serialize)]
#[serde(rename_all = "camelCase")]
struct DesktopRuntime {
    api_base_url: String,
    backend_status: String,
    blender_status: String,
    demo_project_status: String,
    diagnostic_summary: String,
    backend_port: u16,
    storage_path: String,
    blender_path: String,
    logs_path: String,
    app_version: String,
    last_error: Option<String>,
}

#[derive(Clone, Serialize)]
#[serde(rename_all = "camelCase")]
struct InstallProgress {
    name: String,
    status: String,
    message: String,
    percent: u8,
    path: Option<String>,
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct DependencyManifest {
    name: String,
    version: String,
    download_url: String,
    sha256: String,
    archive_type: String,
    exe_relative_path: String,
    installed_size_estimate: String,
}

#[tauri::command]
fn get_desktop_runtime(
    app: AppHandle,
    state: State<'_, Mutex<RuntimeState>>,
) -> Result<DesktopRuntime, String> {
    let mut guard = state.lock().map_err(|_| "Desktop runtime state is locked.")?;
    let runtime = ensure_runtime(&app, &mut guard)?;
    Ok(runtime)
}

#[tauri::command]
fn restart_backend(
    app: AppHandle,
    state: State<'_, Mutex<RuntimeState>>,
) -> Result<DesktopRuntime, String> {
    let mut guard = state.lock().map_err(|_| "Desktop runtime state is locked.")?;
    stop_backend(&mut guard);
    guard.runtime = None;
    ensure_runtime(&app, &mut guard)
}

#[tauri::command]
fn install_dependency(
    app: AppHandle,
    state: State<'_, Mutex<RuntimeState>>,
    name: String,
) -> Result<InstallProgress, String> {
    if name != "blender" {
        return Ok(InstallProgress {
            name,
            status: "failed".to_string(),
            message: "Dependency is not supported by the desktop beta.".to_string(),
            percent: 0,
            path: None,
        });
    }

    let paths = desktop_paths(&app)?;
    let progress = install_blender_dependency(&app, &paths)?;
    if progress.status == "installed" {
        if let Ok(mut guard) = state.lock() {
            guard.runtime = None;
        }
    }
    Ok(progress)
}

#[tauri::command]
fn open_diagnostics_folder(app: AppHandle) -> Result<(), String> {
    let paths = desktop_paths(&app)?;
    fs::create_dir_all(&paths.logs_dir).map_err(|error| error.to_string())?;
    Command::new("explorer")
        .arg(&paths.logs_dir)
        .spawn()
        .map_err(|error| error.to_string())?;
    Ok(())
}

fn ensure_runtime(
    app: &AppHandle,
    state: &mut RuntimeState,
) -> Result<DesktopRuntime, String> {
    if let Some(runtime) = &state.runtime {
        if is_backend_ready(runtime.backend_port) {
            return Ok(runtime.clone());
        }
    }

    let mut paths = desktop_paths(app)?;
    fs::create_dir_all(&paths.storage_dir).map_err(|error| error.to_string())?;
    fs::create_dir_all(&paths.logs_dir).map_err(|error| error.to_string())?;
    let mut dependency_error = None;

    if !paths.blender_bin.is_file() && should_auto_install_blender(app) {
        match install_blender_dependency(app, &paths) {
            Ok(progress) if progress.status == "installed" => {
                paths = desktop_paths(app)?;
            }
            Ok(progress) => {
                dependency_error = Some(progress.message);
            }
            Err(error) => {
                dependency_error = Some(error);
            }
        }
    }

    let (backend_port, backend_status, last_error) = if is_backend_ready(DEFAULT_BACKEND_PORT) {
        (DEFAULT_BACKEND_PORT, "ready".to_string(), None)
    } else {
        let port = find_free_port().ok_or_else(|| "No local backend port is available.".to_string())?;
        match start_backend_sidecar(app, &paths, port) {
            Ok(child) => {
                state.backend_child = Some(child);
                if wait_for_backend(port) {
                    (port, "ready".to_string(), None)
                } else {
                    (
                        port,
                        "failed".to_string(),
                        Some("Backend sidecar did not become ready in time.".to_string()),
                    )
                }
            }
            Err(error) => (port, "failed".to_string(), Some(error)),
        }
    };
    let last_error = last_error.or(dependency_error);

    let blender_status = if paths.blender_bin.is_file() {
        "installed"
    } else {
        "missing"
    };
    let runtime = DesktopRuntime {
        api_base_url: format!("http://127.0.0.1:{backend_port}"),
        backend_status: backend_status.clone(),
        blender_status: blender_status.to_string(),
        demo_project_status: if backend_status == "ready" {
            "ready".to_string()
        } else {
            "failed".to_string()
        },
        diagnostic_summary: diagnostic_summary(&paths, backend_port, &backend_status, blender_status),
        backend_port,
        storage_path: paths.storage_dir.to_string_lossy().to_string(),
        blender_path: paths.blender_bin.to_string_lossy().to_string(),
        logs_path: paths.logs_dir.to_string_lossy().to_string(),
        app_version: app.package_info().version.to_string(),
        last_error,
    };
    state.runtime = Some(runtime.clone());
    Ok(runtime)
}

fn start_backend_sidecar(
    app: &AppHandle,
    paths: &DesktopPaths,
    port: u16,
) -> Result<Child, String> {
    let repo_root = find_repo_root();
    let demo_model = desktop_demo_model_path(app, repo_root.as_deref());
    let backend_log = paths.logs_dir.join("backend.log");
    let backend_err = paths.logs_dir.join("backend.err.log");
    let stdout = fs::File::create(backend_log).map_err(|error| error.to_string())?;
    let stderr = fs::File::create(backend_err).map_err(|error| error.to_string())?;

    let mut command = if let Ok(configured) = env::var("KUSSHOES_BACKEND_BIN") {
        let mut cmd = Command::new(configured);
        cmd.arg("--port")
            .arg(port.to_string())
            .arg("--frontend-port")
            .arg("5173");
        cmd
    } else if let Some(sidecar) = packaged_backend_exe(app) {
        let mut cmd = Command::new(sidecar);
        cmd.arg("--port")
            .arg(port.to_string())
            .arg("--frontend-port")
            .arg("5173");
        cmd
    } else if let Some(root) = &repo_root {
        let python = root
            .join("backend")
            .join(".venv")
            .join("Scripts")
            .join("python.exe");
        if !python.is_file() {
            return Err("Backend sidecar is not bundled and backend/.venv was not found.".to_string());
        }
        let mut cmd = Command::new(python);
        cmd.current_dir(root.join("backend"));
        cmd.arg("-m")
            .arg("app.desktop_entrypoint")
            .arg("--port")
            .arg(port.to_string())
            .arg("--frontend-port")
            .arg("5173");
        cmd
    } else {
        return Err("Backend sidecar is not available in this build.".to_string());
    };

    command
        .env("KUSSHOES_DESKTOP_APP_DATA", &paths.app_data_dir)
        .env("KUSSHOES_DESKTOP_DEMO_MODEL", demo_model.unwrap_or_default())
        .env("BLENDER_BIN", &paths.blender_bin)
        .stdout(Stdio::from(stdout))
        .stderr(Stdio::from(stderr));
    command.spawn().map_err(|error| error.to_string())
}

fn packaged_backend_exe(app: &AppHandle) -> Option<PathBuf> {
    if let Ok(resource_dir) = app.path().resource_dir() {
        let candidate = resource_dir.join("sidecars").join("kusshoes-backend.exe");
        if candidate.is_file() {
            return Some(candidate);
        }
    }
    let candidate = env::current_exe().ok()?.parent()?.join("kusshoes-backend.exe");
    candidate.is_file().then_some(candidate)
}

fn desktop_demo_model_path(app: &AppHandle, repo_root: Option<&Path>) -> Option<PathBuf> {
    if let Some(root) = repo_root {
        let candidate = root.join("data").join("3DModel.glb");
        if candidate.is_file() {
            return Some(candidate);
        }
    }

    let resource_dir = app.path().resource_dir().ok()?;
    for candidate in [
        resource_dir.join("data").join("3DModel.glb"),
        resource_dir.join("resources").join("data").join("3DModel.glb"),
        resource_dir.join("3DModel.glb"),
    ] {
        if candidate.is_file() {
            return Some(candidate);
        }
    }
    None
}

fn install_blender_dependency(
    app: &AppHandle,
    paths: &DesktopPaths,
) -> Result<InstallProgress, String> {
    fs::create_dir_all(&paths.tools_dir).map_err(|error| error.to_string())?;
    fs::create_dir_all(&paths.logs_dir).map_err(|error| error.to_string())?;
    if paths.blender_bin.is_file() {
        return Ok(InstallProgress {
            name: "blender".to_string(),
            status: "installed".to_string(),
            message: "Preview renderer đã được cài đặt.".to_string(),
            percent: 100,
            path: Some(paths.blender_bin.to_string_lossy().to_string()),
        });
    }

    let manifest = read_dependency_manifest(app)?;
    if manifest.archive_type.to_lowercase() != "zip" {
        return Ok(InstallProgress {
            name: manifest.name,
            status: "failed".to_string(),
            message: "Preview renderer artifact phải là file ZIP.".to_string(),
            percent: 0,
            path: None,
        });
    }

    let sha256 = configured_blender_sha(&manifest);
    if !is_sha256(&sha256) {
        return Ok(InstallProgress {
            name: manifest.name,
            status: "failed".to_string(),
            message: "Preview renderer chưa có SHA-256 hợp lệ. Release/dev setup phải cấu hình artifact nội bộ trước.".to_string(),
            percent: 0,
            path: None,
        });
    }

    let artifact_path = env::var_os(BLENDER_ARTIFACT_PATH_ENV)
        .map(PathBuf::from)
        .filter(|path| path.is_file());
    let artifact_url = env::var(BLENDER_ARTIFACT_URL_ENV)
        .ok()
        .map(|value| value.trim().to_string())
        .filter(|value| !value.is_empty())
        .or_else(|| {
            let value = manifest.download_url.trim();
            (!value.is_empty()).then(|| value.to_string())
        });

    let artifact_command = if let Some(path) = artifact_path {
        format!(
            "Copy-Item -LiteralPath '{}' -Destination '{}' -Force;",
            ps_escape_path(&path),
            ps_escape_path(&paths.download_path(&manifest)),
        )
    } else if let Some(url) = artifact_url {
        if url.contains("download.blender.org") {
            return Ok(InstallProgress {
                name: manifest.name,
                status: "failed".to_string(),
                message: "Preview renderer phải lấy từ internal artifact, không tải trực tiếp từ download.blender.org.".to_string(),
                percent: 0,
                path: None,
            });
        }
        format!(
            "Invoke-WebRequest -Uri '{}' -OutFile '{}';",
            ps_escape(&url),
            ps_escape_path(&paths.download_path(&manifest)),
        )
    } else {
        return Ok(InstallProgress {
            name: manifest.name,
            status: "failed".to_string(),
            message: "Preview renderer chưa cấu hình internal artifact. Hãy set KUSSHOES_BLENDER_ARTIFACT_PATH hoặc KUSSHOES_BLENDER_ARTIFACT_URL.".to_string(),
            percent: 0,
            path: None,
        });
    };

    let download_path = paths.download_path(&manifest);
    if let Some(parent) = download_path.parent() {
        fs::create_dir_all(parent).map_err(|error| error.to_string())?;
    }

    let install_root = paths.tools_dir.join(&manifest.name);
    let script = format!(
        "$ErrorActionPreference='Stop'; \
         {}; \
         $hash=(Get-FileHash -Algorithm SHA256 '{}').Hash.ToLowerInvariant(); \
         if ($hash -ne '{}') {{ throw 'Checksum mismatch.' }}; \
         if (Test-Path -LiteralPath '{}') {{ Remove-Item -LiteralPath '{}' -Recurse -Force }}; \
         New-Item -ItemType Directory -Force -Path '{}' | Out-Null; \
         Expand-Archive -LiteralPath '{}' -DestinationPath '{}' -Force;",
        artifact_command,
        ps_escape_path(&download_path),
        sha256.to_lowercase(),
        ps_escape_path(&install_root),
        ps_escape_path(&install_root),
        ps_escape_path(&install_root),
        ps_escape_path(&download_path),
        ps_escape_path(&install_root),
    );
    let output = Command::new("powershell")
        .args(["-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", &script])
        .output()
        .map_err(|error| error.to_string())?;

    if !output.status.success() {
        let details = String::from_utf8_lossy(&output.stderr).trim().to_string();
        let _ = fs::write(paths.logs_dir.join("dependency-install.err.log"), details);
        return Ok(InstallProgress {
            name: manifest.name,
            status: "failed".to_string(),
            message: "Ứng dụng chưa cài được Preview renderer. Vui lòng mở Logs để gửi diagnostics cho team.".to_string(),
            percent: 0,
            path: None,
        });
    }

    let installed_exe = install_root.join(Path::new(&manifest.exe_relative_path));
    let installed = installed_exe.is_file();
    Ok(InstallProgress {
        name: manifest.name,
        status: if installed { "installed" } else { "failed" }.to_string(),
        message: if installed {
            format!(
                "Preview renderer đã cài đặt xong. Dung lượng dự kiến: {}.",
                manifest.installed_size_estimate
            )
        } else {
            "Ứng dụng đã giải nén renderer nhưng chưa tìm thấy blender.exe. Vui lòng mở Logs để gửi diagnostics cho team.".to_string()
        },
        percent: if installed { 100 } else { 0 },
        path: installed.then(|| installed_exe.to_string_lossy().to_string()),
    })
}

fn should_auto_install_blender(app: &AppHandle) -> bool {
    if !cfg!(debug_assertions)
        && env::var(AUTO_INSTALL_BLENDER_ENV).ok().as_deref() != Some("1")
    {
        return false;
    }
    let Ok(manifest) = read_dependency_manifest(app) else {
        return false;
    };
    is_sha256(&configured_blender_sha(&manifest))
        && (env::var_os(BLENDER_ARTIFACT_PATH_ENV).is_some()
            || env::var(BLENDER_ARTIFACT_URL_ENV)
                .ok()
                .is_some_and(|value| !value.trim().is_empty())
            || !manifest.download_url.trim().is_empty())
}

fn configured_blender_sha(manifest: &DependencyManifest) -> String {
    env::var(BLENDER_ARTIFACT_SHA_ENV)
        .ok()
        .map(|value| value.trim().to_string())
        .filter(|value| !value.is_empty())
        .unwrap_or_else(|| manifest.sha256.trim().to_string())
}

fn is_sha256(value: &str) -> bool {
    value.len() == 64 && value.chars().all(|character| character.is_ascii_hexdigit())
}

fn is_backend_ready(port: u16) -> bool {
    http_get(port, "/health").is_some_and(|body| body.contains("\"status\":\"ok\"") || body.contains("\"status\": \"ok\""))
}

fn wait_for_backend(port: u16) -> bool {
    let start = Instant::now();
    while start.elapsed() < Duration::from_secs(20) {
        if is_backend_ready(port) {
            return true;
        }
        thread::sleep(Duration::from_millis(350));
    }
    false
}

fn http_get(port: u16, path: &str) -> Option<String> {
    let mut stream = TcpStream::connect(("127.0.0.1", port)).ok()?;
    let request = format!(
        "GET {path} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nConnection: close\r\n\r\n"
    );
    stream.write_all(request.as_bytes()).ok()?;
    let mut response = String::new();
    stream.read_to_string(&mut response).ok()?;
    Some(response)
}

fn find_free_port() -> Option<u16> {
    for port in DESKTOP_PORT_START..=DESKTOP_PORT_END {
        if TcpListener::bind(("127.0.0.1", port)).is_ok() {
            return Some(port);
        }
    }
    None
}

fn find_repo_root() -> Option<PathBuf> {
    let mut current = env::current_dir().ok()?;
    loop {
        if current.join("backend").join("app").join("main.py").is_file()
            && current.join("frontend").join("src").is_dir()
        {
            return Some(current);
        }
        if !current.pop() {
            return None;
        }
    }
}

fn read_dependency_manifest(app: &AppHandle) -> Result<DependencyManifest, String> {
    let repo_manifest = find_repo_root()
        .map(|root| root.join("desktop").join("dependencies").join("blender.windows.json"));
    let packaged_manifest = app
        .path()
        .resource_dir()
        .ok()
        .map(|path| path.join("dependencies").join("blender.windows.json"));
    for candidate in [repo_manifest, packaged_manifest].into_iter().flatten() {
        if candidate.is_file() {
            let text = fs::read_to_string(candidate).map_err(|error| error.to_string())?;
            return serde_json::from_str(&text).map_err(|error| error.to_string());
        }
    }
    Err("Preview renderer manifest was not found.".to_string())
}

fn diagnostic_summary(
    paths: &DesktopPaths,
    backend_port: u16,
    backend_status: &str,
    blender_status: &str,
) -> String {
    format!(
        "Backend: {backend_status} on 127.0.0.1:{backend_port}\nPreview renderer: {blender_status}\nStorage: {}\nBlender: {}\nApp-data Blender: {}\nDemo project: {DEMO_PROJECT_ID}",
        paths.storage_dir.to_string_lossy(),
        paths.blender_bin.to_string_lossy(),
        paths.installed_blender_bin.to_string_lossy(),
    )
}

fn stop_backend(state: &mut RuntimeState) {
    if let Some(mut child) = state.backend_child.take() {
        let _ = child.kill();
        let _ = child.wait();
    }
}

fn ps_escape(value: &str) -> String {
    value.replace('\'', "''")
}

fn ps_escape_path(path: &Path) -> String {
    ps_escape(&path.to_string_lossy())
}

struct DesktopPaths {
    app_data_dir: PathBuf,
    runtime_dir: PathBuf,
    storage_dir: PathBuf,
    logs_dir: PathBuf,
    tools_dir: PathBuf,
    installed_blender_bin: PathBuf,
    blender_bin: PathBuf,
}

impl DesktopPaths {
    fn download_path(&self, manifest: &DependencyManifest) -> PathBuf {
        self.runtime_dir.join("downloads").join(format!(
            "{}-{}.{}",
            manifest.name, manifest.version, manifest.archive_type
        ))
    }
}

fn desktop_paths(app: &AppHandle) -> Result<DesktopPaths, String> {
    let app_data_dir = app.path().app_data_dir().map_err(|error| error.to_string())?;
    let runtime_dir = app_data_dir.join("runtime");
    let storage_dir = app_data_dir.join("storage");
    let logs_dir = runtime_dir.join("logs");
    let tools_dir = runtime_dir.join("tools");
    let installed_blender_bin = blender_bin_under(&tools_dir.join("blender"));
    let blender_bin =
        resolve_blender_bin(app, &installed_blender_bin).unwrap_or_else(|| installed_blender_bin.clone());
    Ok(DesktopPaths {
        app_data_dir,
        runtime_dir,
        storage_dir,
        logs_dir,
        tools_dir,
        installed_blender_bin,
        blender_bin,
    })
}

fn resolve_blender_bin(app: &AppHandle, installed_blender_bin: &Path) -> Option<PathBuf> {
    env::var_os("BLENDER_BIN")
        .map(PathBuf::from)
        .filter(|path| path.is_file())
        .or_else(|| installed_blender_bin.is_file().then(|| installed_blender_bin.to_path_buf()))
        .or_else(|| bundled_blender_bin(app))
        .or_else(repo_prepared_blender_bin)
}

fn bundled_blender_bin(app: &AppHandle) -> Option<PathBuf> {
    let resource_dir = app.path().resource_dir().ok()?;
    for base in [
        resource_dir.join("dependencies").join("tools").join("blender"),
        resource_dir.join("tools").join("blender"),
    ] {
        let candidate = blender_bin_under(&base);
        if candidate.is_file() {
            return Some(candidate);
        }
    }
    None
}

fn repo_prepared_blender_bin() -> Option<PathBuf> {
    let root = find_repo_root()?;
    let candidate = blender_bin_under(
        &root
            .join("desktop")
            .join("dependencies")
            .join("tools")
            .join("blender"),
    );
    candidate.is_file().then_some(candidate)
}

fn blender_bin_under(base: &Path) -> PathBuf {
    let mut path = base.to_path_buf();
    for component in BLENDER_EXE_RELATIVE_PATH {
        path = path.join(component);
    }
    path
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, args, cwd| {
            let _ = app.emit("single-instance-deep-link", args);
        }))
        .plugin(tauri_plugin_deep_link::init())
        .manage(Mutex::new(RuntimeState::default()))
        .invoke_handler(tauri::generate_handler![
            get_desktop_runtime,
            install_dependency,
            restart_backend,
            open_diagnostics_folder,
        ])
        .on_window_event(|window, event| {
            if matches!(event, WindowEvent::CloseRequested { .. }) {
                let state = window.state::<Mutex<RuntimeState>>();
                if let Ok(mut guard) = state.lock() {
                    stop_backend(&mut guard);
                };
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running KusShoes desktop editor");
}
