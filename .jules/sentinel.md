## 2026-06-01 - Prevent Timing Attacks in HMAC Verification
**Vulnerability:** String comparison (`!=`) was used to verify HMAC signatures instead of constant-time comparison.
**Learning:** Using standard string comparison operators on cryptographic hashes allows attackers to deduce the expected hash byte-by-byte via timing attacks, bypassing signature verification.
**Prevention:** Always use `hmac.compare_digest` (or equivalent constant-time comparison functions) when comparing security-sensitive hashes or tokens.
