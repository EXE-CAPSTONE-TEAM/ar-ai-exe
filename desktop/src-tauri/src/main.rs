#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::{Deserialize, Serialize};
use std::{
    env,
    fs,
    io::{Read, Write},
    net::{TcpListener, TcpStream},
    path::{Path, PathBuf},
    process::{Child, Command, Stdio},
    sync::{
        atomic::{AtomicBool, Ordering},
        Mutex,
    },
    thread,
    time::{Duration, Instant},
};
use tauri::{AppHandle, Emitter, Manager, State, WindowEvent};
use tauri_plugin_updater::UpdaterExt;

/// Comma-separated https storage origins the sidecar may download from / upload to (the R2
/// account endpoint). Baked in at build time, overridable at runtime (KusShoes spec §F.3).
const STORAGE_ORIGINS_ENV: &str = "KUSSHOES_STORAGE_ORIGINS";
const DEMO_PROJECT_ID: &str = "proj_desktop_demo";
const BLENDER_EXE_RELATIVE_PATH: &[&str] = &["blender-4.5.1-windows-x64", "blender.exe"];
const BLENDER_ARTIFACT_PATH_ENV: &str = "KUSSHOES_BLENDER_ARTIFACT_PATH";
const BLENDER_ARTIFACT_URL_ENV: &str = "KUSSHOES_BLENDER_ARTIFACT_URL";
const BLENDER_ARTIFACT_SHA_ENV: &str = "KUSSHOES_BLENDER_SHA256";
/// Set to "0" to stop the shell from fetching the preview renderer on first launch.
const AUTO_INSTALL_BLENDER_ENV: &str = "KUSSHOES_DESKTOP_AUTO_INSTALL_BLENDER";
const INSTALL_PROGRESS_EVENT: &str = "dependency-install-progress";
const UPDATE_AVAILABLE_EVENT: &str = "app-update-available";
const UPDATE_PROGRESS_EVENT: &str = "app-update-progress";
/// Share of the overall bar given to the download; unpacking takes the rest.
const DOWNLOAD_SHARE_PERCENT: u64 = 80;

#[derive(Default)]
struct RuntimeState {
    runtime: Option<DesktopRuntime>,
    backend_child: Option<Child>,
    /// Per-launch secret shared only with the sidecar this shell spawned (spec §F.2).
    launch_token: Option<String>,
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
    /// X-Service-Token for the sidecar's /bake, /prepare and /downloads; only set once the
    /// sidecar passed the launch handshake. Never written to disk.
    sidecar_token: Option<String>,
}

#[derive(Clone, Serialize)]
#[serde(rename_all = "camelCase")]
struct InstallProgress {
    name: String,
    /// missing | downloading | installed | failed (unchanged meaning for the UI).
    status: String,
    /// downloading | verifying | extracting while status is "downloading".
    stage: String,
    message: String,
    /// Overall 0-100 across download and unpack.
    percent: u8,
    downloaded_bytes: u64,
    total_bytes: u64,
    path: Option<String>,
}

impl InstallProgress {
    fn finished(name: &str, status: &str, message: String, path: Option<String>) -> Self {
        Self {
            name: name.to_string(),
            status: status.to_string(),
            stage: status.to_string(),
            message,
            percent: if status == "installed" { 100 } else { 0 },
            downloaded_bytes: 0,
            total_bytes: 0,
            path,
        }
    }

    fn failed(name: &str, message: impl Into<String>) -> Self {
        Self::finished(name, "failed", message.into(), None)
    }

