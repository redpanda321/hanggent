// ========= Copyright 2025-2026 @ Hanggent.AI All Rights Reserved. =========
// Platform Service Interface Definitions
// Abstracts Electron IPC / Web HTTP for dual-mode support
// =========================================================================

/**
 * Backend service - manages communication with the Python backend
 */
export interface BackendService {
  /** Get the base URL for backend API requests */
  getBaseURL(): Promise<string>;
  /** Get the backend port number (Electron: dynamic, Web: from config) */
  getBackendPort(): Promise<number>;
  /** Restart the backend process */
  restartBackend(): Promise<{ success: boolean; error?: string }>;
  /** Check if backend is healthy */
  checkHealth(): Promise<boolean>;
}

/**
 * File service - file system operations
 */
export interface FileService {
  /** Open a file picker dialog (Electron: native dialog, Web: browser <input>) */
  selectFile(options?: FilePickerOptions): Promise<FilePickerResult | null>;
  /** Read a file and return its content */
  readFile(filePath: string): Promise<{ success: boolean; data?: any; error?: string }>;
  /** Read a file and return as data URL (for images, etc.) */
  readFileAsDataUrl(filePath: string): Promise<string | null>;
  /** Get list of files in a project folder */
  getFileList(email: string, taskId: string, projectId: string): Promise<any[]>;
  /** Reveal a file/folder in the system file manager */
  revealInFolder(filePath: string): Promise<void>;
  /** Delete a folder */
  deleteFolder(email: string): Promise<void>;
  /** Download a file (Electron: IPC, Web: browser download) */
  downloadFile(url: string): Promise<any>;
  /** Open a file with the given type (Electron: IPC, Web: fetch content) */
  openFile(type: string, path: string, isShowSourceCode?: boolean): Promise<any>;
  /** Get the project file list via IPC (Electron: local fs, Web: no-op/empty) */
  getProjectFileList(email: string, projectId: string): Promise<any[]>;
}

export interface FilePickerOptions {
  filters?: Array<{ name: string; extensions: string[] }>;
  properties?: string[];
  [key: string]: any;
}

export interface FilePickerResult {
  filePaths?: string[];
  canceled?: boolean;
  [key: string]: any;
}

/**
 * MCP (Model Context Protocol) service - manage MCP server configurations
 */
export interface McpService {
  /** List all installed MCP configurations */
  list(): Promise<Record<string, any>>;
  /** Install a new MCP server configuration */
  install(name: string, config: any): Promise<void>;
  /** Remove an MCP server configuration */
  remove(name: string): Promise<void>;
  /** Update an MCP server configuration */
  update(name: string, config: any): Promise<void>;
}

/**
 * Environment variable service - manage user env vars
 */
export interface EnvService {
  /** Write an environment variable for a user */
  write(email: string, kv: { key: string; value: string }): Promise<any>;
  /** Remove an environment variable for a user */
  remove(email: string, key: string): Promise<any>;
  /** Get the env file path for a user */
  getEnvPath(email: string): Promise<string>;
  /** Read a global environment variable */
  readGlobalEnv(key: string): Promise<any>;
}

/**
 * Window service - native window management (Electron-only, no-ops in web)
 */
export interface WindowService {
  /** Close the application window */
  closeWindow(isForceQuit?: boolean): void;
  /** Minimize the window */
  minimizeWindow(): void;
  /** Toggle maximize/restore */
  toggleMaximizeWindow(): void;
  /** Set window size */
  setSize(size: { width: number; height: number }): Promise<void>;
  /** Get the current OS platform */
  getPlatform(): string;
  /** Check if window is fullscreen */
  isFullScreen(): Promise<boolean>;
  /** Restart the entire app */
  restartApp(): Promise<void>;
}

/**
 * WebView service - embedded browser management
 */
