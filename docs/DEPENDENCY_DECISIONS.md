# Jarvis — Dependency Decisions & Audit

## 1. Runtime Dependencies

| Package | Version Pin | License | Maintenance / Health | Primary Purpose | Lock-in / Replacement Strategy |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `fastapi` | `^0.115.0` | MIT | Very active, widely adopted | HTTP/WebSocket API server, dependency injection | Minimal; routes easily map to Starlette or standard ASGI |
| `uvicorn` | `^0.32.0` | BSD-3 | Standard ASGI server | High-performance async server runner | Can be swapped for Hypercorn or Granian |
| `pydantic` | `^2.9.0` | MIT | Core standard in Python 3 AI | Typed schemas, request/response validation, tool schemas | Standard Pydantic v2; core standard |
| `pydantic-settings` | `^2.5.0` | MIT | Official Pydantic package | Environment variable and `.env` parsing | Simple fallback to Python `os.environ` or yaml config |
| `httpx` | `^0.27.0` | BSD-3 | Active, standard async HTTP | LLM provider communication, outbound web requests | Drop-in swappable with `aiohttp` |
| `cryptography` | `^43.0.0` | Apache-2.0 / BSD | Industry standard PyCA | AES-256-GCM authenticated encryption for sync & secrets | Standard OpenSSL wrapper |
| `websockets` | `^13.0` | BSD-3 | Active, mature | Fast bidirectional streaming communication | Swappable with FastAPI built-in websocket handler |

---

## 2. Test & Development Dependencies

| Package | Version Pin | License | Maintenance / Health | Primary Purpose |
| :--- | :--- | :--- | :--- | :--- |
| `pytest` | `^8.3.0` | MIT | Premier test framework | Unit, integration, security test execution |
| `pytest-asyncio` | `^0.24.0` | Apache-2.0 | Standard pytest async plugin | Seamless execution of `async def test_*` suites |
| `pytest-cov` | `^5.0.0` | MIT | Active | Code coverage auditing and regression reporting |

---

## 3. Dependency Policy & Boundaries

1. **Strict Version Bounds**: Core packages are pinned with semantic bounds in `pyproject.toml` to prevent supply chain breakage.
2. **Local Installation Only**: All dependencies are strictly installed in `.venv` within the workspace root `/Users/snehashissarkar/Snehashis/Repos/JARVIS`. No system-wide or user-wide installations.
3. **No Paid Dependencies**: Zero commercial SDKs or libraries requiring active billing are included.
4. **Mockability**: Every dependency interacting with the network or OS processes implements a mock interface for automated CI/offline test suites.
