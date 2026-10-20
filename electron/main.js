const { app, BrowserWindow, ipcMain, shell, dialog, session } = require("electron");
const path = require("path");
const fs = require("fs");
const http = require("http");
const crypto = require("crypto");
const { spawn, execSync } = require("child_process");

// ── Application Identity & Per-Launch Secret ─────────────────────────────────
app.setAppUserModelId("com.bgai.platform");
app.commandLine.appendSwitch("allow-file-access-from-files");
const desktopSecret = crypto.randomBytes(32).toString("hex");

// ── Single Instance Protection ───────────────────────────────────────────────
const gotTheLock = app.requestSingleInstanceLock();
if (!gotTheLock) {
  app.quit();
  process.exit(0);
}

// Global Chrome User-Agent to prevent Google OAuth 403: disallowed_useragent
const CHROME_OAUTH_UA =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36";
app.userAgentFallback = CHROME_OAUTH_UA;

let mainWindow = null;
let splashWindow = null;
let backendProcess = null;
let backendPort = 8001;
let backendUrl = `http://127.0.0.1:${backendPort}`;
let frontendServer = null;
let frontendUrl = null;
let isQuitting = false;

// ── Directory Helpers ────────────────────────────────────────────────────────
function getAppDataDir() {
  const appData = process.env.APPDATA || path.join(require("os").homedir(), "AppData", "Roaming");
  const dir = path.join(appData, "BG_AI");
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
  return dir;
}

function logDesktopEvent(message) {
  try {
    const logDir = path.join(getAppDataDir(), "logs");
    if (!fs.existsSync(logDir)) fs.mkdirSync(logDir, { recursive: true });
    const logFile = path.join(logDir, "electron.log");
    const timestamp = new Date().toISOString();
    fs.appendFileSync(logFile, `[${timestamp}] ${message}\n`, "utf-8");
  } catch {
    // Ignore logging failures
  }
}

function getWindowStateFilePath() {
  return path.join(getAppDataDir(), "window-state.json");
}

function loadWindowState() {
  try {
    const data = fs.readFileSync(getWindowStateFilePath(), "utf-8");
    return JSON.parse(data);
  } catch {
    return { width: 1400, height: 900, isMaximized: false };
  }
}

function saveWindowState() {
  if (!mainWindow || mainWindow.isDestroyed()) return;
  try {
    const isMaximized = mainWindow.isMaximized();
    const bounds = mainWindow.getBounds();
    fs.writeFileSync(
      getWindowStateFilePath(),
      JSON.stringify({ ...bounds, isMaximized }),
      "utf-8"
    );
  } catch {
    // Ignore write errors during shutdown
  }
}

// ── Backend Process Management ───────────────────────────────────────────────
function getBackendExecutable() {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, "backend", "bgai_backend.exe");
  }
  // Development check: if compiled backend exists, use it; otherwise python script
  const devCompiled = path.join(__dirname, "..", "backend", "dist", "bgai_backend", "bgai_backend.exe");
  if (fs.existsSync(devCompiled)) {
    return devCompiled;
  }
  return "python";
}

function loadEnvFile(envPath) {
  if (!fs.existsSync(envPath)) return {};
  try {
    const content = fs.readFileSync(envPath, "utf-8");
    const parsed = {};
    for (const line of content.split("\n")) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith("#")) continue;
      const eqIdx = trimmed.indexOf("=");
      if (eqIdx !== -1) {
        const key = trimmed.slice(0, eqIdx).trim();
        const val = trimmed.slice(eqIdx + 1).trim();
        parsed[key] = val;
      }
    }
    return parsed;
  } catch {
    return {};
  }
}

