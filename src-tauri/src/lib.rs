use std::env;
use tauri::{path::BaseDirectory, Manager};
use tauri_plugin_shell::ShellExt;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            let extension_path = app
                .path()
                .resolve(
                    "duckdb_extensions/ducklake.duckdb_extension",
                    BaseDirectory::Resource,
                )?;

            // Portable mode keeps data next to WFMHub.exe. A future installed/server
            // edition can override this contract without changing the Python domains.
            let home = env::current_exe()?
                .parent()
                .ok_or_else(|| std::io::Error::other("WFMHub executable has no parent directory"))?
                .to_path_buf();

            let home_arg = home.to_string_lossy().to_string();
            let extension_arg = extension_path.to_string_lossy().to_string();

            let command = app
                .shell()
                .sidecar("wfmhub-engine")?
                .args([
                    "--home",
                    &home_arg,
                    "--ducklake-extension",
                    &extension_arg,
                    "serve",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "8765",
                ]);

            let (mut events, _child) = command.spawn()?;

            tauri::async_runtime::spawn(async move {
                // Drain sidecar events so stdout/stderr pipes do not block the engine.
                while events.recv().await.is_some() {}
            });

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running WFMHub 2");
}
