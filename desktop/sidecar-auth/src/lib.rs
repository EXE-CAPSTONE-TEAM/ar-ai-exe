//! Trust boundary between the KusStudio desktop shell and its local backend sidecar.
//!
//! KusShoes spec §F / ADR-007: the shell always spawns its own sidecar, gives it a fresh
//! per-launch secret, and only trusts a process that proves it holds that secret by answering
//! `GET /handshake?nonce=…` with `HMAC-SHA256(secret, nonce)`. Nothing here depends on Tauri, so
//! the logic is unit-tested on hosts that cannot build the webview (see `.spec/verification.md`).

use hmac::{Hmac, Mac};
use sha2::Sha256;

type HmacSha256 = Hmac<Sha256>;

/// provenance: 256-bit secret (KusShoes spec §Parameter & Data Provenance, "Claim / sidecar tokens").
pub const TOKEN_BYTES: usize = 32;
/// provenance: same entropy as the token; the sidecar accepts 32–128 hex chars (16–64 bytes).
pub const NONCE_BYTES: usize = 32;

/// Lowercase hex of `bytes` random bytes from the OS CSPRNG.
pub fn random_hex(bytes: usize) -> Result<String, getrandom::Error> {
    let mut buffer = vec![0u8; bytes];
    getrandom::getrandom(&mut buffer)?;
    Ok(hex::encode(buffer))
}

pub fn new_launch_token() -> Result<String, getrandom::Error> {
    random_hex(TOKEN_BYTES)
}

pub fn new_nonce() -> Result<String, getrandom::Error> {
    random_hex(NONCE_BYTES)
}

/// `HMAC-SHA256(key = token, message = nonce)` as lowercase hex — what an honest sidecar returns.
pub fn proof(token: &str, nonce: &str) -> String {
    let mut mac = HmacSha256::new_from_slice(token.as_bytes()).expect("HMAC accepts any key length");
    mac.update(nonce.as_bytes());
    hex::encode(mac.finalize().into_bytes())
}

/// Constant-time check of a sidecar's handshake answer.
pub fn verify_proof(token: &str, nonce: &str, candidate_hex: &str) -> bool {
    let Ok(candidate) = hex::decode(candidate_hex.trim()) else {
        return false;
    };
    let mut mac = HmacSha256::new_from_slice(token.as_bytes()).expect("HMAC accepts any key length");
    mac.update(nonce.as_bytes());
    mac.verify_slice(&candidate).is_ok()
}

/// Whether an already-running backend may serve this launch.
///
/// Only a process this shell spawned *and* that proves the current launch token qualifies; a
/// listener that merely answers `/health` (for example one squatting the old default port 8000)
/// is never adopted.
pub fn may_reuse_sidecar(spawned_by_this_launch: bool, proof_verified: bool) -> bool {
    spawned_by_this_launch && proof_verified
}

/// Extract `proof` from a raw HTTP/1.1 response (the shell speaks HTTP over a bare TcpStream).
pub fn parse_handshake_response(raw: &str) -> Option<String> {
    let (head, body) = raw.split_once("\r\n\r\n")?;
    let status_ok = head.lines().next().is_some_and(|line| line.split_whitespace().nth(1) == Some("200"));
    if !status_ok {
        return None;
    }
    let value: serde_json::Value = serde_json::from_str(body.trim()).ok()?;
    value.get("proof")?.as_str().map(str::to_owned)
}

/// Turn a comma-separated list of storage origins into the JSON list the sidecar's
/// `WORKER_ALLOWED_STORAGE_ORIGINS` setting expects. Only bare `https://host[:port]` origins pass.
pub fn storage_origins_env(csv: &str) -> Result<String, String> {
    let mut origins = Vec::new();
    for raw in csv.split(',').map(str::trim).filter(|item| !item.is_empty()) {
        let rest = raw
            .strip_prefix("https://")
            .ok_or_else(|| format!("storage origin must use https: {raw}"))?;
        let valid = !rest.is_empty()
            && !rest.contains(['/', '?', '#', '@', ' ', '\\'])
            && rest.chars().all(|c| c.is_ascii_alphanumeric() || matches!(c, '.' | '-' | ':'));
        if !valid {
            return Err(format!("storage origin must be a bare origin: {raw}"));
        }
        origins.push(serde_json::Value::String(raw.to_ascii_lowercase()));
    }
    if origins.is_empty() {
        return Err("no storage origin configured".to_string());
    }
    Ok(serde_json::Value::Array(origins).to_string())
}