function startBackend() {
  return new Promise((resolve, reject) => {
    const exe = getBackendExecutable();
    const dataDir = getAppDataDir();
    const args = [];

    // Seed and load .env configuration (GROQ_API_KEY, GROQ_MODEL, etc.)
    const appDataEnv = path.join(dataDir, ".env");
    const packagedEnv = path.join(process.resourcesPath || "", "backend", ".env");
    const devEnv = path.join(__dirname, "..", "backend", ".env");

    if (!fs.existsSync(appDataEnv)) {
      if (fs.existsSync(packagedEnv)) {
        try { fs.copyFileSync(packagedEnv, appDataEnv); } catch {}
      } else if (fs.existsSync(devEnv)) {
        try { fs.copyFileSync(devEnv, appDataEnv); } catch {}
      }
    }

    const envConfig = {
      ...loadEnvFile(devEnv),
      ...loadEnvFile(packagedEnv),
      ...loadEnvFile(appDataEnv),
    };

    let cmd = exe;
    if (exe === "python") {
      args.push(path.join(__dirname, "..", "backend", "desktop_server.py"));
    }

    // Pass configuration parameters
    args.push("--data-dir", dataDir);
    args.push("--parent-pid", process.pid.toString());
    args.push("--secret", desktopSecret);

    console.log(`[Electron] Starting backend: ${cmd} ${args.join(" ")}`);
    logDesktopEvent(`Starting backend process: ${cmd} (port search started)`);

    try {
      backendProcess = spawn(cmd, args, {
        cwd: app.isPackaged ? path.join(process.resourcesPath, "backend") : path.join(__dirname, "..", "backend"),
        env: {
          ...process.env,
          ...envConfig,
          BGAI_DESKTOP_MODE: "1",
          BGAI_DATA_DIR: dataDir,
          BGAI_DESKTOP_SECRET: desktopSecret,
        },
        stdio: ["ignore", "pipe", "pipe"],
      });
    } catch (err) {
      console.error("[Electron] Failed to spawn backend process:", err);
      logDesktopEvent(`Failed to spawn backend process: ${err.message}`);
      return reject(new Error(`Could not launch backend executable: ${err.message}`));
    }

    backendProcess.stdout.on("data", (data) => {
      const output = data.toString();
      console.log(`[Backend STDOUT] ${output.trim()}`);
      // Detect announced port from desktop_server.py
      const portMatch = output.match(/BGAI_PORT:(\d+)/);
      if (portMatch) {
        backendPort = parseInt(portMatch[1], 10);
        backendUrl = `http://127.0.0.1:${backendPort}`;
        console.log(`[Electron] Detected backend running on: ${backendUrl}`);
        logDesktopEvent(`Backend port announced: ${backendPort} (${backendUrl})`);
      }
    });

    backendProcess.stderr.on("data", (data) => {
      console.error(`[Backend STDERR] ${data.toString().trim()}`);
      logDesktopEvent(`[Backend STDERR] ${data.toString().trim()}`);
    });

    backendProcess.on("exit", (code, signal) => {
      console.log(`[Electron] Backend process exited with code ${code}, signal ${signal}`);
      logDesktopEvent(`Backend process exited with code ${code}, signal ${signal}`);
      backendProcess = null;
      if (!isQuitting && mainWindow && !mainWindow.isDestroyed()) {
        dialog.showErrorBox(
          "Backend Engine Stopped",
          "The BG AI backend process terminated unexpectedly. Please restart the application."
        );
      }
    });

    // Start polling health check
    pollHealthCheck(30, 400)
      .then(resolve)
      .catch(reject);
  });
}

function pollHealthCheck(maxRetries = 30, intervalMs = 400) {
  return new Promise((resolve, reject) => {
    let retries = 0;

    function check() {
      const req = http.get(`${backendUrl}/health`, { timeout: 1000 }, (res) => {
        if (res.statusCode === 200) {
          console.log(`[Electron] Backend health check PASSED on ${backendUrl}/health`);
          return resolve();
        }
        retry();
      });

      req.on("error", () => {
        retry();
      });

      req.on("timeout", () => {
        req.destroy();
        retry();
      });
    }

    function retry() {
      retries++;
      if (retries >= maxRetries) {
        return reject(
          new Error(
            `Backend failed to respond on ${backendUrl}/health within ${
              (maxRetries * intervalMs) / 1000
            } seconds.`
          )
        );
      }
      setTimeout(check, intervalMs);
    }

    check();
  });
}

function killBackend() {
  if (backendProcess && backendProcess.pid) {
    console.log(`[Electron] Killing backend process PID: ${backendProcess.pid}`);
    try {
      if (process.platform === "win32") {
        // Kill process tree on Windows
        execSync(`taskkill /F /T /PID ${backendProcess.pid}`, { stdio: "ignore" });
      } else {
        backendProcess.kill("SIGTERM");
      }
    } catch {
      // Process might already be dead
    }
    backendProcess = null;
  }
}

