/**
 * ServiceManager - Orchestrates external service lifecycle
 * 
 * Manages OpenCode and OpenClaw services with:
 * - Auto-start on app ready
 * - Health monitoring
 * - Log routing to renderer
 * - Graceful shutdown
 * - Degraded mode support
 */

import { BrowserWindow, ipcMain, app } from 'electron';
import log from 'electron-log';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { ServicesConfig, ServiceState, ServiceName, LogEntry } from './types';
import { OpenCodeService } from './OpenCodeService';
import { OpenClawService } from './OpenClawService';
import { LogRouter } from './LogRouter';

// Default config path
const CONFIG_PATH = path.join(__dirname, '../../../config/services.json');

export class ServiceManager {
  private config: ServicesConfig;
  private openCode: OpenCodeService | null = null;
  private openClaw: OpenClawService | null = null;
  private logRouter: LogRouter;
  private mainWindow: BrowserWindow | null = null;
  private isInitialized = false;

  constructor() {
    this.config = this.loadConfig();
    this.logRouter = new LogRouter(this.config.logging);
  }

  /**
   * Load configuration from file with env var overrides
   */
  private loadConfig(): ServicesConfig {
    let config: ServicesConfig;
    
    try {
      // Try to load from config file
      if (fs.existsSync(CONFIG_PATH)) {
        const raw = fs.readFileSync(CONFIG_PATH, 'utf-8');
        config = JSON.parse(raw);
        log.info('[ServiceManager] Loaded config from', CONFIG_PATH);
      } else {
        // Use defaults if config file doesn't exist
        config = this.getDefaultConfig();
        log.info('[ServiceManager] Using default config');
      }
    } catch (error) {
      log.error('[ServiceManager] Error loading config:', error);
      config = this.getDefaultConfig();
    }

    // Apply environment variable overrides
    if (process.env.OPENCODE_PORT) {
      config.opencode.port = parseInt(process.env.OPENCODE_PORT, 10);
    }
    if (process.env.OPENCODE_URL) {
      config.opencode.url = process.env.OPENCODE_URL;
    }
    if (process.env.OPENCLAW_PORT) {
      config.openclaw.port = parseInt(process.env.OPENCLAW_PORT, 10);
    }
    if (process.env.OPENCLAW_URL) {
      config.openclaw.url = process.env.OPENCLAW_URL;
    }
    if (process.env.HANGGENT_LOG_DIR) {
      config.logging.logDir = process.env.HANGGENT_LOG_DIR;
    }

    // Disable services if env vars say so
    if (process.env.OPENCODE_ENABLED === 'false') {
      config.opencode.enabled = false;
    }
    if (process.env.OPENCLAW_ENABLED === 'false') {
      config.openclaw.enabled = false;
    }

    return config;
  }

  /**
   * Get default configuration
   */
  private getDefaultConfig(): ServicesConfig {
    return {
      opencode: {
        enabled: true,
        port: 4096,
        url: 'http://localhost:4096',
        healthEndpoint: '/health',
        startupTimeoutMs: 15000,
        restartOnCrash: true,
        maxRestarts: 3,
        command: 'opencode',
        args: ['serve'],
        env: {},
      },
      openclaw: {
        enabled: true,
        port: 18789,
        url: 'http://localhost:18789',
        healthEndpoint: '/health',
        startupTimeoutMs: 20000,
        restartOnCrash: true,
        maxRestarts: 3,
        command: 'openclaw',
        args: ['gateway'],
        env: {},
      },
      logging: {
        streamToViewer: true,
        maxBufferLines: 1000,
        persistToFile: true,
        logDir: path.join(os.homedir(), '.hanggent', 'logs'),
      },
    };
  }

  /**
   * Initialize services (call once on app ready)
   */
  async initialize(): Promise<void> {
    if (this.isInitialized) {
      log.warn('[ServiceManager] Already initialized');
      return;
    }

    log.info('[ServiceManager] Initializing external services...');

    // Create service instances
    this.openCode = new OpenCodeService(this.config.opencode, this.logRouter);
    this.openClaw = new OpenClawService(this.config.openclaw, this.logRouter);

    // Set up event forwarding
    this.setupEventForwarding(this.openCode);
    this.setupEventForwarding(this.openClaw);

    // Register IPC handlers
    this.registerIpcHandlers();

    this.isInitialized = true;
    log.info('[ServiceManager] Initialization complete');
  }

  /**
   * Set up event forwarding to renderer
   */
  private setupEventForwarding(service: OpenCodeService | OpenClawService): void {
    service.on('status', (state: ServiceState) => {
      this.sendToRenderer('service:status', state);
    });
  }

  /**
   * Send message to renderer process
   */
  private sendToRenderer(channel: string, data: unknown): void {
    if (this.mainWindow && !this.mainWindow.isDestroyed()) {
      try {
        this.mainWindow.webContents.send(channel, data);
      } catch (error) {
        // Window might be closing
      }
    }
  }

  /**
   * Set main window for IPC communication
   */
  setMainWindow(win: BrowserWindow | null): void {
    this.mainWindow = win;
    this.logRouter.setMainWindow(win);
  }

