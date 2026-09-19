use rand::{rngs::OsRng, RngCore};
use serde::{Deserialize, Serialize};
use std::{env, path::Path, sync::Mutex, time::Duration};
use tauri::{path::BaseDirectory, Manager, RunEvent, State};
use tauri_plugin_shell::{
    process::{CommandChild, CommandEvent},
    ShellExt,
};

const READY_PREFIX: &str = "WFMHUB2_READY ";
const ERROR_PREFIX: &str = "WFMHUB2_ERROR ";
const PORTABLE_HOME_ERROR: &str = "The portable WFMHub folder is not writable. Move WFMHub to a writable folder or grant write access.";
const STARTUP_TIMEOUT: Duration = Duration::from_secs(30);

#[derive(Clone, Debug, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
enum EnginePhase {
    Starting,
    Ready,
    Failed,
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct EngineConnection {
    phase: EnginePhase,
    base_url: Option<String>,
    session_token: Option<String>,
    message: Option<String>,
}

impl Default for EngineConnection {
    fn default() -> Self {
        Self {
            phase: EnginePhase::Starting,
            base_url: None,
            session_token: None,
            message: None,
        }
    }
}

impl EngineConnection {
    fn mark_ready(&mut self, port: u16, session_token: String) {
        if self.phase != EnginePhase::Starting {
            return;
        }

        self.phase = EnginePhase::Ready;
        self.base_url = Some(format!("http://127.0.0.1:{port}/api"));
        self.session_token = Some(session_token);
        self.message = None;
    }