// ── Local Frontend Loopback Server (for Firebase Auth & Google OAuth) ────────
function startFrontendServer() {
  return new Promise((resolve) => {
    const distDir = path.join(__dirname, "..", "frontend", "dist");
    const distIndex = path.join(distDir, "index.html");
    if (!fs.existsSync(distIndex)) {
      console.log("[Electron] frontend/dist/index.html not found, skipping frontend server");
      return resolve(null);
    }

    const mimeTypes = {
      ".html": "text/html",
      ".js": "text/javascript",
      ".css": "text/css",
      ".json": "application/json",
      ".png": "image/png",
      ".jpg": "image/jpeg",
      ".jpeg": "image/jpeg",
      ".gif": "image/gif",
      ".svg": "image/svg+xml",
      ".ico": "image/x-icon",
      ".mp4": "video/mp4",
      ".webm": "video/webm",
      ".woff": "font/woff",
      ".woff2": "font/woff2",
      ".ttf": "font/ttf",
    };

    frontendServer = http.createServer((req, res) => {
      let reqPath = decodeURI(req.url.split("?")[0]);
      if (reqPath === "/" || !reqPath) reqPath = "/index.html";

      // 1. Resolve candidate paths for static files
      const candidates = [
        path.join(distDir, reqPath),
      ];
      if (app.isPackaged && process.resourcesPath) {
        candidates.push(
          path.join(process.resourcesPath, "app.asar.unpacked", "frontend", "dist", reqPath),
          path.join(process.resourcesPath, path.basename(reqPath)),
          path.join(process.resourcesPath, "backend", reqPath)
        );
      }
      candidates.push(
        path.join(__dirname, "..", "frontend", "public", reqPath),
        path.join(__dirname, "..", "frontend", "public", path.basename(reqPath))
      );

      let filePath = candidates.find((p) => {
        try {
          return fs.existsSync(p) && !fs.statSync(p).isDirectory();
        } catch {
          return false;
        }
      });

      // SPA fallback: any missing path serves index.html
      if (!filePath) {
        filePath = distIndex;
      }

      const ext = path.extname(filePath).toLowerCase();
      const contentType = mimeTypes[ext] || "application/octet-stream";

      let stat;
      try {
        stat = fs.statSync(filePath);
      } catch (err) {
        res.writeHead(500);
        res.end("Internal Server Error");
        return;
      }

      const fileSize = stat.size;
      const range = req.headers.range;

      // Handle HTTP Range requests for video/media streaming
      if (range) {
        const parts = range.replace(/bytes=/, "").split("-");
        const start = parseInt(parts[0], 10);
        const end = parts[1] ? parseInt(parts[1], 10) : fileSize - 1;

        if (isNaN(start) || start >= fileSize || end >= fileSize || start > end) {
          res.writeHead(416, {
            "Content-Range": `bytes */${fileSize}`,
            "Access-Control-Allow-Origin": "*",
          });
          return res.end();
        }

        const chunkSize = end - start + 1;
        const fileStream = fs.createReadStream(filePath, { start, end });
        res.writeHead(206, {
          "Content-Range": `bytes ${start}-${end}/${fileSize}`,
          "Accept-Ranges": "bytes",
          "Content-Length": chunkSize,
          "Content-Type": contentType,
          "Access-Control-Allow-Origin": "*",
        });
        fileStream.pipe(res);
      } else {
        res.writeHead(200, {
          "Content-Length": fileSize,
          "Content-Type": contentType,
          "Accept-Ranges": "bytes",
          "Access-Control-Allow-Origin": "*",
        });
        fs.createReadStream(filePath).pipe(res);
      }
    });

    frontendServer.listen(0, "127.0.0.1", () => {
      const port = frontendServer.address().port;
      frontendUrl = `http://localhost:${port}`;
      console.log(`[Electron] Local frontend server running on ${frontendUrl}`);
      logDesktopEvent(`Local frontend server running on ${frontendUrl}`);
      resolve(frontendUrl);
    });

    frontendServer.on("error", (err) => {
      console.error("[Electron] Frontend server error:", err);
      logDesktopEvent(`Frontend server error: ${err.message}`);
      resolve(null);
    });
  });
}

function stopFrontendServer() {
  if (frontendServer) {
    try {
      frontendServer.close();
    } catch {}
    frontendServer = null;
  }
}

// ── Window Creation ──────────────────────────────────────────────────────────
function createSplashWindow() {
  splashWindow = new BrowserWindow({
    width: 500,
    height: 380,
    frame: false,
    transparent: false,
    backgroundColor: "#0a0a0a",
    resizable: false,
    center: true,
    show: false,
    icon: path.join(__dirname, "..", "build", "icon.ico"),
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
    },
  });

  splashWindow.loadFile(path.join(__dirname, "splash.html"));
  splashWindow.once("ready-to-show", () => {
    splashWindow.show();
  });
}