    fn from_installer(name: &str, progress: runtime_installer::Progress) -> Self {
        use runtime_installer::Stage;
        let stage_percent = u64::from(progress.percent());
        let (stage, percent, message) = match progress.stage {
            Stage::Downloading => (
                "downloading",
                stage_percent * DOWNLOAD_SHARE_PERCENT / 100,
                format!(
                    "Đang tải bộ dựng hình 3D (chỉ lần đầu): {} / {}",
                    format_mb(progress.done),
                    format_mb(progress.total)
                ),
            ),
            Stage::Verifying => (
                "verifying",
                DOWNLOAD_SHARE_PERCENT,
                "Đang kiểm tra file đã tải...".to_string(),
            ),
            Stage::Extracting => (
                "extracting",
                DOWNLOAD_SHARE_PERCENT + stage_percent * (99 - DOWNLOAD_SHARE_PERCENT) / 100,
                format!("Đang cài đặt bộ dựng hình 3D... {stage_percent}%"),
            ),
        };
        Self {
            name: name.to_string(),
            status: "downloading".to_string(),
            stage: stage.to_string(),
            message,
            percent: percent as u8,
            downloaded_bytes: progress.done,
            total_bytes: progress.total,
            path: None,
        }
    }
}

fn format_mb(bytes: u64) -> String {
    if bytes == 0 {
        return "? MB".to_string();
    }
    format!("{:.0} MB", bytes as f64 / (1024.0 * 1024.0))
}

/// The background preview-renderer install: at most one runs, the latest progress is kept so a
/// window that opens (or reloads) mid-install can pick it up before the next event arrives.
#[derive(Default)]
struct InstallState {
    running: AtomicBool,
    last: Mutex<Option<InstallProgress>>,
}

impl InstallState {
    fn record(&self, progress: &InstallProgress) {
        if let Ok(mut last) = self.last.lock() {
            *last = Some(progress.clone());
        }
    }

    fn latest(&self) -> Option<InstallProgress> {
        self.last.lock().ok().and_then(|last| last.clone())
    }
}

#[derive(Default)]
struct UpdateState {
    pending: Mutex<Option<tauri_plugin_updater::Update>>,
}

#[derive(Clone, Serialize)]
#[serde(rename_all = "camelCase")]
struct AppUpdateInfo {
    version: String,
    current_version: String,
    notes: Option<String>,
}

