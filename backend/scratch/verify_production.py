"""
backend/scratch/verify_production.py
Empirical Verification of Production Deployment Environment:
- Backend: https://bg-chatbox.onrender.com
- Frontend: https://thebg.co.in
"""
import time
import requests
import json

BACKEND_URL = "https://bg-chatbox.onrender.com"
FRONTEND_URL = "https://thebg.co.in"

report_data = {}

def measure(fn, *args, **kwargs):
    t0 = time.time()
    res = fn(*args, **kwargs)
    dt = time.time() - t0
    return res, dt

print("=" * 60)
print("BG AI — PHASE 7.1 PRODUCTION VERIFICATION")
print(f"Backend:  {BACKEND_URL}")
print(f"Frontend: {FRONTEND_URL}")
print("=" * 60)

# ── 1. Backend Health & Connectivity ──────────────────────────────────────────
print("\n[1] Backend Reachability & HTTPS")
try:
    r_root, lat_root = measure(requests.get, f"{BACKEND_URL}/", timeout=20)
    print(f"  Status: {r_root.status_code}")
    print(f"  Latency: {lat_root:.2f}s")
    print(f"  HTTPS: {r_root.url.startswith('https://')}")
    print(f"  Response: {r_root.text}")
    report_data["backend_reachable"] = (r_root.status_code == 200)
    report_data["backend_latency"] = f"{lat_root:.2f}s"
except Exception as e:
    print(f"  FAIL: {e}")
    report_data["backend_reachable"] = False

# ── 2. Deployed Endpoints Analysis ────────────────────────────────────────────
print("\n[2] Deployed API Schema Inspection")
try:
    r_openapi = requests.get(f"{BACKEND_URL}/openapi.json", timeout=15)
    if r_openapi.status_code == 200:
        schema = r_openapi.json()
        deployed_paths = list(schema.get("paths", {}).keys())
        print(f"  Total deployed routes: {len(deployed_paths)}")
        print(f"  Has /auth/register: {'/auth/register' in deployed_paths}")
        print(f"  Has /auth/login: {'/auth/login' in deployed_paths}")
        print(f"  Has /agents: {'/agents' in deployed_paths}")
        print(f"  Has /agent-actions: {'/agent-actions' in deployed_paths}")
        report_data["deployed_routes_count"] = len(deployed_paths)
        report_data["has_phase7_endpoints"] = ('/auth/login' in deployed_paths)
        report_data["has_phase5_endpoints"] = ('/agents' in deployed_paths)
    else:
        print(f"  OpenAPI returned {r_openapi.status_code}")
        report_data["has_phase7_endpoints"] = False
except Exception as e:
    print(f"  FAIL: {e}")
    report_data["has_phase7_endpoints"] = False

# ── 3. Production Authentication Endpoints ────────────────────────────────────
print("\n[3] Production Authentication Endpoints")
try:
    r_reg = requests.post(f"{BACKEND_URL}/auth/register", json={"username": "probe_user", "password": "probe_password_123"}, timeout=10)
    print(f"  POST /auth/register -> HTTP {r_reg.status_code}")
    r_login = requests.post(f"{BACKEND_URL}/auth/login", json={"username": "probe_user", "password": "probe_password_123"}, timeout=10)
    print(f"  POST /auth/login -> HTTP {r_login.status_code}")
    r_me = requests.get(f"{BACKEND_URL}/auth/me", headers={"Authorization": "Bearer fake_token"}, timeout=10)
    print(f"  GET /auth/me -> HTTP {r_me.status_code}")
    report_data["prod_auth_status"] = "NOT_DEPLOYED" if r_reg.status_code == 404 else "ACTIVE"
except Exception as e:
    print(f"  Auth check error: {e}")
    report_data["prod_auth_status"] = "ERROR"