#[cfg(test)]
mod tests {
    use super::*;

    const TOKEN: &str = "0f0e0d0c0b0a09080706050403020100ffeeddccbbaa99887766554433221100";
    const NONCE: &str = "00112233445566778899aabbccddeeff00112233445566778899aabbccddeeff";

    #[test]
    fn generated_secrets_have_the_documented_entropy_and_differ() {
        let first = new_launch_token().unwrap();
        let second = new_launch_token().unwrap();
        assert_eq!(first.len(), TOKEN_BYTES * 2);
        assert_eq!(new_nonce().unwrap().len(), NONCE_BYTES * 2);
        assert_ne!(first, second);
        assert!(first.chars().all(|c| c.is_ascii_hexdigit()));
    }

    #[test]
    fn proof_matches_rfc4231_hmac_sha256() {
        // RFC 4231 test case 2: key "Jefe", data "what do ya want for nothing?".
        assert_eq!(
            proof("Jefe", "what do ya want for nothing?"),
            "5bdcc146bf60754e6a042426089575c75a003f089d2739839dec58b964ec3843"
        );
    }

    #[test]
    fn verify_accepts_only_the_proof_for_this_token_and_nonce() {
        let good = proof(TOKEN, NONCE);
        assert!(verify_proof(TOKEN, NONCE, &good));
        assert!(verify_proof(TOKEN, NONCE, &format!(" {good}\n")));
        assert!(!verify_proof("another-token", NONCE, &good));
        assert!(!verify_proof(TOKEN, &NONCE.replace('0', "1"), &good));
        assert!(!verify_proof(TOKEN, NONCE, &good[..good.len() - 2]));
        assert!(!verify_proof(TOKEN, NONCE, "not-hex"));
        assert!(!verify_proof(TOKEN, NONCE, ""));
    }

    #[test]
    fn a_health_responder_that_was_not_spawned_here_is_never_adopted() {
        assert!(!may_reuse_sidecar(false, true));
        assert!(!may_reuse_sidecar(false, false));
        assert!(!may_reuse_sidecar(true, false));
        assert!(may_reuse_sidecar(true, true));
    }

    #[test]
    fn handshake_response_parsing() {
        let ok = "HTTP/1.1 200 OK\r\ncontent-type: application/json\r\n\r\n{\"proof\":\"abc123\"}";
        assert_eq!(parse_handshake_response(ok).as_deref(), Some("abc123"));
        let denied = "HTTP/1.1 503 Service Unavailable\r\n\r\n{\"proof\":\"abc123\"}";
        assert_eq!(parse_handshake_response(denied), None);
        assert_eq!(parse_handshake_response("HTTP/1.1 200 OK\r\n\r\n{\"status\":\"ok\"}"), None);
        assert_eq!(parse_handshake_response("garbage"), None);
    }

    #[test]
    fn storage_origins_render_as_a_json_list_of_https_origins() {
        assert_eq!(
            storage_origins_env(" https://Acct.r2.cloudflarestorage.com , https://cdn.example:8443 ").unwrap(),
            r#"["https://acct.r2.cloudflarestorage.com","https://cdn.example:8443"]"#
        );
        for bad in [
            "",
            "http://acct.r2.cloudflarestorage.com",
            "https://acct.r2.cloudflarestorage.com/kusshoes",
            "https://user@acct.r2.cloudflarestorage.com",
            "https://acct.r2.cloudflarestorage.com?x=1",
        ] {
            assert!(storage_origins_env(bad).is_err(), "{bad} should be rejected");
        }
    }
}