function createMainWindow() {
  const state = loadWindowState();

  mainWindow = new BrowserWindow({
    width: state.width || 1400,
    height: state.height || 900,
    x: state.x,
    y: state.y,
    minWidth: 1024,
    minHeight: 700,
    backgroundColor: "#0a0a0a",
    show: false,
    autoHideMenuBar: true,
    title: "BG AI — AI Data Intelligence Platform",
    icon: path.join(__dirname, "..", "build", "icon.ico"),
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webSecurity: true,
      spellcheck: false,
    },
  });

  if (state.isMaximized) {
    mainWindow.maximize();
  }

  // Navigation and external link safety
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    // 1. Permit initial empty/about:blank popup initialization used by Firebase Auth SDK
    if (!url || url === "about:blank" || url === "about:blank#") {
      logDesktopEvent("[OAuth Popup] Allowing initial blank window for Firebase Auth");
      return {
        action: "allow",
        overrideBrowserWindowOptions: {
          width: 520,
          height: 680,
          autoHideMenuBar: true,
          title: "Sign in with Google — BG AI",
          modal: false,
          webPreferences: {
            nodeIntegration: false,
            contextIsolation: false, // Essential for cross-origin window.opener.postMessage authentication exchange
            sandbox: false,
          },
        },
      };
    }

    // 2. Permit Firebase and Google OAuth popup authentication windows
    const isAuthUrl =
      url.includes("firebaseapp.com") ||
      url.includes("accounts.google.com") ||
      url.includes("google.com/o/oauth2") ||
      url.includes("oauth2.googleapis.com") ||
      url.includes("apis.google.com") ||
      url.includes("gstatic.com");

    if (isAuthUrl) {
      logDesktopEvent(`Permitting Google / Firebase OAuth popup: ${url.split("?")[0]}`);
      return {
        action: "allow",
        overrideBrowserWindowOptions: {
          width: 520,
          height: 680,
          autoHideMenuBar: true,
          title: "Sign in with Google — BG AI",
          modal: false,
          webPreferences: {
            nodeIntegration: false,
            contextIsolation: false, // Essential for cross-origin window.opener.postMessage authentication exchange
            sandbox: false,
          },
        },
      };
    }

    if (url.startsWith("http:") || url.startsWith("https:") || url.startsWith("mailto:")) {
      shell.openExternal(url);
    }
    return { action: "deny" };
  });

  // Ensure child popup windows (e.g. Google Sign-In) use standard Chrome User-Agent and retain navigation
  mainWindow.webContents.on("did-create-window", (childWindow) => {
    childWindow.webContents.setUserAgent(CHROME_OAUTH_UA);

    // Keep all OAuth redirections inside the popup; only external non-auth links escape to system browser
    childWindow.webContents.on("will-navigate", (event, navUrl) => {
      const isAllowedNav =
        navUrl.includes("firebaseapp.com") ||
        navUrl.includes("accounts.google.com") ||
        navUrl.includes("google.com") ||
        navUrl.includes("googleapis.com") ||
        navUrl.includes("gstatic.com") ||
        navUrl.startsWith("http://localhost:") ||
        navUrl.startsWith("http://127.0.0.1:") ||
        navUrl.startsWith("about:");

      if (!isAllowedNav) {
        event.preventDefault();
        shell.openExternal(navUrl);
      }
    });

    childWindow.webContents.setWindowOpenHandler(({ url: childUrl }) => {
      if (childUrl.startsWith("http:") || childUrl.startsWith("https:")) {
        shell.openExternal(childUrl);
      }
      return { action: "deny" };
    });
  });

  // Capture diagnostic logs from renderer to desktop log
  mainWindow.webContents.on("console-message", (_, level, message) => {
    if (message.includes("[BG AI") || message.includes("Firebase") || message.includes("auth/") || level >= 2) {
      logDesktopEvent(`[Renderer Console] ${message}`);
    }
  });

  mainWindow.webContents.on("will-navigate", (event, url) => {
    // Only allow navigation to localhost or local files
    if (
      !url.startsWith("file://") &&
      !url.startsWith("http://localhost:") &&
      !url.startsWith("http://127.0.0.1:")
    ) {
      event.preventDefault();
      shell.openExternal(url);
    }
  });

  mainWindow.on("close", () => {
    saveWindowState();
  });

  mainWindow.once("ready-to-show", () => {
    if (splashWindow && !splashWindow.isDestroyed()) {
      splashWindow.close();
      splashWindow = null;
    }
    mainWindow.show();
  });

  // Load production bundle via local server or Vite dev server
  const distIndex = path.join(__dirname, "..", "frontend", "dist", "index.html");
  if (!app.isPackaged && process.env.VITE_DEV_SERVER_URL) {
    mainWindow.loadURL(process.env.VITE_DEV_SERVER_URL);
  } else if (frontendUrl) {
    mainWindow.loadURL(frontendUrl);
  } else if (fs.existsSync(distIndex)) {
    mainWindow.loadFile(distIndex);
  } else {
    mainWindow.loadURL(backendUrl);
  }
}

