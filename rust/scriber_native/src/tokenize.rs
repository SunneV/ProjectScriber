//! BPE token counting via tiktoken-rs (audit feature 3).
//!
//! Only compiled when the `bpe` Cargo feature is enabled. When absent, the
//! module is empty and `has_bpe_tokenizer()` returns false at runtime, so the
//! Python side gracefully falls back to the calibrated estimator.

#[cfg(feature = "bpe")]
use pyo3::prelude::*;

/// Supported BPE encodings (mirrors the OpenAI model families).
#[cfg(feature = "bpe")]
fn build_encoding(name: &str) -> PyResult<tiktoken_rs::CoreBPE> {
    match name {
        "cl100k_base" => tiktoken_rs::cl100k_base()
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string())),
        "o200k_base" => tiktoken_rs::o200k_base()
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string())),
        other => Err(pyo3::exceptions::PyValueError::new_err(format!(
            "Unknown encoding '{other}'. Supported: cl100k_base, o200k_base"
        ))),
    }
}

/// Count tokens in `text` using the named BPE encoding (exact, audit feature 3).
#[cfg(feature = "bpe")]
#[pyfunction]
pub fn count_tokens_bpe(text: &str, encoding: &str) -> PyResult<usize> {
    let bpe = build_encoding(encoding)?;
    Ok(bpe.encode_with_special_tokens(text).len())
}
