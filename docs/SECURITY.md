# Security Architecture, Threat Model & Compliance (`STRIDE` / `OWASP API`)

## 1. Authentication & Cryptographic Verification

### Telegram WebApp `initData` HMAC-SHA256 Validation
All Telegram Mini App (TMA) API requests are authenticated in [`app/api/auth.py`](../app/api/auth.py) via constant-time HMAC-SHA256 signature verification:
1. The raw `initData` query string is parsed and sorted alphabetically by key (excluding `hash`).
2. A secret key is derived via `HMAC-SHA256(key=b"WebAppData", msg=BOT_TOKEN)`.
3. The payload signature is verified using `hmac.compare_digest` to prevent timing side-channel attacks.
4. **Replay & Clock-Skew Protection**:
   - Signatures older than `INIT_DATA_MAX_AGE_SECONDS` (`43200s` default, configurable per call) are rejected.
   - Future-dated timestamps (`auth_date - now > 60s`) are rejected to prevent clock-skew injection.
5. **Development Bypass Isolation**:
   - `dev_auth_bypass` is strictly gated behind `APP_ENV == "local_dev" and DEV_AUTH_BYPASS == True` and is unreachable in `production` or `staging`.

---

## 2. Multi-Tenant Authorization & BOLA/IDOR Prevention (`OWASP API1:2023`)

Every multi-tenant administrative and analytics endpoint enforces explicit tenant-scoped access control:
- **Administrative Mutation Guard (`check_admin_rights`)**: Verifies that the authenticated `user_id` is an active `ChatAdmin` for the target `chat_id` (or a system superadmin) before permitting any roster, billing, disciplinary, or tenant policy mutation.
- **Tenant Membership Guard (`verify_tenant_membership`)**: Prevents cross-tenant Broken Object Level Authorization (BOLA / IDOR) by verifying that the caller holds a valid `ChatAdmin`, `PlayerProfile`, or historical `Signup` relationship with `chat_id`, raising `HTTP 403 Forbidden` otherwise.

---

## 3. Immutable Administrative Audit Ledger (`AuditLog`)

All sensitive administrative mutations stage an immutable [`AuditLog`](../app/db/models.py) record within the same database transaction via [`record_audit_log`](../app/core/services/audit.py):

| Audited Action Code | Triggering Endpoint | Recorded Metadata (`payload`) |
| :--- | :--- | :--- |
| `TENANT_SETTINGS_UPDATE` | `PATCH /api/dashboard/groups/{chat_id}/settings` | Updated policy, billing mode, currency, sport preset, and defaults |
| `DISCIPLINARY_CARD_ISSUED` | `POST /api/dashboard/groups/{chat_id}/players/{uid}/card` | `card_type` (`YELLOW` / `RED`), `weeks`, `reason` |
| `BILLING_PAYMENT_TOGGLED` | `POST /api/dashboard/signups/{signup_id}/toggle_pay` | `is_paid` boolean state and target `user_id` |

---

## 4. Infrastructure & Container Hardening

- **Non-Root Execution**: Kubernetes pods in [`deploy/k8s/deployment.yaml`](../deploy/k8s/deployment.yaml) run with `runAsNonRoot: true`, `runAsUser: 10001`, `readOnlyRootFilesystem: true`, `allowPrivilegeEscalation: false`, and `capabilities.drop: ["ALL"]`.
- **Zero-Trust Network Segmentation**: [`deploy/k8s/networkpolicy.yaml`](../deploy/k8s/networkpolicy.yaml) restricts ingress to port `8000` from the ingress controller and limits egress strictly to internal PostgreSQL (`5432`), Redis (`6379`), DNS (`53`), and public HTTPS (`443`) while blocking RFC 1918 lateral movement.
- **OPSEC & Secret Hygiene**: Zero credentials, tokens, private IP addresses, or personal identifiers are stored in version-controlled files; all secrets are injected via environment variables or Kubernetes `Secret` manifests.