// ── IPC Handlers ─────────────────────────────────────────────────────────────
ipcMain.on("bgai:get-backend-url", (event) => {
  event.returnValue = backendUrl;
});

ipcMain.on("bgai:get-desktop-secret", (event) => {
  event.returnValue = desktopSecret;
});

ipcMain.handle("bgai:get-version", () => {
  return app.getVersion();
});

ipcMain.handle("bgai:open-external", async (_, url) => {
  await shell.openExternal(url);
});

ipcMain.handle("bgai:show-item-in-folder", async (_, filePath) => {
  shell.showItemInFolder(filePath);
});

ipcMain.handle("bgai:open-app-data", async () => {
  await shell.openPath(getAppDataDir());
});

// ── Native Google OAuth Loopback Flow (RFC 8252 with PKCE) ───────────────────
let activeOAuthServer = null;

ipcMain.handle("bgai:start-google-auth", async () => {
  if (activeOAuthServer) {
    try {
      activeOAuthServer.close();
    } catch {}
    activeOAuthServer = null;
  }

  // Load environment variables for Google Desktop Client ID from all configuration locations
  const dataDir = getAppDataDir();
  const appDataEnv = path.join(dataDir, ".env");
  const packagedEnv = path.join(process.resourcesPath || "", "backend", ".env");
  const devEnv = path.join(__dirname, "..", "backend", ".env");
  const rootEnv = path.join(__dirname, "..", ".env");
  const frontendEnv = path.join(__dirname, "..", "frontend", ".env");

  const envVars = {
    ...loadEnvFile(rootEnv),
    ...loadEnvFile(frontendEnv),
    ...loadEnvFile(devEnv),
    ...loadEnvFile(packagedEnv),
    ...loadEnvFile(appDataEnv),
    ...process.env,
  };

  const DEFAULT_GOOGLE_DESKTOP_CLIENT_ID =
    "1045610580763-dvtqgpm0dla9laa7r8q9m883qdr7itjd.apps.googleusercontent.com";

  const desktopClientId =
    envVars.GOOGLE_DESKTOP_CLIENT_ID ||
    process.env.GOOGLE_DESKTOP_CLIENT_ID ||
    DEFAULT_GOOGLE_DESKTOP_CLIENT_ID;

  const desktopClientSecret =
    envVars.GOOGLE_DESKTOP_CLIENT_SECRET ||
    process.env.GOOGLE_DESKTOP_CLIENT_SECRET ||
    "";

  if (!desktopClientId) {
    const errorMsg =
      "Google Sign-In on Desktop requires an OAuth Client ID of type 'Desktop app' (RFC 8252).\n" +
      "1. Open Google Cloud Console: https://console.cloud.google.com/apis/credentials?project=bg-platform-4b882\n" +
      "2. Click 'Create Credentials' > 'OAuth client ID'\n" +
      "3. Select Application type: 'Desktop app' (e.g. 'BG AI Desktop') and click Create\n" +
      "4. Add the generated Client ID to .env as: GOOGLE_DESKTOP_CLIENT_ID=<your-client-id>";
    logDesktopEvent(`[OAuth] Error: ${errorMsg}`);
    return {
      success: false,
      error: errorMsg,
    };
  }

  return new Promise((resolve) => {
    let finished = false;
    let timeoutTimer = null;

    const cleanupAndResolve = (result) => {
      if (finished) return;
      finished = true;
      if (timeoutTimer) clearTimeout(timeoutTimer);
      if (activeOAuthServer) {
        try {
          activeOAuthServer.close();
        } catch {}
        activeOAuthServer = null;
      }
      resolve(result);
    };

    const server = http.createServer();
    activeOAuthServer = server;

    // 2-minute safety timeout
    timeoutTimer = setTimeout(() => {
      cleanupAndResolve({
        success: false,
        error: "Google sign-in timed out or was cancelled by user.",
      });
    }, 120000);

    server.on("error", (err) => {
      logDesktopEvent(`[OAuth Loopback Server Error] ${err.message}`);
      cleanupAndResolve({
        success: false,
        error: `Could not start local authentication listener: ${err.message}`,
      });
    });

    server.listen(0, "127.0.0.1", async () => {
      const port = server.address().port;
      const callbackUrl = `http://127.0.0.1:${port}/callback`;

      // 1. Generate PKCE code verifier and code challenge (RFC 7636)
      const codeVerifier = crypto.randomBytes(32).toString("base64url");
      const codeChallenge = crypto
        .createHash("sha256")
        .update(codeVerifier)
        .digest("base64url");

      // 2. Generate cryptographically unpredictable state parameter (RFC 6749 Section 10.12)
      const oauthState = crypto.randomBytes(16).toString("hex");

      logDesktopEvent(`[OAuth] Started loopback listener on ${callbackUrl} (PKCE enabled)`);

      // 3. Construct Google OAuth 2.0 authorization URL for Desktop apps
      const authParams = new URLSearchParams({
        client_id: desktopClientId,
        redirect_uri: callbackUrl,
        response_type: "code",
        scope: "openid email profile",
        code_challenge: codeChallenge,
        code_challenge_method: "S256",
        state: oauthState,
        access_type: "offline",
        prompt: "select_account",
      });

      const authUri = `https://accounts.google.com/o/oauth2/v2/auth?${authParams.toString()}`;

      server.on("request", async (req, res) => {
        const reqUrl = new URL(req.url, `http://127.0.0.1:${port}`);

        if (req.method === "GET" && reqUrl.pathname === "/callback") {
          const code = reqUrl.searchParams.get("code");
          const state = reqUrl.searchParams.get("state");
          const error = reqUrl.searchParams.get("error");
          const errorDesc = reqUrl.searchParams.get("error_description");

          // Validate state parameter to mitigate CSRF attacks
          if (!state || state !== oauthState) {
            logDesktopEvent("[OAuth] State parameter mismatch or missing");
            res.writeHead(400, { "Content-Type": "text/html; charset=utf-8" });
            res.end(`<!DOCTYPE html><html><body style="background:#09090b;color:#ef4444;font-family:sans-serif;text-align:center;padding:50px;">
              <h2>Authentication Failed</h2><p>Security validation failed: invalid OAuth state. Please return to BG AI and try again.</p>
            </body></html>`);
            return cleanupAndResolve({
              success: false,
              error: "OAuth state validation failed (possible CSRF attempt).",
            });
          }

          if (error) {
            logDesktopEvent(`[OAuth] Google returned error: ${error} - ${errorDesc}`);
            res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
            res.end(`<!DOCTYPE html><html><body style="background:#09090b;color:#ef4444;font-family:sans-serif;text-align:center;padding:50px;">
              <h2>Sign-In Cancelled</h2><p>${errorDesc || error}</p><p>You can close this tab and return to BG AI.</p>
            </body></html>`);
            return cleanupAndResolve({
              success: false,
              error: errorDesc || error || "Google sign-in was cancelled.",
            });
          }

          if (!code) {
            logDesktopEvent("[OAuth] No authorization code received in callback");
            res.writeHead(400, { "Content-Type": "text/html; charset=utf-8" });
            res.end(`<!DOCTYPE html><html><body style="background:#09090b;color:#ef4444;font-family:sans-serif;text-align:center;padding:50px;">
              <h2>Missing Authorization Code</h2><p>Please return to BG AI and try again.</p>
            </body></html>`);
            return cleanupAndResolve({
              success: false,
              error: "No authorization code returned from Google.",
            });
          }

          // 4. Exchange authorization code + code_verifier for tokens with PKCE (RFC 7636)
          try {
            logDesktopEvent("[OAuth] Exchanging authorization code with Google token endpoint");

            const tokenRequestBody = {
              client_id: desktopClientId,
              code: code,
              code_verifier: codeVerifier,
              grant_type: "authorization_code",
              redirect_uri: callbackUrl,
            };

            if (desktopClientSecret) {
              tokenRequestBody.client_secret = desktopClientSecret;
            }

            const tokenRes = await fetch("https://oauth2.googleapis.com/token", {
              method: "POST",
              headers: { "Content-Type": "application/x-www-form-urlencoded" },
              body: new URLSearchParams(tokenRequestBody),
            });

            if (!tokenRes.ok) {
              const tokenErrText = await tokenRes.text();
              let parsedErr = {};
              try {
                parsedErr = JSON.parse(tokenErrText);
              } catch {}

              const sanitizedErrorCode = parsedErr.error || "token_exchange_error";
              const sanitizedErrorDesc = parsedErr.error_description || "Token exchange failed";

              // Log strictly safe diagnostic information per security guidelines
              logDesktopEvent(
                `[OAuth Token Exchange Diagnostic] HTTP ${tokenRes.status} | ` +
                `Error: ${sanitizedErrorCode} | ` +
                `Description: ${sanitizedErrorDesc} | ` +
                `PKCE verifier exists: ${Boolean(codeVerifier)} | ` +
                `Client ID matches request: ${Boolean(desktopClientId && desktopClientId === authParams.get("client_id"))} | ` +
                `Redirect URI matches request: ${Boolean(callbackUrl === authParams.get("redirect_uri"))}`
              );

              let userFacingMsg = `Authentication error: ${sanitizedErrorDesc}`;
              if (sanitizedErrorCode === "invalid_request" && sanitizedErrorDesc.includes("client_secret")) {
                userFacingMsg = "Google OAuth requires the Desktop Client Secret. Please set GOOGLE_DESKTOP_CLIENT_SECRET in .env.";
              } else if (sanitizedErrorCode === "invalid_grant") {
                userFacingMsg = "Authorization code expired or has already been used. Please try signing in again.";
              } else if (sanitizedErrorCode === "invalid_client") {
                userFacingMsg = "Invalid OAuth client configuration. Please verify your client ID and client secret in .env.";
              }

              res.writeHead(400, { "Content-Type": "text/html; charset=utf-8" });
              res.end(`<!DOCTYPE html><html><body style="background:#09090b;color:#ef4444;font-family:sans-serif;text-align:center;padding:50px;">
                <h2>Authentication Error</h2><p>${userFacingMsg}</p>
                <p style="color:#a1a1aa;font-size:13px;">Return to BG AI to try again.</p>
              </body></html>`);
              return cleanupAndResolve({
                success: false,
                error: userFacingMsg,
              });
            }

            const tokenData = await tokenRes.json();
            const idToken = tokenData.id_token;

            if (!idToken) {
              logDesktopEvent("[OAuth] No id_token returned from token endpoint");
              res.writeHead(400, { "Content-Type": "text/html; charset=utf-8" });
              res.end(`<!DOCTYPE html><html><body style="background:#09090b;color:#ef4444;font-family:sans-serif;text-align:center;padding:50px;">
                <h2>Authentication Error</h2><p>No ID token received from Google.</p>
              </body></html>`);
              return cleanupAndResolve({
                success: false,
                error: "Google did not provide an ID token.",
              });
            }

            // Decode unverified payload to extract display info for UX (backend cryptographically verifies token)
            let email = "";
            let displayName = "";
            let uid = "";
            try {
              const parts = idToken.split(".");
              if (parts.length >= 2) {
                const payload = JSON.parse(Buffer.from(parts[1], "base64").toString("utf-8"));
                email = payload.email || "";
                displayName = payload.name || (email ? email.split("@")[0] : "google_user");
                uid = payload.sub || "";
              }
            } catch {}

            // Send successful response to browser
            res.writeHead(200, {
              "Content-Type": "text/html; charset=utf-8",
              "Cache-Control": "no-store",
            });
            res.end(`<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>BG AI — Authentication Successful</title>
  <style>
    body { background: #09090b; color: #fff; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }
    .card { text-align: center; padding: 40px; border-radius: 16px; border: 1px solid rgba(255,255,255,0.1); background: #121215; max-width: 420px; width: 90%; box-shadow: 0 20px 40px rgba(0,0,0,0.5); }
    .icon { font-size: 40px; margin-bottom: 12px; color: #22c55e; }
    h2 { margin: 0 0 10px; font-size: 20px; font-weight: 700; color: #22c55e; }
    p { color: #a1a1aa; font-size: 14px; margin: 0 0 16px; }
    .btn { display: inline-block; background: #6366f1; color: #fff; padding: 10px 20px; border-radius: 8px; text-decoration: none; font-size: 14px; font-weight: 600; cursor: pointer; }
  </style>
</head>
<body>
  <div class="card">
    <div class="icon">✓</div>
    <h2>Sign-In Successful!</h2>
    <p>You have successfully authenticated with BG AI. You can safely close this browser window and return to the application.</p>
    <a class="btn" href="javascript:window.close()">Close Window</a>
  </div>
  <script>setTimeout(function(){ window.close(); }, 2000);</script>
</body>
</html>`);

            logDesktopEvent(`[OAuth] Successfully authenticated Google user via PKCE: ${email}`);
            cleanupAndResolve({
              success: true,
              idToken: idToken,
              email: email,
              username: displayName,
              uid: uid,
            });
          } catch (tokenErr) {
            logDesktopEvent(`[OAuth] Token exchange exception: ${tokenErr.message}`);
            cleanupAndResolve({
              success: false,
              error: `Token exchange error: ${tokenErr.message}`,
            });
          }
          return;
        }

        res.writeHead(404);
        res.end("Not Found");
      });

      logDesktopEvent("[OAuth] Opening default system browser for Google sign-in with PKCE");
      await shell.openExternal(authUri);
    });
  });
});