  /**
   * Register IPC handlers for renderer communication
   */
  private registerIpcHandlers(): void {
    // Get service status
    ipcMain.handle('services:getStatus', async () => {
      return {
        opencode: this.openCode?.getState() || null,
        openclaw: this.openClaw?.getState() || null,
      };
    });

    // Get service config
    ipcMain.handle('services:getConfig', async () => {
      return this.config;
    });

    // Start a service
    ipcMain.handle('services:start', async (_event, name: ServiceName) => {
      const service = name === 'opencode' ? this.openCode : this.openClaw;
      if (service) {
        return service.start();
      }
      return false;
    });

    // Stop a service
    ipcMain.handle('services:stop', async (_event, name: ServiceName) => {
      const service = name === 'opencode' ? this.openCode : this.openClaw;
      if (service) {
        await service.stop();
        return true;
      }
      return false;
    });

    // Restart a service
    ipcMain.handle('services:restart', async (_event, name: ServiceName) => {
      const service = name === 'opencode' ? this.openCode : this.openClaw;
      if (service) {
        return service.restart();
      }
      return false;
    });

    // Check service health
    ipcMain.handle('services:checkHealth', async (_event, name: ServiceName) => {
      const service = name === 'opencode' ? this.openCode : this.openClaw;
      if (service) {
        return service.checkHealth();
      }
      return false;
    });

    // Get buffered logs
    ipcMain.handle('services:getLogs', async (_event, source?: ServiceName | 'hanggent') => {
      if (source) {
        return this.logRouter.getBufferedLogs(source);
      }
      return this.logRouter.getAllLogs();
    });

    // Clear logs
    ipcMain.handle('services:clearLogs', async (_event, source: ServiceName | 'hanggent') => {
      this.logRouter.clearLogs(source);
      return true;
    });

    // Update service config
    ipcMain.handle('services:updateConfig', async (_event, name: ServiceName, updates: Partial<ServicesConfig['opencode']>) => {
      if (name === 'opencode') {
        this.config.opencode = { ...this.config.opencode, ...updates };
      } else if (name === 'openclaw') {
        this.config.openclaw = { ...this.config.openclaw, ...updates };
      }
      // Save config to file
      this.saveConfig();
      return true;
    });
  }

  /**
   * Save current config to file
   */
  private saveConfig(): void {
    try {
      const configDir = path.dirname(CONFIG_PATH);
      if (!fs.existsSync(configDir)) {
        fs.mkdirSync(configDir, { recursive: true });
      }
      fs.writeFileSync(CONFIG_PATH, JSON.stringify(this.config, null, 2));
      log.info('[ServiceManager] Config saved');
    } catch (error) {
      log.error('[ServiceManager] Failed to save config:', error);
    }
  }

  /**
   * Start all enabled services
   */
  async startAll(): Promise<void> {
    log.info('[ServiceManager] Starting all enabled services...');

    const promises: Promise<boolean>[] = [];

    if (this.openCode?.isEnabled()) {
      promises.push(this.openCode.start());
    }
    if (this.openClaw?.isEnabled()) {
      promises.push(this.openClaw.start());
    }

    const results = await Promise.allSettled(promises);
    
    results.forEach((result, index) => {
      const serviceName = index === 0 ? 'opencode' : 'openclaw';
      if (result.status === 'fulfilled') {
        log.info(`[ServiceManager] ${serviceName} start result: ${result.value}`);
      } else {
        log.error(`[ServiceManager] ${serviceName} start failed:`, result.reason);
      }
    });
  }

  /**
   * Stop all services
   */
  async stopAll(): Promise<void> {
    log.info('[ServiceManager] Stopping all services...');

    const promises: Promise<void>[] = [];

    if (this.openCode) {
      promises.push(this.openCode.stop());
    }
    if (this.openClaw) {
      promises.push(this.openClaw.stop());
    }

    await Promise.allSettled(promises);
    
    // Close log router
    this.logRouter.close();
    
    log.info('[ServiceManager] All services stopped');
  }

  /**
   * Get OpenCode service instance
   */
  getOpenCode(): OpenCodeService | null {
    return this.openCode;
  }

  /**
   * Get OpenClaw service instance
   */
  getOpenClaw(): OpenClawService | null {
    return this.openClaw;
  }

  /**
   * Check if OpenCode is available
   */
  async isOpenCodeAvailable(): Promise<boolean> {
    if (!this.openCode) return false;
    const state = this.openCode.getState();
    if (state.status !== 'running' && state.status !== 'degraded') return false;
    return this.openCode.checkHealth();
  }

  /**
   * Check if OpenClaw is available
   */
  async isOpenClawAvailable(): Promise<boolean> {
    if (!this.openClaw) return false;
    const state = this.openClaw.getState();
    if (state.status !== 'running' && state.status !== 'degraded') return false;
    return this.openClaw.checkHealth();
  }
}

// Singleton instance
let serviceManager: ServiceManager | null = null;

/**
 * Get or create the ServiceManager singleton
 */
export function getServiceManager(): ServiceManager {
  if (!serviceManager) {
    serviceManager = new ServiceManager();
  }
  return serviceManager;
}

/**
 * Initialize services on app ready
 */
export async function initializeServices(): Promise<ServiceManager> {
  const manager = getServiceManager();
  await manager.initialize();
  await manager.startAll();
  return manager;
}

/**
 * Cleanup services on app quit
 */
export async function cleanupServices(): Promise<void> {
  if (serviceManager) {
    await serviceManager.stopAll();
    serviceManager = null;
  }
}
