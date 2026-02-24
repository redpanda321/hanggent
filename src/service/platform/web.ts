// ========= Copyright 2025-2026 @ Hanggent.AI All Rights Reserved. =========
// Web Platform Service Implementation
// Provides web-compatible alternatives for Electron IPC calls.
// In web mode, the backend and server are pre-deployed (via Docker/k8s),
// so installation, auto-update, and native window APIs are no-ops.
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
class WebBackendService implements BackendService {
  /**
   * In web mode, the backend is accessed through Vite dev proxy or nginx reverse proxy.
   * The proxy is configured in vite.config.web.ts:
   *   /api/backend/* -> backend:5001
   *   /api/*         -> server:3001
   */
  async getBaseURL(): Promise<string> {
    // In web mode, use the proxy path so requests go through Vite/nginx
    return '/api/backend';
  }

  async getBackendPort(): Promise<number> {
    // In web mode, backend port is abstracted away behind the proxy
    return 5001;
  }

  async restartBackend(): Promise<{ success: boolean; error?: string }> {
    // Web mode: backend lifecycle is managed by Docker/k8s, not the frontend
    console.warn('[WebPlatform] restartBackend is not available in web mode');
    return { success: false, error: 'Not available in web mode' };
  }

  async checkHealth(): Promise<boolean> {
    try {
      const res = await fetch('/api/backend/health', {
        signal: AbortSignal.timeout(2000),
      }).catch(() => null);
      return !!res?.ok;
    } catch {
      return false;
    }
  }
}

// --------------- File ---------------
class WebFileService implements FileService {
  async selectFile(_options?: FilePickerOptions): Promise<FilePickerResult | null> {
    // Use browser's native file picker via an invisible <input>
    return new Promise((resolve) => {
      const input = document.createElement('input');
      input.type = 'file';
      input.multiple = true;

      // Map Electron-style filter extensions to accept attribute
      if (_options?.filters?.length) {
        const exts = _options.filters
          .flatMap((f) => f.extensions)
          .map((ext) => `.${ext}`)
          .join(',');
        if (exts) input.accept = exts;
      }

      input.onchange = () => {
        if (input.files && input.files.length > 0) {
          // Return File objects directly; consumers should check for this
          resolve({
            canceled: false,
            files: Array.from(input.files),
          } as any);
        } else {
          resolve({ canceled: true });
        }
      };

      // Handle cancel (user closes the picker without selecting)
      input.oncancel = () => resolve({ canceled: true });

      input.click();
    });
  }

  async readFile(filePath: string): Promise<{ success: boolean; data?: any; error?: string }> {
    // In web mode, try to fetch from backend file serving endpoint
    try {
      const res = await fetch(`/api/backend/files/read?path=${encodeURIComponent(filePath)}`);
      if (res.ok) {
        const data = await res.text();
        return { success: true, data };
      }
      return { success: false, error: `HTTP ${res.status}` };
    } catch (error) {
      return { success: false, error: String(error) };
    }
  }

  async readFileAsDataUrl(filePath: string): Promise<string | null> {
    try {
      const res = await fetch(`/api/backend/files/read?path=${encodeURIComponent(filePath)}`);
      if (!res.ok) return null;
      const blob = await res.blob();
      return new Promise((resolve) => {
        const reader = new FileReader();
        reader.onloadend = () => resolve(reader.result as string);
        reader.readAsDataURL(blob);
      });
    } catch {
      return null;
    }
  }

  async getFileList(email: string, taskId: string, projectId: string): Promise<any[]> {
    // In web mode, files are managed server-side; return empty list
    // The backend handles file persistence
    try {
      const res = await fetch(
        `/api/backend/files/list?email=${encodeURIComponent(email)}&task_id=${encodeURIComponent(taskId)}&project_id=${encodeURIComponent(projectId)}`
      );
      if (res.ok) return await res.json();
    } catch {
      // ignore
    }
    return [];
  }

  async revealInFolder(_filePath: string): Promise<void> {
    // Not available in web mode - no-op
    console.info('[WebPlatform] revealInFolder is not available in web mode');
  }

  async deleteFolder(_email: string): Promise<void> {
    console.warn('[WebPlatform] deleteFolder is not available in web mode');
  }

