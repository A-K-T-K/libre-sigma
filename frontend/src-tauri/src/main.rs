// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde_json::Value;
use std::env;
use std::io::{BufRead, BufReader};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::{Arc, Mutex};
use std::thread;
use tauri::{Manager, State};

#[cfg(target_os = "windows")]
use std::os::windows::process::CommandExt;

#[cfg(target_os = "windows")]
const CREATE_NO_WINDOW: u32 = 0x08000000;

struct AppState {
  backend_port: Arc<Mutex<Option<u16>>>,
  sidecar_child: Arc<Mutex<Option<Child>>>,
}

#[tauri::command]
fn get_backend_port(state: State<AppState>) -> Result<u16, String> {
  let port_guard = state.backend_port.lock().map_err(|e| e.to_string())?;
  match *port_guard {
    Some(port) => Ok(port),
    None => Err("Backend engine is initializing, port not yet available".to_string()),
  }
}

/// Locates the backend entry Python script across dev layouts.
fn find_backend_entry_script() -> Option<PathBuf> {
  let mut candidate_dirs: Vec<PathBuf> = Vec::new();
  if let Ok(cwd) = env::current_dir() {
    candidate_dirs.push(cwd.clone());
    candidate_dirs.push(cwd.join(".."));
    candidate_dirs.push(cwd.join("..").join(".."));
  }
  if let Ok(current_exe) = env::current_exe() {
    if let Some(exe_dir) = current_exe.parent() {
      candidate_dirs.push(exe_dir.to_path_buf());
      candidate_dirs.push(exe_dir.join(".."));
      candidate_dirs.push(exe_dir.join("..").join(".."));
      candidate_dirs.push(exe_dir.join("..").join("..").join(".."));
    }
  }

  for dir in candidate_dirs {
    let script = dir.join("backend_entry.py");
    if script.exists() && script.is_file() {
      return Some(script);
    }
  }
  None
}

/// Locates the backend precompiled executable in production release layouts.
fn find_backend_executable() -> Option<PathBuf> {
  // In dev/debug builds, always prefer Python dev launch for hot reloading and clean dependency resolution
  if cfg!(debug_assertions) {
    return None;
  }

  let mut candidate_paths: Vec<PathBuf> = Vec::new();

  // 1. Current executable directory
  if let Ok(current_exe) = env::current_exe() {
    if let Some(exe_dir) = current_exe.parent() {
      candidate_paths.push(exe_dir.join("libresigma-server-x86_64-pc-windows-msvc.exe"));
      candidate_paths.push(exe_dir.join("libresigma-server.exe"));
      candidate_paths.push(exe_dir.join("binaries").join("libresigma-server-x86_64-pc-windows-msvc.exe"));
      candidate_paths.push(exe_dir.join("binaries").join("libresigma-server.exe"));
      candidate_paths.push(exe_dir.join("libretab-server-x86_64-pc-windows-msvc.exe"));
      candidate_paths.push(exe_dir.join("libretab-server.exe"));
      candidate_paths.push(exe_dir.join("binaries").join("libretab-server-x86_64-pc-windows-msvc.exe"));
      candidate_paths.push(exe_dir.join("binaries").join("libretab-server.exe"));
    }
  }

  // 2. Current working directory
  if let Ok(cwd) = env::current_dir() {
    candidate_paths.push(cwd.join("binaries").join("libresigma-server-x86_64-pc-windows-msvc.exe"));
    candidate_paths.push(cwd.join("binaries").join("libresigma-server.exe"));
    candidate_paths.push(cwd.join("dist").join("libresigma-server").join("libresigma-server.exe"));
    candidate_paths.push(cwd.join("binaries").join("libretab-server-x86_64-pc-windows-msvc.exe"));
    candidate_paths.push(cwd.join("binaries").join("libretab-server.exe"));
    candidate_paths.push(cwd.join("dist").join("libretab-server").join("libretab-server.exe"));
  }

  for path in candidate_paths {
    if path.exists() && path.is_file() {
      println!("[Tauri] Found backend engine executable at: {:?}", path);
      return Some(path);
    }
  }

  None
}

