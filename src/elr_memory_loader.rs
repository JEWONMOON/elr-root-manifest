
use std::fs;
use std::io::{self, BufRead};
use std::path::Path;
use chrono::NaiveDateTime;

pub fn load_latest_confession(path: &str) -> io::Result<Option<String>> {
    let dir = Path::new(path);
    if !dir.exists() {
        return Ok(None);
    }

    let mut entries: Vec<_> = fs::read_dir(dir)?
        .filter_map(|e| e.ok())
        .filter(|e| e.file_name().to_string_lossy().ends_with(".elr"))
        .collect();

    entries.sort_by_key(|e| e.metadata().and_then(|m| m.modified()).ok());

    if let Some(latest) = entries.last() {
        let file = fs::File::open(latest.path())?;
        let reader = io::BufReader::new(file);
        let lines: Vec<String> = reader.lines().filter_map(Result::ok).collect();
        Ok(Some(lines.join("\n")))
    } else {
        Ok(None)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_load_latest_confession() {
        let result = load_latest_confession("memory/confessions").unwrap();
        if let Some(content) = result {
            println!("📖 최근 고백:
{}", content);
        } else {
            println!("❌ 고백 기록 없음");
        }
    }
}