ipcMain.on("bgai:get-intro-video-path", (event) => {
  // If local frontend server is running, use HTTP URL to match window origin (avoiding file:// CORS restrictions)
  if (frontendUrl) {
    event.returnValue = `${frontendUrl}/bg-ai-intro.mp4`;
    return;
  }

  // 1. Packaged production: check app.asar.unpacked
  if (app.isPackaged) {
    const unpacked = path.join(
      process.resourcesPath,
      "app.asar.unpacked",
      "frontend",
      "dist",
      "bg-ai-intro.mp4"
    );
    if (fs.existsSync(unpacked)) {
      event.returnValue = `file:///${unpacked.replace(/\\/g, "/")}`;
      return;
    }
  }

  // 2. Extra resources or direct path
  if (process.resourcesPath) {
    const resPath = path.join(process.resourcesPath, "bg-ai-intro.mp4");
    if (fs.existsSync(resPath)) {
      event.returnValue = `file:///${resPath.replace(/\\/g, "/")}`;
      return;
    }
  }

  // 3. Development: check frontend/dist or frontend/public
  const devDist = path.join(__dirname, "..", "frontend", "dist", "bg-ai-intro.mp4");
  if (fs.existsSync(devDist)) {
    event.returnValue = `file:///${devDist.replace(/\\/g, "/")}`;
    return;
  }

  const devPublic = path.join(__dirname, "..", "frontend", "public", "bg-ai-intro.mp4");
  if (fs.existsSync(devPublic)) {
    event.returnValue = `file:///${devPublic.replace(/\\/g, "/")}`;
    return;
  }

  event.returnValue = "./bg-ai-intro.mp4";
});

