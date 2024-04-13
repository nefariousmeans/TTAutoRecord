use chrono::Local;
use regex::Regex;
use std::collections::HashMap;
use std::env;
use std::fs::{self, File};
use std::io::{self, Read, Write};
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::sync::Arc;
use tokio::sync::Mutex;
use tokio::time::{sleep, Duration};
use tokio::runtime::Builder;

static STREAM_LINKS_JSON_PATH: &str = "../json/stream_links.json";
static LOCK_FILES_DIR: &str = "../lock_files";
static VIDEOS_DIR: &str = "../videos";

async fn clear_lock_files(directory: &str) -> std::io::Result<()> {
    let paths = fs::read_dir(directory)?;
    for path in paths {
        let path = path?.path();
        if path.is_file() && path.extension().and_then(|s| s.to_str()) == Some("lock") {
            fs::remove_file(path)?;
        }
    }
    Ok(())
}

async fn read_stream_links() -> Result<HashMap<String, String>, Box<dyn std::error::Error>> {
    let mut contents = String::new();
    File::open(STREAM_LINKS_JSON_PATH)?.read_to_string(&mut contents)?;
    Ok(serde_json::from_str(&contents)?)
}

async fn download_livestream(username: &str, stream_link: &str, lock: Arc<Mutex<()>>, ffmpeg_path: &Path) -> Result<(), Box<dyn std::error::Error>> {
    let _lock = lock.lock().await;
    let lock_file_path = format!("{}/{}.lock", LOCK_FILES_DIR, username);

    let stream_id = extract_stream_id(stream_link);
    let datetime = Local::now().format("%Y-%m-%d_%H-%M-%S").to_string();

    let video_folder = format!("../videos/{}", username);
    fs::create_dir_all(&video_folder)?;

    let video_path = format!("{}/{}_{}.mkv", VIDEOS_DIR, username, datetime);

    let status = Command::new(ffmpeg_path)
        .arg("-i")
        .arg(stream_link)
        .arg("-c:v")
        .arg("copy")
        .arg("-c:a")
        .arg("aac")
        .arg("-y")
        .arg(&video_path)
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status()?;
    
    if status.success() {
        sleep(Duration::from_secs(1)).await;
    }

    fs::remove_file(lock_file_path)?;
    Ok(())
}

fn extract_stream_id(url: &str) -> String {
    Regex::new(r"stream-(\d+)_")
        .unwrap()
        .captures(url)
        .and_then(|caps| caps.get(1).map(|m| m.as_str().to_string()))
        .unwrap_or_else(|| "unknownid".to_string())
}

fn current_exe_path() -> Result<PathBuf, Box<dyn std::error::Error>> {
    Ok(env::current_exe()?)
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let lock_files_dir = "../lock_files";
    let videos_dir = "../videos";

    // Clear .lock files from lock_files directory
    if let Err(e) = clear_lock_files(lock_files_dir).await {
        eprintln!("Failed to clear lock files: {}", e);
    }

    fs::create_dir_all(lock_files_dir)?;
    fs::create_dir_all(videos_dir)?;

    let runtime = Builder::new_multi_thread()
        .worker_threads(128)
        .enable_all()
        .build()
        .unwrap();

    loop {
        let links = read_stream_links().await?;
        for (username, stream_link) in links.iter() {
            let lock_file_path = format!("{}/{}.lock", lock_files_dir, username);
            if !Path::new(&lock_file_path).exists() {
                println!("Downloading livestream for user: {}", username);
                if let Err(e) = fs::write(&lock_file_path, "") {
                    eprintln!("Error creating lock file for user {}: {}", username, e);
                    continue;
                }
                let lock = Arc::new(Mutex::new(()));
                let username = username.clone(); // Clone username to move into the closure
                let stream_link = stream_link.clone(); // Clone stream_link to move into the closure
                let handle = runtime.handle().clone(); // Clone handle for spawning tasks
                let ffmpeg_path = current_exe_path()?.parent().unwrap().join("ffmpeg.exe");
                handle.spawn(async move {
                    if let Err(e) = download_livestream(&username, &stream_link, lock, &ffmpeg_path).await {
                        eprintln!("Error downloading livestream for user {}: {}", username, e);
                    } else {
                        println!("Livestream downloaded successfully for user: {}", username);
                    }
                });
                sleep(Duration::from_secs(1)).await; // Add a 1-second delay
            } else {

            }
        }
        sleep(Duration::from_secs(3)).await;
    }
}
