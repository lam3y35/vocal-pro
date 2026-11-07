#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::path::PathBuf;
use vocalpro_lib::AppContext;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    tracing_subscriber::fmt()
        .with_env_filter(tracing_subscriber::EnvFilter::from_default_env())
        .init();

    let app_data_dir = dirs::data_dir()
        .unwrap_or_else(|| PathBuf::from("."))
        .join("VocalPro");

    let python_bin = std::env::var("VOCALPRO_PYTHON")
        .map(PathBuf::from)
        .unwrap_or_else(|_| PathBuf::from("python3"));

    let worker_dir = std::env::var("VOCALPRO_WORKER_DIR")
        .map(PathBuf::from)
        .unwrap_or_else(|_| PathBuf::from("worker"));

    let ctx = AppContext::new(app_data_dir, python_bin, worker_dir, false)?;
    println!(
        "VocalPro v3 Core initialized at {}",
        ctx.app_data_dir.display()
    );
    Ok(())
}
