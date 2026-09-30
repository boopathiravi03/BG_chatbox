"""
backend/scratch/poll_deployment.py
Polls Render and Cloudflare deployments until Phase 7 endpoints appear.
"""
import time
import requests

BACKEND_URL = "https://bg-chatbox.onrender.com"
FRONTEND_URL = "https://thebg.co.in"

print("Waiting for Render and Cloudflare deployment...")
print(f"Target backend: {BACKEND_URL}")
print(f"Target frontend: {FRONTEND_URL}")

start_time = time.time()
max_wait = 360  # wait up to 6 minutes

backend_updated = False
frontend_updated = False

for attempt in range(1, 25):
    elapsed = time.time() - start_time
    print(f"\n--- Check {attempt} (Elapsed: {elapsed:.0f}s) ---")
    
    # 1. Check Backend
    try:
        r = requests.get(f"{BACKEND_URL}/", timeout=10)
        text = r.text
        print(f"Backend root status: {r.status_code}, body: {text}")
        if "BG AI Backend v7" in text or "v7" in text:
            print(">>> BACKEND DEPLOYMENT DETECTED (Phase 7 banner present)!")
            backend_updated = True
        else:
            # Also check if /auth/register exists (not 404)
            r_auth = requests.post(f"{BACKEND_URL}/auth/register", json={}, timeout=10)
            if r_auth.status_code in [400, 422]:
                print(">>> BACKEND DEPLOYMENT DETECTED (/auth/register returned validation error, not 404)!")
                backend_updated = True
            else:
                print(f"Backend still on old code (/auth/register returned {r_auth.status_code})")
    except Exception as e:
        print(f"Backend check exception: {e}")
        
    # 2. Check Frontend
    try:
        r_fe = requests.get(FRONTEND_URL, timeout=10)
        lm = r_fe.headers.get("last-modified")
        print(f"Frontend status: {r_fe.status_code}, Last-Modified: {lm}")
    except Exception as e:
        print(f"Frontend check exception: {e}")
        
    if backend_updated:
        print("\nBackend deployment is live!")
        break
        
    time.sleep(15)

if not backend_updated:
    print("\nDeployment is still building or taking longer than expected.")