# ── 4. CORS Policy on Production ──────────────────────────────────────────────
print("\n[4] Production CORS Inspection")
try:
    r_cors_allowed = requests.options(
        f"{BACKEND_URL}/chat",
        headers={
            "Origin": "https://thebg.co.in",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Authorization,Content-Type"
        },
        timeout=10
    )
    origin_header_allowed = r_cors_allowed.headers.get("access-control-allow-origin")
    cred_header_allowed = r_cors_allowed.headers.get("access-control-allow-credentials")
    print(f"  Origin 'https://thebg.co.in':")
    print(f"    Status: {r_cors_allowed.status_code}")
    print(f"    Allow-Origin: {origin_header_allowed}")
    print(f"    Allow-Credentials: {cred_header_allowed}")

    r_cors_unauth = requests.options(
        f"{BACKEND_URL}/chat",
        headers={
            "Origin": "https://malicious-attacker.com",
            "Access-Control-Request-Method": "POST",
        },
        timeout=10
    )
    origin_header_unauth = r_cors_unauth.headers.get("access-control-allow-origin")
    print(f"  Origin 'https://malicious-attacker.com':")
    print(f"    Status: {r_cors_unauth.status_code}")
    print(f"    Allow-Origin: {origin_header_unauth}")
    
    report_data["cors_wildcard_present"] = (origin_header_unauth == "https://malicious-attacker.com" or origin_header_unauth == "*")
except Exception as e:
    print(f"  CORS check error: {e}")

# ── 5. Security Headers on Production ─────────────────────────────────────────
print("\n[5] Production Security Headers")
try:
    r_hdr = requests.get(f"{BACKEND_URL}/", timeout=10)
    headers_to_check = [
        "X-Content-Type-Options",
        "Referrer-Policy",
        "X-Frame-Options",
        "Content-Security-Policy",
        "Strict-Transport-Security"
    ]
    hdr_results = {}
    for h in headers_to_check:
        val = r_hdr.headers.get(h)
        print(f"  {h}: {val}")
        hdr_results[h] = val
    report_data["production_security_headers"] = hdr_results
except Exception as e:
    print(f"  Header check error: {e}")

# ── 6. Error Handling & Secret Leakage on Production ──────────────────────────
print("\n[6] Production Error Handling & Information Leakage")
try:
    # Trigger 404
    r_404 = requests.get(f"{BACKEND_URL}/nonexistent_endpoint_xyz", timeout=10)
    print(f"  404 body: {r_404.text}")
    
    # Trigger 422 validation error
    r_422 = requests.post(f"{BACKEND_URL}/connect", json={"db_type": "invalid_type"}, timeout=10)
    print(f"  422 / Bad input body: {r_422.text}")
    
    # Check for secret leakage
    has_secret_leak = any(
        kw in r_404.text.lower() or kw in r_422.text.lower()
        for kw in ["password", "secret_key", "traceback", "env", "token"]
    )
    print(f"  Any secret leakage in responses: {has_secret_leak}")
    report_data["secret_leakage_detected"] = has_secret_leak
except Exception as e:
    print(f"  Error test exception: {e}")

# ── 7. Frontend Deployment Inspection ─────────────────────────────────────────
print("\n[7] Frontend Deployment Inspection (https://thebg.co.in)")
try:
    r_fe = requests.get(FRONTEND_URL, timeout=10)
    print(f"  Status: {r_fe.status_code}")
    print(f"  Last-Modified header: {r_fe.headers.get('last-modified')}")
    print(f"  Server: {r_fe.headers.get('server')}")
    print(f"  Cloudflare cache status: {r_fe.headers.get('cf-cache-status')}")
    report_data["frontend_status"] = r_fe.status_code
    report_data["frontend_last_modified"] = r_fe.headers.get('last-modified')
except Exception as e:
    print(f"  Frontend check error: {e}")

# ── 8. Timing Measurements ────────────────────────────────────────────────────
print("\n[8] Latency Measurements")
latencies = {}
for endpoint, method in [("/", "GET"), ("/database-type", "GET"), ("/suggestions", "GET")]:
    try:
        if method == "GET":
            _, dt = measure(requests.get, f"{BACKEND_URL}{endpoint}", timeout=10)
        latencies[endpoint] = f"{dt*1000:.0f}ms"
        print(f"  {method} {endpoint}: {latencies[endpoint]}")
    except Exception as e:
        latencies[endpoint] = "TIMEOUT/ERROR"
        print(f"  {method} {endpoint}: ERROR ({e})")
report_data["latencies"] = latencies

print("\n" + "=" * 60)
print("PROBE RESULTS SUMMARY:")
print(json.dumps(report_data, indent=2))
print("=" * 60)
