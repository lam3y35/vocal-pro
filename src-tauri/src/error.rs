use serde::{Deserialize, Serialize};
use thiserror::Error;

#[derive(Debug, Error, Serialize, Deserialize, Clone)]
#[serde(tag = "kind", content = "message")]
pub enum AppError {
    #[error("Worker error ({code}): {message}")]
    Worker {
        code: String,
        message: String,
        detail: Option<String>,
    },
    #[error("Audio I/O or decode error: {0}")]
    Audio(String),
    #[error("Database error: {0}")]
    Database(String),
    #[error("Invalid input: {0}")]
    InvalidInput(String),
    #[error("System error: {0}")]
    System(String),
}

impl From<std::io::Error> for AppError {
    fn from(err: std::io::Error) -> Self {
        Self::System(err.to_string())
    }
}

impl From<rusqlite::Error> for AppError {
    fn from(err: rusqlite::Error) -> Self {
        Self::Database(err.to_string())
    }
}

impl From<serde_json::Error> for AppError {
    fn from(err: serde_json::Error) -> Self {
        Self::System(err.to_string())
    }
}

pub type AppResult<T> = Result<T, AppError>;
