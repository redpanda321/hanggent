// ========= Copyright 2025-2026 @ Hanggent.AI All Rights Reserved. =========
// Electron Platform Service Implementation
// Wraps existing window.ipcRenderer / window.electronAPI calls
// =========================================================================

import type {
  BackendService,
  EnvService,
  FileService,
  FilePickerOptions,
  FilePickerResult,
  InstallEventCallbacks,
  InstallService,
  IpcEventService,
  LogService,
  McpService,
  PlatformService,
  SystemService,
  UpdateEventCallbacks,
  UpdateService,
  WebViewService,
  WindowService,
} from './types';

// --------------- Backend ---------------
class ElectronBackendService implements BackendService {
  private _baseUrl = '';

  async getBaseURL(): Promise<string> {
    if (this._baseUrl) return this._baseUrl;
    const port = await window.ipcRenderer.invoke('get-backend-port');
    this._baseUrl = `http://localhost:${port}`;
    return this._baseUrl;
  }

  async getBackendPort(): Promise<number> {
    return window.electronAPI.getBackendPort();
  }

  async restartBackend(): Promise<{ success: boolean; error?: string }> {
    return window.electronAPI.restartBackend();
  }

  async checkHealth(): Promise<boolean> {
    try {
      const port = await this.getBackendPort();
      const res = await fetch(`http://localhost:${port}/health`, {
        signal: AbortSignal.timeout(1000),
      }).catch(() => null);
      return !!res?.ok;
    } catch {
      return false;
    }
  }
}

// --------------- File ---------------
class ElectronFileService implements FileService {
  async selectFile(options?: FilePickerOptions): Promise<FilePickerResult | null> {
    return window.electronAPI.selectFile(options);
  }

  async readFile(filePath: string): Promise<{ success: boolean; data?: any; error?: string }> {
    return window.ipcRenderer.invoke('read-file', filePath);
  }

  async readFileAsDataUrl(filePath: string): Promise<string | null> {
    return window.electronAPI.readFileAsDataUrl(filePath);
  }

  async getFileList(email: string, taskId: string, projectId: string): Promise<any[]> {
    return window.ipcRenderer.invoke('get-file-list', email, taskId, projectId);
  }

  async revealInFolder(filePath: string): Promise<void> {
    await window.ipcRenderer.invoke('reveal-in-folder', filePath);
  }

  async deleteFolder(email: string): Promise<void> {
    await window.electronAPI.deleteFolder(email);
  }

  async downloadFile(url: string): Promise<any> {
    return window.ipcRenderer.invoke('download-file', url);
  }

  async openFile(type: string, path: string, isShowSourceCode?: boolean): Promise<any> {
    return window.ipcRenderer.invoke('open-file', type, path, isShowSourceCode);
  }

  async getProjectFileList(email: string, projectId: string): Promise<any[]> {
    return window.ipcRenderer.invoke('get-project-file-list', email, projectId);
  }
}

// --------------- MCP ---------------
class ElectronMcpService implements McpService {
  async list(): Promise<Record<string, any>> {
    return window.ipcRenderer.invoke('mcp-list');
  }

  async install(name: string, config: any): Promise<void> {
    await window.ipcRenderer.invoke('mcp-install', name, config);
  }

  async remove(name: string): Promise<void> {
    await window.ipcRenderer.invoke('mcp-remove', name);
  }

  async update(name: string, config: any): Promise<void> {
    await window.ipcRenderer.invoke('mcp-update', name, config);
  }
}

// --------------- Env ---------------
class ElectronEnvService implements EnvService {
  async write(email: string, kv: { key: string; value: string }): Promise<any> {
    return window.electronAPI.envWrite(email, kv);
  }

  async remove(email: string, key: string): Promise<any> {
    return window.electronAPI.envRemove(email, key);
  }

  async getEnvPath(email: string): Promise<string> {
    return window.ipcRenderer.invoke('get-env-path', email);
  }

  async readGlobalEnv(key: string): Promise<any> {
    return window.electronAPI.readGlobalEnv(key);
  }
}

// --------------- Window ---------------
class ElectronWindowService implements WindowService {
  closeWindow(isForceQuit?: boolean): void {
    window.electronAPI.closeWindow(isForceQuit);
  }

  minimizeWindow(): void {
    window.electronAPI.minimizeWindow();
  }

  toggleMaximizeWindow(): void {
    window.electronAPI.toggleMaximizeWindow();
  }

  async setSize(size: { width: number; height: number }): Promise<void> {
    await window.electronAPI.setSize(size);
  }

  getPlatform(): string {
    return window.electronAPI?.getPlatform?.() || 'web';
  }

  async isFullScreen(): Promise<boolean> {
    return window.electronAPI.isFullScreen();
  }

  async restartApp(): Promise<void> {
    await window.electronAPI.restartApp();
  }
}

// --------------- WebView ---------------
class ElectronWebViewService implements WebViewService {
  async createWebView(id: string, url: string): Promise<any> {
    return window.electronAPI.createWebView(id, url);
  }

  async hideWebView(id: string): Promise<void> {
    await window.electronAPI.hideWebView(id);
  }

  async showWebview(id: string): Promise<void> {
    await window.electronAPI.showWebview(id);
  }

  async hideAllWebview(): Promise<void> {
    await window.electronAPI.hideAllWebview();
  }

  async destroy(webviewId: string): Promise<void> {
    await window.electronAPI.webviewDestroy(webviewId);
  }

  async getActiveWebview(): Promise<any> {
    return window.electronAPI.getActiveWebview();
  }

  async getShowWebview(): Promise<any> {
    return window.electronAPI.getShowWebview();
  }

  async changeViewSize(id: string, size: { width: number; height: number }): Promise<void> {
    await window.electronAPI.changeViewSize(id, size);
  }

