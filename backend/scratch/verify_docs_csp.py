import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8001"
routes = [
    ("/", "GET"),
    ("/openapi.json", "GET"),
    ("/auth/login", "POST"),
    ("/auth/register", "POST"),
    ("/auth/me", "GET"),
    ("/agents", "GET"),
    ("/agent-actions", "GET"),
    ("/chat", "POST"),
    ("/query", "POST"),
    ("/connect", "POST"),
    ("/intelligence", "GET"),
    ("/analyst/ask", "POST"),
    ("/forecasting/candidates", "GET"),
    ("/anomaly/report", "GET")
]

print("Checking non-docs endpoints for strict CSP:")
all_strict = True
for path, method in routes:
    req = urllib.request.Request(f"{BASE}{path}", method=method, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req) as res:
            csp = res.headers.get("Content-Security-Policy")
    except urllib.error.HTTPError as e:
        csp = e.headers.get("Content-Security-Policy")
    except Exception as e:
        csp = str(e)
    
    is_strict = (csp == "default-src 'none'")
    if not is_strict:
        all_strict = False
    status = "[PASS]" if is_strict else "[FAIL]"
    print(f"  {status} {path} ({method}) -> {csp}")

print("\nAll non-docs endpoints strictly use default-src 'none':", all_strict)

print("\nChecking docs endpoints for scoped CSP:")
docs_routes = ["/docs", "/docs/", "/redoc", "/redoc/", "/docs/oauth2-redirect"]
for path in docs_routes:
    req = urllib.request.Request(f"{BASE}{path}", headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req) as res:
            csp = res.headers.get("Content-Security-Policy")
            has_cdn = "cdn.jsdelivr.net" in (csp or "")
            has_tiangolo = "fastapi.tiangolo.com" in (csp or "")
            status = "[PASS]" if (has_cdn and has_tiangolo) else "[FAIL]"
            print(f"  {status} {path} -> {csp}")
    except Exception as e:
        print(f"  [ERROR] {path} -> {e}")