#[derive(Clone, Serialize)]
#[serde(rename_all = "camelCase")]
struct UpdateProgress {
    downloaded_bytes: u64,
    total_bytes: u64,
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

/// Starts (or joins) the background install and returns immediately; progress arrives as
/// `dependency-install-progress` events.
#[tauri::command]
fn install_dependency(app: AppHandle, name: String) -> Result<InstallProgress, String> {
    if name != "blender" {
        return Ok(InstallProgress::failed(
            &name,
            "Dependency is not supported by the desktop beta.",
        ));
    }
    Ok(start_blender_install(&app))
}

#[tauri::command]
fn get_install_progress(app: AppHandle) -> Result<InstallProgress, String> {
    let installs = app.state::<InstallState>();
    if let Some(progress) = installs.latest() {
        return Ok(progress);
    }
    let paths = desktop_paths(&app)?;
    Ok(if paths.blender_bin.is_file() {
        // "present" (not "installed") so the UI does not announce a fresh install every launch.
        let mut present = InstallProgress::finished(
            "blender",
            "installed",
            "Bộ dựng hình 3D đã sẵn sàng.".to_string(),
            Some(paths.blender_bin.to_string_lossy().to_string()),
        );
        present.stage = "present".to_string();
        present
    } else {
        InstallProgress::finished(
            "blender",
            "missing",
            "Chưa cài bộ dựng hình 3D.".to_string(),
            None,
        )
    })
}

#[tauri::command]
fn get_app_update(app: AppHandle) -> Option<AppUpdateInfo> {
    let state = app.state::<UpdateState>();
    let pending = state.pending.lock().ok()?;
    pending
        .as_ref()
        .map(|update| update_info(&app, update))
}

/// Downloads and runs the new installer (passive NSIS), then restarts into the new version.
#[tauri::command]
async fn install_app_update(app: AppHandle) -> Result<(), String> {
    let update = app
        .state::<UpdateState>()
        .pending
        .lock()
        .map_err(|_| "Update state is locked.".to_string())?
        .take()
        .ok_or_else(|| "Không có bản cập nhật nào đang chờ.".to_string())?;
    let mut downloaded: u64 = 0;
    let progress_app = app.clone();
    update
        .download_and_install(
            move |chunk, total| {
                downloaded += chunk as u64;
                let _ = progress_app.emit(
                    UPDATE_PROGRESS_EVENT,
                    UpdateProgress {
                        downloaded_bytes: downloaded,
                        total_bytes: total.unwrap_or(0),
                    },
                );
            },
            || {},
        )
        .await
        .map_err(|error| format!("Cập nhật thất bại: {error}"))?;
    if let Ok(mut guard) = app.state::<Mutex<RuntimeState>>().lock() {
        stop_backend(&mut guard);
    }
    app.restart();
}

fn update_info(app: &AppHandle, update: &tauri_plugin_updater::Update) -> AppUpdateInfo {
    AppUpdateInfo {
        version: update.version.clone(),
        current_version: app.package_info().version.to_string(),
        notes: update.body.clone(),
    }
}

async fn check_for_update(app: AppHandle) {
    let Ok(updater) = app.updater() else {
        return;
    };
    match updater.check().await {
        Ok(Some(update)) => {
            let info = update_info(&app, &update);
            if let Ok(mut pending) = app.state::<UpdateState>().pending.lock() {
                *pending = Some(update);
            }
            let _ = app.emit(UPDATE_AVAILABLE_EVENT, info);
        }
        Ok(None) => {}
        Err(error) => {
            if let Ok(paths) = desktop_paths(&app) {
                let _ = fs::create_dir_all(&paths.logs_dir);
                let _ = fs::write(paths.logs_dir.join("update-check.err.log"), error.to_string());
            }
        }
    }
}

fn start_blender_install(app: &AppHandle) -> InstallProgress {
    let installs = app.state::<InstallState>();
    if installs.running.swap(true, Ordering::SeqCst) {
        return installs.latest().unwrap_or_else(|| {
            InstallProgress::finished("blender", "downloading", "Đang chuẩn bị...".to_string(), None)
        });
    }
    let mut starting =
        InstallProgress::finished("blender", "downloading", "Đang chuẩn bị tải...".to_string(), None);
    starting.stage = "downloading".to_string();
    installs.record(&starting);
    let _ = app.emit(INSTALL_PROGRESS_EVENT, &starting);

    let app = app.clone();
    thread::spawn(move || {
        let installs = app.state::<InstallState>();
        let outcome = match desktop_paths(&app) {
            Ok(paths) => install_blender_dependency(&app, &paths, &mut |progress| {
                installs.record(progress);
                let _ = app.emit(INSTALL_PROGRESS_EVENT, progress);
            }),
            Err(error) => InstallProgress::failed("blender", error),
        };
        if outcome.status == "installed" {
            // The sidecar learns BLENDER_BIN at spawn; let the next runtime request respawn it.
            if let Ok(mut guard) = app.state::<Mutex<RuntimeState>>().lock() {
                guard.runtime = None;
            }
        }
        installs.record(&outcome);
        installs.running.store(false, Ordering::SeqCst);
        let _ = app.emit(INSTALL_PROGRESS_EVENT, &outcome);
    });
    starting
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
        let verified = state
            .launch_token
            .as_deref()
            .is_some_and(|token| sidecar_proves_token(runtime.backend_port, token));
        if sidecar_auth::may_reuse_sidecar(state.backend_child.is_some(), verified) {
            return Ok(runtime.clone());
        }
    }

    // The preview renderer installs in the background (see start_blender_install); starting the
    // editor never waits for it.
    let paths = desktop_paths(app)?;
    fs::create_dir_all(&paths.storage_dir).map_err(|error| error.to_string())?;
    fs::create_dir_all(&paths.logs_dir).map_err(|error| error.to_string())?;

