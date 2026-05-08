use serde::{Deserialize, Serialize};
use std::process::{Child, Command};
use std::sync::Mutex;
use tauri::State;

struct ProxyProcess(Mutex<Option<Child>>);

#[derive(Deserialize)]
struct ProxyConfig {
    port: u16,
    openai_url: String,
    openai_key: String,
    anthropic_url: String,
    anthropic_key: String,
    mode: String,
    strong_k: u32,
    python_path: String,
}

#[derive(Serialize)]
struct ProxyStatus {
    running: bool,
    port: u16,
    pid: Option<u32>,
    message: String,
}

#[tauri::command]
fn start_proxy(config: ProxyConfig, state: State<ProxyProcess>) -> Result<ProxyStatus, String> {
    let mut proc = state.0.lock().map_err(|e| e.to_string())?;

    if let Some(ref child) = *proc {
        return Ok(ProxyStatus {
            running: true,
            port: config.port,
            pid: Some(child.id()),
            message: "Proxy is already running".into(),
        });
    }

    let mut cmd = Command::new(&config.python_path);
    cmd.arg("-m").arg("agentpreproxy.main")
        .arg("--host").arg("127.0.0.1")
        .arg("--port").arg(config.port.to_string())
        .arg("--mode").arg(&config.mode)
        .arg("--strong-k").arg(config.strong_k.to_string())
        .arg("--debug");

    if !config.openai_url.is_empty() {
        cmd.arg("--openai-url").arg(&config.openai_url);
    }
    if !config.openai_key.is_empty() {
        cmd.arg("--openai-key").arg(&config.openai_key);
    }
    if !config.anthropic_url.is_empty() {
        cmd.arg("--anthropic-url").arg(&config.anthropic_url);
    }
    if !config.anthropic_key.is_empty() {
        cmd.arg("--anthropic-key").arg(&config.anthropic_key);
    }

    let child = cmd.spawn().map_err(|e| format!("Failed to start proxy: {}", e))?;
    let pid = child.id();
    *proc = Some(child);

    Ok(ProxyStatus {
        running: true,
        port: config.port,
        pid: Some(pid),
        message: format!("Proxy started on 127.0.0.1:{}", config.port),
    })
}

#[tauri::command]
fn stop_proxy(state: State<ProxyProcess>) -> Result<ProxyStatus, String> {
    let mut proc = state.0.lock().map_err(|e| e.to_string())?;

    if let Some(ref mut child) = *proc {
        child.kill().map_err(|e| format!("Failed to kill: {}", e))?;
        child.wait().ok();
        *proc = None;
        Ok(ProxyStatus {
            running: false,
            port: 0,
            pid: None,
            message: "Proxy stopped".into(),
        })
    } else {
        Ok(ProxyStatus {
            running: false,
            port: 0,
            pid: None,
            message: "Proxy was not running".into(),
        })
    }
}

#[tauri::command]
fn get_status(state: State<ProxyProcess>) -> ProxyStatus {
    let proc = state.0.lock().unwrap();
    match &*proc {
        Some(child) => ProxyStatus {
            running: true,
            port: 0,
            pid: Some(child.id()),
            message: "Running".into(),
        },
        None => ProxyStatus {
            running: false,
            port: 0,
            pid: None,
            message: "Stopped".into(),
        },
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_shell::init())
        .manage(ProxyProcess(Mutex::new(None)))
        .invoke_handler(tauri::generate_handler![start_proxy, stop_proxy, get_status])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