  onWebviewNavigated(callback: (id: string, url: string) => void): (() => void) | undefined {
    return window.electronAPI.onWebviewNavigated(callback);
  }

  async captureWebview(id: string): Promise<string> {
    return window.ipcRenderer.invoke('capture-webview', id);
  }

  async setSize(rect: { x: number; y: number; width: number; height: number }): Promise<void> {
    await window.electronAPI.setSize(rect);
  }
}

// --------------- System ---------------
class ElectronSystemService implements SystemService {
  async getSystemLanguage(): Promise<string> {
    return window.ipcRenderer.invoke('get-system-language');
  }

  async getBrowserPort(): Promise<number> {
    return window.ipcRenderer.invoke('get-browser-port');
  }

  async getHomeDir(): Promise<string> {
    return window.electronAPI.getHomeDir();
  }

  async executeCommand(command: string, email: string): Promise<any> {
    return window.electronAPI.executeCommand(command, email);
  }

  async getProjectFolderPath(email: string, projectId: string): Promise<string> {
    return window.electronAPI.getProjectFolderPath(email, projectId);
  }

  async openInIDE(folderPath: string, ide: string): Promise<any> {
    return window.electronAPI.openInIDE(folderPath, ide);
  }

  async getEmailFolderPath(email: string): Promise<string> {
    return window.electronAPI.getEmailFolderPath(email);
  }
}

// --------------- Update ---------------
class ElectronUpdateService implements UpdateService {
  async checkUpdate(): Promise<void> {
    await window.ipcRenderer.invoke('check-update');
  }

  async startDownload(): Promise<void> {
    await window.ipcRenderer.invoke('start-download');
  }

  async quitAndInstall(): Promise<void> {
    await window.ipcRenderer.invoke('quit-and-install');
  }

  onUpdateEvents(callbacks: UpdateEventCallbacks): () => void {
    const { onCanAvailable, onError, onDownloadProgress, onDownloaded } = callbacks;

    if (onCanAvailable) window.ipcRenderer?.on('update-can-available', onCanAvailable);
    if (onError) window.ipcRenderer?.on('update-error', onError);
    if (onDownloadProgress) window.ipcRenderer?.on('download-progress', onDownloadProgress);
    if (onDownloaded) window.ipcRenderer?.on('update-downloaded', onDownloaded);

    return () => {
      if (onCanAvailable) window.ipcRenderer?.off('update-can-available', onCanAvailable);
      if (onError) window.ipcRenderer?.off('update-error', onError);
      if (onDownloadProgress) window.ipcRenderer?.off('download-progress', onDownloadProgress);
      if (onDownloaded) window.ipcRenderer?.off('update-downloaded', onDownloaded);
    };
  }
}

// --------------- Install ---------------
class ElectronInstallService implements InstallService {
  async checkToolInstalled(): Promise<{ success: boolean; isInstalled?: boolean; error?: any }> {
    return window.ipcRenderer.invoke('check-tool-installed');
  }

  async getInstallationStatus(): Promise<{ success: boolean; isInstalling?: boolean }> {
    return window.electronAPI.getInstallationStatus();
  }

  async checkAndInstallDepsOnUpdate(): Promise<{ success: boolean; error?: string }> {
    return window.electronAPI.checkAndInstallDepsOnUpdate();
  }

  onInstallEvents(callbacks: InstallEventCallbacks): () => void {
    const { onStart, onLog, onComplete, onBackendReady } = callbacks;

    if (onStart) window.electronAPI.onInstallDependenciesStart(onStart);
    if (onLog) window.electronAPI.onInstallDependenciesLog(onLog);
    if (onComplete) window.electronAPI.onInstallDependenciesComplete(onComplete);
    if (onBackendReady) window.electronAPI.onBackendReady(onBackendReady);

    return () => {
      window.electronAPI.removeAllListeners('install-dependencies-start');
      window.electronAPI.removeAllListeners('install-dependencies-log');
      window.electronAPI.removeAllListeners('install-dependencies-complete');
      window.electronAPI.removeAllListeners('backend-ready');
    };
  }
}

// --------------- Log ---------------
class ElectronLogService implements LogService {
  async exportLog(): Promise<{ success: boolean; savedPath?: string; error?: string }> {
    return window.electronAPI.exportLog();
  }

  async uploadLog(email: string, taskId: string, baseUrl: string, token: string): Promise<void> {
    await window.electronAPI.uploadLog(email, taskId, baseUrl, token);
  }

  async getLogFolder(email: string): Promise<string> {
    return window.ipcRenderer.invoke('get-log-folder', email);
  }
}

// --------------- IPC Events ---------------
class ElectronIpcEventService implements IpcEventService {
  on(channel: string, listener: (...args: any[]) => void): void {
    window.ipcRenderer?.on(channel, listener);
  }

  off(channel: string, listener: (...args: any[]) => void): void {
    window.ipcRenderer?.off(channel, listener);
  }

  removeAllListeners(channel: string): void {
    window.ipcRenderer?.removeAllListeners(channel);
  }
}

// --------------- Main Service ---------------
export class ElectronPlatformService implements PlatformService {
  readonly backend = new ElectronBackendService();
  readonly file = new ElectronFileService();
  readonly mcp = new ElectronMcpService();
  readonly env = new ElectronEnvService();
  readonly window = new ElectronWindowService();
  readonly webview = new ElectronWebViewService();
  readonly system = new ElectronSystemService();
  readonly update = new ElectronUpdateService();
  readonly install = new ElectronInstallService();
  readonly log = new ElectronLogService();
  readonly ipc = new ElectronIpcEventService();

  readonly isElectron = true;
  readonly isWeb = false;
}