    // Never adopt whatever already answers /health (spec §F.1): always run our own sidecar on an
    // OS-assigned port and trust it only after it proves this launch's token.
    stop_backend(state);
    let launch_token = sidecar_auth::new_launch_token()
        .map_err(|error| format!("Cannot generate the launch token: {error}"))?;
    let backend_port =
        find_free_port().ok_or_else(|| "No local backend port is available.".to_string())?;
    let (backend_status, last_error) =
        match start_backend_sidecar(app, &paths, backend_port, &launch_token) {
            Ok(child) => {
                state.backend_child = Some(child);
                if !wait_for_backend(backend_port) {
                    (
                        "failed".to_string(),
                        Some("Backend sidecar did not become ready in time.".to_string()),
                    )
                } else if !sidecar_proves_token(backend_port, &launch_token) {
                    stop_backend(state);
                    (
                        "failed".to_string(),
                        Some(
                            "Local backend failed the launch handshake; another program may be using its port."
                                .to_string(),
                        ),
                    )
                } else {
                    ("ready".to_string(), None)
                }
            }
            Err(error) => ("failed".to_string(), Some(error)),
        };
    let sidecar_token = (backend_status == "ready").then(|| launch_token.clone());
    state.launch_token = Some(launch_token);

    let blender_status = if paths.blender_bin.is_file() {
        "installed"
    } else if app.state::<InstallState>().running.load(Ordering::SeqCst) {
        "downloading"
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
        sidecar_token,
    };
    state.runtime = Some(runtime.clone());
    Ok(runtime)
}

fn start_backend_sidecar(
    app: &AppHandle,
    paths: &DesktopPaths,
    port: u16,
    launch_token: &str,
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

    if let Some(origins) = configured_storage_origins()? {
        command.env("WORKER_ALLOWED_STORAGE_ORIGINS", origins);
    }
    command
        .env("CONTROL_PLANE_SERVICE_TOKEN", launch_token)
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
    report: &mut dyn FnMut(&InstallProgress),
) -> InstallProgress {
    const NAME: &str = "blender";
    if paths.blender_bin.is_file() {
        return InstallProgress::finished(
            NAME,
            "installed",
            "Bộ dựng hình 3D đã được cài đặt.".to_string(),
            Some(paths.blender_bin.to_string_lossy().to_string()),
        );
    }
    let manifest = match read_dependency_manifest(app) {
        Ok(manifest) => manifest,
        Err(error) => return InstallProgress::failed(NAME, error),
    };
    if manifest.archive_type.to_lowercase() != "zip" {
        return InstallProgress::failed(NAME, "Preview renderer artifact phải là file ZIP.");
    }
    let sha256 = configured_blender_sha(&manifest);
    if !is_sha256(&sha256) {
        return InstallProgress::failed(
            NAME,
            "Preview renderer chưa có SHA-256 hợp lệ. Release/dev setup phải cấu hình artifact nội bộ trước.",
        );
    }

    let download_path = paths.download_path(&manifest);
    // A local artifact (developer machines) is placed where the installer looks for an
    // already-downloaded archive; it is used only if its SHA-256 matches.
    if let Some(local) = env::var_os(BLENDER_ARTIFACT_PATH_ENV)
        .map(PathBuf::from)
        .filter(|path| path.is_file())
    {
        if let Some(parent) = download_path.parent() {
            let _ = fs::create_dir_all(parent);
        }
        if let Err(error) = fs::copy(&local, &download_path) {
            return InstallProgress::failed(NAME, format!("Không sao chép được artifact: {error}"));
        }
    }
    let url = artifact_url(&manifest).unwrap_or_default();
    if url.is_empty() && !download_path.is_file() {
        return InstallProgress::failed(
            NAME,
            "Preview renderer chưa cấu hình internal artifact. Hãy set KUSSHOES_BLENDER_ARTIFACT_PATH hoặc KUSSHOES_BLENDER_ARTIFACT_URL.",
        );
    }
    if url.contains("download.blender.org") {
        return InstallProgress::failed(
            NAME,
            "Preview renderer phải lấy từ internal artifact, không tải trực tiếp từ download.blender.org.",
        );
    }

    let install_root = paths.tools_dir.join(&manifest.name);
    let result = runtime_installer::install_zip(
        &runtime_installer::Artifact { url: &url, sha256: &sha256 },
        &download_path,
        &install_root,
        Path::new(&manifest.exe_relative_path),
        &mut |progress| report(&InstallProgress::from_installer(NAME, progress)),
    );
    match result {
        Ok(exe) => InstallProgress::finished(
            NAME,
            "installed",
            format!(
                "Bộ dựng hình 3D đã cài đặt xong (khoảng {}).",
                manifest.installed_size_estimate
            ),
            Some(exe.to_string_lossy().to_string()),
        ),
        Err(error) => {
            let _ = fs::create_dir_all(&paths.logs_dir);
            let _ = fs::write(
                paths.logs_dir.join("dependency-install.err.log"),
                error.to_string(),
            );
            let hint = match error {
                runtime_installer::InstallError::Http(_) => {
                    "Không tải được bộ dựng hình 3D. Kiểm tra kết nối mạng rồi bấm Thử lại."
                }
                runtime_installer::InstallError::Io(_) => {
                    "Không ghi được file (ổ đĩa có thể đã đầy). Giải phóng dung lượng rồi bấm Thử lại."
                }
                _ => "Cài bộ dựng hình 3D thất bại. Bấm Thử lại; nếu vẫn lỗi, mở Logs để gửi cho team.",
            };
            InstallProgress::failed(NAME, hint)
        }
    }
}