fn main() {
  let backend_port = Arc::new(Mutex::new(None));
  let sidecar_child: Arc<Mutex<Option<Child>>> = Arc::new(Mutex::new(None));

  let port_for_setup = Arc::clone(&backend_port);
  let child_for_setup = Arc::clone(&sidecar_child);
  let child_for_event = Arc::clone(&sidecar_child);

  tauri::Builder::default()
    .manage(AppState {
      backend_port: Arc::clone(&backend_port),
      sidecar_child: Arc::clone(&sidecar_child),
    })
    .invoke_handler(tauri::generate_handler![get_backend_port])
    .setup(move |app| {
      let app_handle = app.handle();
      let port_clone = Arc::clone(&port_for_setup);
      let child_clone = Arc::clone(&child_for_setup);

      // Locate backend executable or fallback to Python dev command
      let backend_exe_opt = find_backend_executable();

      let mut spawn_cmd = if let Some(ref exe_path) = backend_exe_opt {
        let mut c = Command::new(exe_path);
        c.arg("--port").arg("0");
        if let Some(parent_dir) = exe_path.parent() {
          c.current_dir(parent_dir);
        }
        c
      } else if let Some(script_path) = find_backend_entry_script() {
        println!("[Tauri] Launching Python dev backend from: {:?}", script_path);
        let mut c = Command::new("python");
        c.arg("-u").arg(&script_path).arg("--port").arg("0");
        if let Some(parent_dir) = script_path.parent() {
          c.current_dir(parent_dir);
        }
        c
      } else {
        println!("[Tauri] No precompiled binary found. Attempting Python dev launch...");
        let mut c = Command::new("python");
        c.arg("-u").arg("backend_entry.py").arg("--port").arg("0");
        c
      };

      spawn_cmd.stdout(Stdio::piped());
      spawn_cmd.stderr(Stdio::piped());
      spawn_cmd.stdin(Stdio::piped());

      #[cfg(target_os = "windows")]
      spawn_cmd.creation_flags(CREATE_NO_WINDOW);

      match spawn_cmd.spawn() {
        Ok(mut child) => {
          println!("[Tauri] Successfully launched backend process (PID: {}).", child.id());

          let stdout = child.stdout.take();
          let stderr = child.stderr.take();

          *child_clone.lock().unwrap() = Some(child);

          // Stdout stream reader thread
          if let Some(out) = stdout {
            let port_arc = Arc::clone(&port_clone);
            let handle_clone = app_handle.clone();

            thread::spawn(move || {
              let reader = BufReader::new(out);
              for line_result in reader.lines() {
                if let Ok(line) = line_result {
                  println!("[Backend Engine] {}", line);

                  // Intercept dynamic handshake JSON
                  if line.contains("\"status\"") && line.contains("\"port\"") {
                    if let Ok(parsed) = serde_json::from_str::<Value>(&line) {
                      if parsed["status"] == "ready" {
                        if let Some(port_num) = parsed["port"].as_u64() {
                          let port = port_num as u16;
                          *port_arc.lock().unwrap() = Some(port);
                          println!("[Tauri] Backend ready on dynamic port: {}", port);
                          let _ = handle_clone.emit_all("backend-ready", port);
                        }
                      }
                    }
                  }
                }
              }
            });
          }

          // Stderr stream reader thread
          if let Some(err) = stderr {
            thread::spawn(move || {
              let reader = BufReader::new(err);
              for line_result in reader.lines() {
                if let Ok(line) = line_result {
                  eprintln!("[Backend Engine Stderr] {}", line);
                }
              }
            });
          }
        }
        Err(e) => {
          eprintln!("[Tauri Error] Failed to launch backend engine process: {}", e);
        }
      }

      Ok(())
    })
    .on_window_event(move |event| {
      if let tauri::WindowEvent::Destroyed = event.event() {
        if let Ok(mut lock) = child_for_event.lock() {
          if let Some(mut child) = lock.take() {
            println!("[Tauri] Window destroyed. Killing backend process (PID: {})...", child.id());
            let _ = child.kill();
          }
        }
      }
    })
    .run(tauri::generate_context!())
    .expect("error while running tauri application");
}