// ── Application Lifecycle ────────────────────────────────────────────────────
app.on("second-instance", () => {
  if (mainWindow) {
    if (mainWindow.isMinimized()) mainWindow.restore();
    mainWindow.focus();
  }
});

app.whenReady().then(async () => {
  // 1. Set pure Google Chrome User-Agent so Google OAuth does not block with disallowed_useragent
  session.defaultSession.setUserAgent(CHROME_OAUTH_UA);

  // 2. Enforce Content-Security-Policy ONLY on local application pages (never onto external identity providers)
  session.defaultSession.webRequest.onHeadersReceived((details, callback) => {
    const isLocalApp =
      details.url.startsWith("http://localhost:") ||
      details.url.startsWith("http://127.0.0.1:") ||
      details.url.startsWith("file://");

    if (!isLocalApp) {
      return callback({ responseHeaders: details.responseHeaders });
    }

    callback({
      responseHeaders: {
        ...details.responseHeaders,
        "Content-Security-Policy": [
          "default-src 'self' 'unsafe-inline' 'unsafe-eval' data: blob: " +
          "http://127.0.0.1:* http://localhost:* " +
          "https://*.googleapis.com " +
          "https://*.firebaseio.com " +
          "https://*.firebaseapp.com " +
          "https://accounts.google.com " +
          "https://apis.google.com " +
          "https://thebg.co.in " +
          "https://thebg.con.in " +
          "https://fonts.googleapis.com " +
          "https://fonts.gstatic.com " +
          "https://cdn.jsdelivr.net; " +
          "connect-src 'self' data: blob: " +
          "http://127.0.0.1:* http://localhost:* " +
          "https://*.googleapis.com " +
          "https://*.firebaseio.com " +
          "https://*.firebaseapp.com " +
          "https://identitytoolkit.googleapis.com " +
          "https://securetoken.googleapis.com " +
          "https://thebg.co.in " +
          "https://thebg.con.in; " +
          "frame-src 'self' https://*.firebaseapp.com https://accounts.google.com; " +
          "img-src 'self' data: blob: https://*.googleusercontent.com https://*.gstatic.com https://*.googleapis.com; " +
          "media-src 'self' data: blob: file:;"
        ]
      }
    });
  });

  createSplashWindow();

  try {
    await startBackend();
    await startFrontendServer();
    createMainWindow();
  } catch (err) {
    console.error("[Electron] Backend startup failed:", err);
    if (splashWindow && !splashWindow.isDestroyed()) {
      splashWindow.webContents.executeJavaScript(`
        showError("Backend Startup Failed: ${err.message.replace(/"/g, '\\"')}");
      `);
    } else {
      dialog.showErrorBox("Startup Error", `Failed to initialize BG AI Backend:\n\n${err.message}`);
    }
  }

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createMainWindow();
    }
  });
});

app.on("before-quit", () => {
  isQuitting = true;
  saveWindowState();
  killBackend();
  stopFrontendServer();
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

