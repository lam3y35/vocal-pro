#![recursion_limit = "512"]
#![allow(
    unknown_lints,
    clippy::too_many_arguments,
    clippy::large_enum_variant,
    clippy::chunks_exact_to_as_chunks
)]

pub mod audio;
pub mod commands;
pub mod db;
pub mod error;
pub mod models;
pub mod system;
pub mod worker;

pub use commands::AppContext;
pub use error::{AppError, AppResult};