  async downloadFile(url: string): Promise<any> {
    // In web mode, trigger a browser download
    const a = document.createElement('a');
    a.href = url;
    a.download = '';
    a.click();
    return { success: true };
  }

  async openFile(type: string, path: string, _isShowSourceCode?: boolean): Promise<any> {
    try {
      const res = await fetch(
        `/api/backend/files/open?type=${encodeURIComponent(type)}&path=${encodeURIComponent(path)}`
      );
      if (res.ok) return await res.text();
    } catch {
      // ignore
    }
    return null;
  }

  async getProjectFileList(_email: string, _projectId: string): Promise<any[]> {
    // In web mode, project files are fetched via the server API, not local IPC
    return [];
  }
}

// --------------- MCP ---------------
class WebMcpService implements McpService {
  async list(): Promise<Record<string, any>> {
    // In web mode, MCP configs are managed server-side
    try {
      const res = await fetch('/api/mcp/list');
      if (res.ok) return await res.json();
    } catch {
      // ignore
    }
    return {};
  }

  async install(name: string, config: any): Promise<void> {
    await fetch('/api/mcp/install', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, config }),
    });
  }

  async remove(name: string): Promise<void> {
    await fetch('/api/mcp/remove', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    });
  }

  async update(name: string, config: any): Promise<void> {
    await fetch('/api/mcp/update', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, config }),
    });
  }
}

// --------------- Env ---------------
class WebEnvService implements EnvService {
  async write(email: string, kv: { key: string; value: string }): Promise<any> {
    try {
      const res = await fetch('/api/env/write', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, ...kv }),
      });
      if (res.ok) return await res.json();
    } catch {
      // ignore
    }
    return { success: false };
  }

  async remove(email: string, key: string): Promise<any> {
    try {
      const res = await fetch('/api/env/remove', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, key }),
      });
      if (res.ok) return await res.json();
    } catch {
      // ignore
    }
    return { success: false };
  }

  async getEnvPath(_email: string): Promise<string> {
    // Not meaningful in web mode since env is managed server-side
    return '';
  }

  async readGlobalEnv(_key: string): Promise<any> {
    // Not available in web mode
    return null;
  }
}

// --------------- Window ---------------
class WebWindowService implements WindowService {
  closeWindow(_isForceQuit?: boolean): void {
    // In web mode, closing the window = closing the browser tab (no-op, user controls this)
  }

  minimizeWindow(): void {
    // No-op in web mode
  }

  toggleMaximizeWindow(): void {
    // No-op in web mode
  }

  async setSize(_size: { width: number; height: number }): Promise<void> {
    // No-op in web mode
  }

  getPlatform(): string {
    return 'web';
  }

  async isFullScreen(): Promise<boolean> {
    return !!document.fullscreenElement;
  }

  async restartApp(): Promise<void> {
    // In web mode, "restart" = refresh the page
    window.location.reload();
  }
}

// --------------- WebView ---------------
class WebWebViewService implements WebViewService {
  async createWebView(_id: string, url: string): Promise<any> {
    // In web mode, open in a new tab
    globalThis.open(url, '_blank');
    return { id: _id };
  }

  async hideWebView(_id: string): Promise<void> {
    // No-op in web mode
  }

  async showWebview(_id: string): Promise<void> {
    // No-op in web mode
  }

  async hideAllWebview(): Promise<void> {
    // No-op in web mode
  }

  async destroy(_webviewId: string): Promise<void> {
    // No-op in web mode
  }

  async getActiveWebview(): Promise<any> {
    return null;
  }

  async getShowWebview(): Promise<any> {
    return null;
  }

  async changeViewSize(_id: string, _size: { width: number; height: number }): Promise<void> {
    // No-op in web mode
  }

  onWebviewNavigated(_callback: (id: string, url: string) => void): (() => void) | undefined {
    // No webview navigation events in web mode
    return undefined;
  }

  async captureWebview(_id: string): Promise<string> {
    // No webview capture in web mode
    return '';
  }

  async setSize(_rect: { x: number; y: number; width: number; height: number }): Promise<void> {
    // No-op in web mode
  }
}

// --------------- System ---------------
class WebSystemService implements SystemService {
  async getSystemLanguage(): Promise<string> {
    // Use browser's language
    return navigator.language || 'en';
  }

