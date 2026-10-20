const { contextBridge, ipcRenderer } = require("electron");

/**
 * Validated desktop bridge exposed to the renderer under window.electronAPI.
 * Enforces strict context isolation and prevents arbitrary Node access.
 */
contextBridge.exposeInMainWorld("electronAPI", {
  /**
   * Returns the dynamic backend URL (e.g. http://127.0.0.1:8001)
   */
  getBackendUrl: () => ipcRenderer.sendSync("bgai:get-backend-url"),

  /**
   * Returns per-launch authentication secret for local loopback verification.
   */
  getDesktopSecret: () => ipcRenderer.sendSync("bgai:get-desktop-secret"),

  /**
   * Returns true to indicate the app is running in desktop Electron mode.
   */
  isDesktop: () => true,

  /**
   * Returns the resolved desktop path for the BG AI intro video.
   */
  getIntroVideoPath: () => ipcRenderer.sendSync("bgai:get-intro-video-path"),

  /**
   * Retrieves desktop app version information.
   */
  getAppVersion: () => ipcRenderer.invoke("bgai:get-version"),

  /**
   * Safely opens external URLs in the user's default OS browser.
   */
  openExternal: (url) => {
    if (typeof url === "string" && (url.startsWith("http://") || url.startsWith("https://") || url.startsWith("mailto:"))) {
      ipcRenderer.invoke("bgai:open-external", url);
    }
  },

  /**
   * Shows a file in Windows File Explorer.
   */
  showItemInFolder: (filePath) => {
    if (typeof filePath === "string") {
      ipcRenderer.invoke("bgai:show-item-in-folder", filePath);
    }
  },

  /**
   * Starts native Google OAuth via external system browser with loopback redirect.
   */
  startGoogleAuth: () => ipcRenderer.invoke("bgai:start-google-auth"),

  /**
   * Opens the local AppData folder containing logs and databases.
   */
  openAppDataFolder: () => {
    ipcRenderer.invoke("bgai:open-app-data");
  },
});