    fn mark_failed(&mut self, message: impl Into<String>) {
        if self.phase == EnginePhase::Failed {
            return;
        }

        self.phase = EnginePhase::Failed;
        self.base_url = None;
        self.session_token = None;
        self.message = Some(message.into());
    }
}

#[derive(Default)]
struct EngineState {
    connection: Mutex<EngineConnection>,
    child: Mutex<Option<CommandChild>>,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct ReadyPayload {
    port: u16,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct ErrorPayload {
    code: String,
    message: String,
}

fn parse_readiness_line(line: &[u8]) -> Result<Option<u16>, String> {
    let decoded = String::from_utf8_lossy(line);
    let Some(payload) = decoded.trim().strip_prefix(READY_PREFIX) else {
        return Ok(None);
    };
    let ready: ReadyPayload = serde_json::from_str(payload)
        .map_err(|error| format!("invalid engine readiness payload: {error}"))?;
    if ready.port == 0 {
        return Err("engine readiness payload contained port 0".to_owned());
    }
    Ok(Some(ready.port))
}

fn parse_error_line(line: &[u8]) -> Result<Option<String>, String> {
    let decoded = String::from_utf8_lossy(line);
    let Some(payload) = decoded.trim().strip_prefix(ERROR_PREFIX) else {
        return Ok(None);
    };
    let failure: ErrorPayload = serde_json::from_str(payload)
        .map_err(|error| format!("invalid engine error payload: {error}"))?;
    if failure.code != "portable_home_not_writable" || failure.message != PORTABLE_HOME_ERROR {
        return Err("engine reported an unrecognized startup error".to_owned());
    }
    Ok(Some(failure.message))
}

fn generate_session_token() -> String {
    let mut bytes = [0_u8; 32];
    OsRng.fill_bytes(&mut bytes);
    const HEX: &[u8; 16] = b"0123456789abcdef";
    let mut token = String::with_capacity(bytes.len() * 2);
    for byte in bytes {
        token.push(HEX[(byte >> 4) as usize] as char);
        token.push(HEX[(byte & 0x0f) as usize] as char);
    }
    token
}

#[tauri::command]
fn get_engine_connection(state: State<'_, EngineState>) -> Result<EngineConnection, String> {
    state
        .connection
        .lock()
        .map(|connection| connection.clone())
        .map_err(|_| "engine connection state is unavailable".to_owned())
}

fn fail_engine(state: &EngineState, message: impl Into<String>) {
    if let Ok(mut connection) = state.connection.lock() {
        connection.mark_failed(message);
    }
}

fn stop_engine(state: &EngineState) {
    if let Ok(mut child) = state.child.lock() {
        if let Some(child) = child.take() {
            let _ = child.kill();
        }
    }
}

fn resolve_ducklake_extension(app: &tauri::App, home: &Path) -> Result<std::path::PathBuf, String> {
    let portable = home.join("duckdb_extensions/ducklake.duckdb_extension");
    if portable.is_file() {
        return Ok(portable);
    }

    let bundled = app
        .path()
        .resolve(
            "duckdb_extensions/ducklake.duckdb_extension",
            BaseDirectory::Resource,
        )
        .map_err(|error| format!("DuckLake resource path could not be resolved: {error}"))?;
    if !bundled.is_file() {
        return Err("the bundled DuckLake extension is missing".to_owned());
    }
    Ok(bundled)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(EngineState::default())
        .invoke_handler(tauri::generate_handler![get_engine_connection])
        .setup(|app| {
            let session_token = generate_session_token();
            // Portable mode keeps data next to WFMHub.exe. A future installed/server
            // edition can override this contract without changing the Python domains.
            let home = match env::current_exe()
                .ok()
                .and_then(|executable| executable.parent().map(ToOwned::to_owned))
            {
                Some(path) => path,
                None => {
                    fail_engine(
                        app.state::<EngineState>().inner(),
                        "WFMHub executable home could not be resolved",
                    );
                    return Ok(());
                }
            };
            let extension_path = match resolve_ducklake_extension(app, &home) {
                Ok(path) => path,
                Err(error) => {
                    fail_engine(app.state::<EngineState>().inner(), error);
                    return Ok(());
                }
            };

            let home_arg = home.to_string_lossy().into_owned();
            let extension_arg = extension_path.to_string_lossy().into_owned();
            let sidecar = match app.shell().sidecar("wfmhub-engine") {
                Ok(sidecar) => sidecar,
                Err(error) => {
                    fail_engine(
                        app.state::<EngineState>().inner(),
                        format!("WFMHub engine sidecar could not be resolved: {error}"),
                    );
                    return Ok(());
                }
            };
            let command = sidecar
                .env("WFMHUB2_SESSION_TOKEN", &session_token)
                .env("WFMHUB2_PARENT_PID", std::process::id().to_string())
                .args([
                    "--home",
                    &home_arg,
                    "--ducklake-extension",
                    &extension_arg,
                    "serve",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "0",
                ]);

            let (mut events, child) = match command.spawn() {
                Ok(process) => process,
                Err(error) => {
                    fail_engine(
                        app.state::<EngineState>().inner(),
                        format!("WFMHub engine could not be started: {error}"),
                    );
                    return Ok(());
                }
            };

            match app.state::<EngineState>().child.lock() {
                Ok(mut owned_child) => *owned_child = Some(child),
                Err(_) => {
                    let _ = child.kill();
                    fail_engine(
                        app.state::<EngineState>().inner(),
                        "WFMHub engine process state is unavailable",
                    );
                    return Ok(());
                }
            }

            let event_handle = app.handle().clone();
            let readiness_token = session_token.clone();
            tauri::async_runtime::spawn(async move {
                while let Some(event) = events.recv().await {
                    let state = event_handle.state::<EngineState>();
                    match event {
                        CommandEvent::Stdout(line) => match parse_readiness_line(&line) {
                            Ok(Some(port)) => {
                                if let Ok(mut connection) = state.connection.lock() {
                                    connection.mark_ready(port, readiness_token.clone());
                                }
                            }
                            Ok(None) => match parse_error_line(&line) {
                                Ok(Some(message)) => {
                                    fail_engine(state.inner(), message);
                                    stop_engine(state.inner());
                                }
                                Ok(None) => {}
                                Err(error) => {
                                    fail_engine(state.inner(), error);
                                    stop_engine(state.inner());
                                }
                            },
                            Err(error) => {
                                fail_engine(state.inner(), error);
                                stop_engine(state.inner());
                            }
                        },
                        CommandEvent::Error(error) => {
                            fail_engine(
                                state.inner(),
                                format!("WFMHub engine process error: {error}"),
                            );
                            stop_engine(state.inner());
                        }
                        CommandEvent::Terminated(payload) => {
                            fail_engine(
                                state.inner(),
                                format!("WFMHub engine stopped unexpectedly ({:?})", payload.code),
                            );
                            stop_engine(state.inner());
                        }
                        CommandEvent::Stderr(_) => {
                            // The sidecar owns log persistence. Do not expose arbitrary stderr,
                            // which may contain paths or operational details, to the webview.
                        }
                        _ => {}
                    }
                }
            });

            let timeout_handle = app.handle().clone();
            std::thread::spawn(move || {
                std::thread::sleep(STARTUP_TIMEOUT);
                let state = timeout_handle.state::<EngineState>();
                let timed_out = state
                    .connection
                    .lock()
                    .map(|connection| connection.phase == EnginePhase::Starting)
                    .unwrap_or(false);
                if timed_out {
                    fail_engine(state.inner(), "WFMHub engine startup timed out");
                    stop_engine(state.inner());
                }
            });

            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building WFMHub 2");

    app.run(|app_handle, event| {
        if matches!(event, RunEvent::ExitRequested { .. } | RunEvent::Exit) {
            stop_engine(app_handle.state::<EngineState>().inner());
        }
    });
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_the_engine_readiness_contract() {
        assert_eq!(
            parse_readiness_line(br#"WFMHUB2_READY {"port":43127}"#).unwrap(),
            Some(43127)
        );
        assert_eq!(parse_readiness_line(b"ordinary engine log").unwrap(), None);
    }

    #[test]
    fn rejects_invalid_readiness_payloads() {
        assert!(parse_readiness_line(br#"WFMHUB2_READY {"port":0}"#).is_err());
        assert!(parse_readiness_line(b"WFMHUB2_READY not-json").is_err());
        assert!(parse_readiness_line(br#"WFMHUB2_READY {"port":43127,"token":"leak"}"#).is_err());
    }

    #[test]
    fn accepts_only_the_known_sanitized_startup_error() {
        let line = format!(
            r#"WFMHUB2_ERROR {{"code":"portable_home_not_writable","message":"{PORTABLE_HOME_ERROR}"}}"#
        );
        assert_eq!(
            parse_error_line(line.as_bytes()).unwrap(),
            Some(PORTABLE_HOME_ERROR.to_owned())
        );
        assert!(parse_error_line(
            br#"WFMHUB2_ERROR {"code":"unexpected","message":"sensitive details"}"#
        )
        .is_err());
        assert_eq!(parse_error_line(b"ordinary engine log").unwrap(), None);
    }

    #[test]
    fn only_a_starting_engine_can_become_ready() {
        let mut connection = EngineConnection::default();
        connection.mark_failed("first failure");
        connection.mark_ready(43127, "secret".to_owned());

        assert_eq!(connection.phase, EnginePhase::Failed);
        assert!(connection.base_url.is_none());
        assert!(connection.session_token.is_none());
    }

    #[test]
    fn session_tokens_are_256_bit_lowercase_hex() {
        let first = generate_session_token();
        let second = generate_session_token();

        assert_eq!(first.len(), 64);
        assert!(first.chars().all(|character| character.is_ascii_hexdigit()));
        assert_eq!(first, first.to_ascii_lowercase());
        assert_ne!(first, second);
    }
}