  async getBrowserPort(): Promise<number> {
    // In web mode, browser port is managed by the deployment
    // Return a default; the backend knows its own browser port
    return 9222;
  }

  async getHomeDir(): Promise<string> {
    return '';
  }

  async executeCommand(_command: string, _email: string): Promise<any> {
    console.warn('[WebPlatform] executeCommand is not available in web mode');
    return { success: false, error: 'Not available in web mode' };
  }

  async getProjectFolderPath(_email: string, _projectId: string): Promise<string> {
    return '';
  }

  async openInIDE(_folderPath: string, _ide: string): Promise<any> {
    console.warn('[WebPlatform] openInIDE is not available in web mode');
    return { success: false, error: 'Not available in web mode' };
  }

  async getEmailFolderPath(_email: string): Promise<string> {
    return '';
  }
}

// --------------- Update ---------------
class WebUpdateService implements UpdateService {
  async checkUpdate(): Promise<void> {
    // Auto-update not applicable in web mode (deployed via Docker/k8s)
  }

  async startDownload(): Promise<void> {
    // No-op
  }

  async quitAndInstall(): Promise<void> {
    // No-op
  }

  onUpdateEvents(_callbacks: UpdateEventCallbacks): () => void {
    // No update events in web mode
    return () => {};
  }
}

// --------------- Install ---------------
class WebInstallService implements InstallService {
  /**
   * In web mode, the backend is pre-deployed — no local installation needed.
   * Return as if everything is already installed and ready.
   */
  async checkToolInstalled(): Promise<{ success: boolean; isInstalled?: boolean }> {
    return { success: true, isInstalled: true };
  }

  async getInstallationStatus(): Promise<{ success: boolean; isInstalling?: boolean }> {
    return { success: true, isInstalling: false };
  }

  async checkAndInstallDepsOnUpdate(): Promise<{ success: boolean }> {
    return { success: true };
  }

  onInstallEvents(_callbacks: InstallEventCallbacks): () => void {
    // No install events in web mode
    return () => {};
  }
}

// --------------- Log ---------------
class WebLogService implements LogService {
  async exportLog(): Promise<{ success: boolean; savedPath?: string; error?: string }> {
    console.info('[WebPlatform] exportLog: downloading from server');
    try {
      const res = await fetch('/api/logs/export');
      if (res.ok) {
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `hanggent-logs-${Date.now()}.zip`;
        a.click();
        URL.revokeObjectURL(url);
        return { success: true, savedPath: a.download };
      }
      if (res.status === 401) {
        return { success: false, error: 'Please sign in to export logs' };
      }
      return { success: false, error: `Server returned ${res.status}` };
    } catch (e) {
      console.error('[WebPlatform] exportLog failed:', e);
      return { success: false, error: 'Failed to connect to server' };
    }
  }

  async uploadLog(email: string, taskId: string, baseUrl: string, token: string): Promise<void> {
    // In web mode, upload via HTTP
    try {
      await fetch(`${baseUrl}/api/logs/upload`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ email, taskId }),
      });
    } catch (error) {
      console.error('[WebPlatform] uploadLog failed:', error);
    }
  }

  async getLogFolder(_email: string): Promise<string> {
    // Not meaningful in web mode
    return '';
  }
}

// --------------- IPC Events ---------------
class WebIpcEventService implements IpcEventService {
  // In web mode, there are no IPC events — all methods are no-ops
  on(_channel: string, _listener: (...args: any[]) => void): void {
    // no-op
  }

  off(_channel: string, _listener: (...args: any[]) => void): void {
    // no-op
  }

  removeAllListeners(_channel: string): void {
    // no-op
  }
}

// --------------- Main Service ---------------
export class WebPlatformService implements PlatformService {
  readonly backend = new WebBackendService();
  readonly file = new WebFileService();
  readonly mcp = new WebMcpService();
  readonly env = new WebEnvService();
  readonly window = new WebWindowService();
  readonly webview = new WebWebViewService();
  readonly system = new WebSystemService();
  readonly update = new WebUpdateService();
  readonly install = new WebInstallService();
  readonly log = new WebLogService();
  readonly ipc = new WebIpcEventService();

  readonly isElectron = false;
  readonly isWeb = true;
}
