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

let mainWindow = null;
let splashWindow = null;
let backendProcess = null;
let backendPort = 8001;
let backendUrl = `http://127.0.0.1:${backendPort}`;
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

function startBackend() {
  return new Promise((resolve, reject) => {
    const exe = getBackendExecutable();
    const dataDir = getAppDataDir();
    const args = [];

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
    // Permit Firebase and Google OAuth popup authentication windows
    if (
      url.includes("firebaseapp.com") ||
      url.includes("accounts.google.com") ||
      url.includes("google.com/o/oauth2")
    ) {
      return {
        action: "allow",
        overrideBrowserWindowOptions: {
          width: 520,
          height: 680,
          autoHideMenuBar: true,
          title: "Sign in with Google — BG AI",
          parent: mainWindow,
          modal: true,
          webPreferences: {
            nodeIntegration: false,
            contextIsolation: true,
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

  // Load production bundle or Vite dev server
  const distIndex = path.join(__dirname, "..", "frontend", "dist", "index.html");
  if (!app.isPackaged && process.env.VITE_DEV_SERVER_URL) {
    mainWindow.loadURL(process.env.VITE_DEV_SERVER_URL);
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

ipcMain.on("bgai:get-intro-video-path", (event) => {
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
  // 1. Strip 'Electron/...' from User-Agent so Google OAuth does not block with disallowed_useragent
  const defaultUA = session.defaultSession.getUserAgent();
  const cleanUA = defaultUA.replace(/Electron\/[0-9\.]+\s?/, "");
  session.defaultSession.setUserAgent(cleanUA);

  // 2. Enforce Content-Security-Policy permitting local backend, Firebase Auth, Google OAuth, fonts, and media
  session.defaultSession.webRequest.onHeadersReceived((details, callback) => {
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
          "https://fonts.googleapis.com " +
          "https://fonts.gstatic.com " +
          "https://cdn.jsdelivr.net; " +
          "media-src 'self' data: blob: file:;"
        ]
      }
    });
  });

  createSplashWindow();

  try {
    await startBackend();
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
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