export interface WebViewService {
  /** Create a webview with the given URL */
  createWebView(id: string, url: string): Promise<any>;
  /** Hide a specific webview */
  hideWebView(id: string): Promise<void>;
  /** Show a specific webview */
  showWebview(id: string): Promise<void>;
  /** Hide all webviews */
  hideAllWebview(): Promise<void>;
  /** Destroy a webview */
  destroy(webviewId: string): Promise<void>;
  /** Get currently active webview */
  getActiveWebview(): Promise<any>;
  /** Get webview show state */
  getShowWebview(): Promise<any>;
  /** Change webview size */
  changeViewSize(id: string, size: { width: number; height: number }): Promise<void>;
  /** Register callback for webview navigation changes */
  onWebviewNavigated(callback: (id: string, url: string) => void): (() => void) | undefined;
  /** Capture a webview screenshot */
  captureWebview(id: string): Promise<string>;
  /** Set webview container size/position */
  setSize(rect: { x: number; y: number; width: number; height: number }): Promise<void>;
}

/**
 * System service - misc system utilities
 */
export interface SystemService {
  /** Get system language */
  getSystemLanguage(): Promise<string>;
  /** Get browser debugging port */
  getBrowserPort(): Promise<number>;
  /** Get user home directory */
  getHomeDir(): Promise<string>;
  /** Execute a shell command */
  executeCommand(command: string, email: string): Promise<any>;
  /** Get project folder path */
  getProjectFolderPath(email: string, projectId: string): Promise<string>;
  /** Open folder in IDE */
  openInIDE(folderPath: string, ide: string): Promise<any>;
  /** Get email folder path */
  getEmailFolderPath(email: string): Promise<string>;
}

/**
 * Update service - app auto-update (Electron-only)
 */
export interface UpdateService {
  /** Check for available updates */
  checkUpdate(): Promise<void>;
  /** Start downloading the update */
  startDownload(): Promise<void>;
  /** Quit and install the update */
  quitAndInstall(): Promise<void>;
  /** Register update event listeners. Returns cleanup function. */
  onUpdateEvents(callbacks: UpdateEventCallbacks): () => void;
}

export interface UpdateEventCallbacks {
  onCanAvailable?: (info: any) => void;
  onError?: (error: any) => void;
  onDownloadProgress?: (progress: any) => void;
  onDownloaded?: (info: any) => void;
}

/**
 * Installation service - dependency installation (Electron-only)
 */
export interface InstallService {
  /** Check if tools are installed */
  checkToolInstalled(): Promise<{ success: boolean; isInstalled?: boolean; error?: any }>;
  /** Get installation status */
  getInstallationStatus(): Promise<{ success: boolean; isInstalling?: boolean }>;
  /** Check and install dependencies */
  checkAndInstallDepsOnUpdate(): Promise<{ success: boolean; error?: string }>;
  /** Register install event listeners. Returns cleanup function. */
  onInstallEvents(callbacks: InstallEventCallbacks): () => void;
}

export interface InstallEventCallbacks {
  onStart?: () => void;
  onLog?: (data: { type: string; data: string }) => void;
  onComplete?: (data: { success: boolean; code?: number; error?: string }) => void;
  onBackendReady?: (data: { success: boolean; port?: number; error?: string }) => void;
}

/**
 * Log service - app logging
 */
export interface LogService {
  /** Export logs to a file (Electron: save dialog, Web: download) */
  exportLog(): Promise<{ success: boolean; savedPath?: string; error?: string }>;
  /** Upload logs to server */
  uploadLog(email: string, taskId: string, baseUrl: string, token: string): Promise<void>;
  /** Get the log folder path for a user */
  getLogFolder(email: string): Promise<string>;
}

/**
 * IPC event service - raw event listener management
 */
export interface IpcEventService {
  /** Register an event listener */
  on(channel: string, listener: (...args: any[]) => void): void;
  /** Remove an event listener */
  off(channel: string, listener: (...args: any[]) => void): void;
  /** Remove all listeners for a channel */
  removeAllListeners(channel: string): void;
}

/**
 * The main platform service interface
 */
export interface PlatformService {
  readonly backend: BackendService;
  readonly file: FileService;
  readonly mcp: McpService;
  readonly env: EnvService;
  readonly window: WindowService;
  readonly webview: WebViewService;
  readonly system: SystemService;
  readonly update: UpdateService;
  readonly install: InstallService;
  readonly log: LogService;
  readonly ipc: IpcEventService;

  /** Whether this is running in Electron */
  readonly isElectron: boolean;
  /** Whether this is running in a web browser */
  readonly isWeb: boolean;
}