fn artifact_url(manifest: &DependencyManifest) -> Option<String> {
    env::var(BLENDER_ARTIFACT_URL_ENV)
        .ok()
        .map(|value| value.trim().to_string())
        .filter(|value| !value.is_empty())
        .or_else(|| {
            let value = manifest.download_url.trim();
            (!value.is_empty()).then(|| value.to_string())
        })
}

/// First launch fetches the renderer by itself when the build ships a verified artifact source.
fn should_auto_install_blender(app: &AppHandle) -> bool {
    if env::var(AUTO_INSTALL_BLENDER_ENV).ok().as_deref() == Some("0") {
        return false;
    }
    let Ok(manifest) = read_dependency_manifest(app) else {
        return false;
    };
    is_sha256(&configured_blender_sha(&manifest))
        && (env::var_os(BLENDER_ARTIFACT_PATH_ENV).is_some() || artifact_url(&manifest).is_some())
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
    // OS-assigned ephemeral port: nothing predictable for another process to squat.
    let listener = TcpListener::bind(("127.0.0.1", 0)).ok()?;
    listener.local_addr().ok().map(|address| address.port())
}

/// True only when the process on `port` returns HMAC(launch_token, fresh nonce).
fn sidecar_proves_token(port: u16, launch_token: &str) -> bool {
    let Ok(nonce) = sidecar_auth::new_nonce() else {
        return false;
    };
    http_get(port, &format!("/handshake?nonce={nonce}"))
        .and_then(|raw| sidecar_auth::parse_handshake_response(&raw))
        .is_some_and(|proof| sidecar_auth::verify_proof(launch_token, &nonce, &proof))
}

/// Storage origin allowlist for the sidecar: runtime env var first, then the build-time value.
fn configured_storage_origins() -> Result<Option<String>, String> {
    let raw = env::var(STORAGE_ORIGINS_ENV)
        .ok()
        .or_else(|| option_env!("KUSSHOES_STORAGE_ORIGINS").map(str::to_owned));
    match raw {
        Some(value) if !value.trim().is_empty() => sidecar_auth::storage_origins_env(&value).map(Some),
        _ => Ok(None),
    }
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
        .plugin(tauri_plugin_updater::Builder::new().build())
        .manage(Mutex::new(RuntimeState::default()))
        .manage(InstallState::default())
        .manage(UpdateState::default())
        .setup(|app| {
            let handle = app.handle().clone();
            let renderer_missing = desktop_paths(&handle)
                .map(|paths| !paths.blender_bin.is_file())
                .unwrap_or(false);
            if renderer_missing && should_auto_install_blender(&handle) {
                start_blender_install(&handle);
            }
            tauri::async_runtime::spawn(check_for_update(handle));
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            get_desktop_runtime,
            install_dependency,
            get_install_progress,
            get_app_update,
            install_app_update,
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
