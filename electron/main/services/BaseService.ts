/**
 * BaseService - Abstract base class for external service management
 */

import { ChildProcess, spawn } from 'node:child_process';
import { EventEmitter } from 'node:events';
import log from 'electron-log';
import axios from 'axios';
import kill from 'tree-kill';
import { ServiceConfig, ServiceName, ServiceState, ServiceStatus } from './types';
import { LogRouter } from './LogRouter';

export abstract class BaseService extends EventEmitter {
  protected name: ServiceName;
  protected config: ServiceConfig;
  protected process: ChildProcess | null = null;
  protected state: ServiceState;
  protected logRouter: LogRouter;
  protected healthCheckInterval: NodeJS.Timeout | null = null;
  protected isShuttingDown = false;

  constructor(name: ServiceName, config: ServiceConfig, logRouter: LogRouter) {
    super();
    this.name = name;
    this.config = config;
    this.logRouter = logRouter;
    this.state = {
      name,
      status: 'stopped',
      port: config.port,
      url: config.url,
      restartCount: 0,
    };
  }

  /**
   * Get current service state
   */
  getState(): ServiceState {
    return { ...this.state };
  }

  /**
   * Check if service is enabled
   */
  isEnabled(): boolean {
    return this.config.enabled;
  }

  /**
   * Update state and emit event
   */
  protected updateState(updates: Partial<ServiceState>): void {
    this.state = { ...this.state, ...updates };
    this.emit('status', this.state);
  }

  /**
   * Get the actual port (from env var override or config)
   */
  protected getPort(): number {
    const envVar = this.name === 'opencode' ? 'OPENCODE_PORT' : 'OPENCLAW_PORT';
    const envPort = process.env[envVar];
    return envPort ? parseInt(envPort, 10) : this.config.port;
  }

  /**
   * Get the actual URL (from env var override or config)
   */
  protected getUrl(): string {
    const envVar = this.name === 'opencode' ? 'OPENCODE_URL' : 'OPENCLAW_URL';
    const envUrl = process.env[envVar];
    if (envUrl) return envUrl;
    
    // Build URL from port
    const port = this.getPort();
    return `http://localhost:${port}`;
  }

  /**
   * Start the service
   */
  async start(): Promise<boolean> {
    if (!this.config.enabled) {
      log.info(`[${this.name}] Service is disabled, skipping start`);
      this.updateState({ status: 'stopped' });
      return false;
    }

    if (this.state.status === 'running') {
      log.info(`[${this.name}] Service is already running`);
      return true;
    }

    this.isShuttingDown = false;
    this.updateState({ status: 'starting' });
    log.info(`[${this.name}] Starting service...`);

    try {
      await this.spawnProcess();
      
      // Wait for health check
      const healthy = await this.waitForHealth();
      
      if (healthy) {
        this.updateState({
          status: 'running',
          startedAt: new Date(),
          lastError: undefined,
        });
        this.startHealthCheck();
        log.info(`[${this.name}] Service started successfully on port ${this.getPort()}`);
        return true;
      } else {
        throw new Error('Health check failed after startup');
      }
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      log.error(`[${this.name}] Failed to start:`, errorMsg);
      this.updateState({
        status: 'error',
        lastError: errorMsg,
      });
      await this.handleCrash();
      return false;
    }
  }

  /**
   * Spawn the service process
   */
  protected async spawnProcess(): Promise<void> {
    const port = this.getPort();
    const env = {
      ...process.env,
      ...this.config.env,
      PORT: String(port),
    };

    const args = [...this.config.args, '--port', String(port)];

    log.info(`[${this.name}] Spawning: ${this.config.command} ${args.join(' ')}`);

    this.process = spawn(this.config.command, args, {
      env,
      stdio: ['ignore', 'pipe', 'pipe'],
      shell: process.platform === 'win32',
      detached: false,
    });

    this.updateState({ pid: this.process.pid });

    // Route stdout/stderr to log router
    this.process.stdout?.on('data', (data) => {
      this.logRouter.route(this.name, data, false);
    });

    this.process.stderr?.on('data', (data) => {
      this.logRouter.route(this.name, data, true);
    });

    // Handle process exit
    this.process.on('exit', (code, signal) => {
      log.info(`[${this.name}] Process exited with code ${code}, signal ${signal}`);
      this.process = null;
      this.updateState({ pid: undefined });
      
      if (!this.isShuttingDown && this.state.status === 'running') {
        this.updateState({ status: 'error', lastError: `Process exited with code ${code}` });
        this.handleCrash();
      }
    });

    this.process.on('error', (error) => {
      log.error(`[${this.name}] Process error:`, error);
      this.updateState({ status: 'error', lastError: error.message });
    });
  }

  /**
   * Wait for service to become healthy
   */
  protected async waitForHealth(): Promise<boolean> {
    const startTime = Date.now();
    const timeout = this.config.startupTimeoutMs;
    const interval = 500;

    while (Date.now() - startTime < timeout) {
      if (this.isShuttingDown) return false;
      
      try {
        const healthy = await this.checkHealth();
        if (healthy) return true;
      } catch {
        // Ignore errors during startup
      }
      
      await new Promise(resolve => setTimeout(resolve, interval));
    }

    return false;
  }

  /**
   * Check service health
   */
  async checkHealth(): Promise<boolean> {
    try {
      const url = `${this.getUrl()}${this.config.healthEndpoint}`;
      const response = await axios.get(url, { timeout: 5000 });
      return response.status >= 200 && response.status < 300;
    } catch {
      return false;
    }
  }

  /**
   * Start periodic health checks
   */
  protected startHealthCheck(): void {
    this.stopHealthCheck();
    
    this.healthCheckInterval = setInterval(async () => {
      if (this.state.status !== 'running') return;
      
      try {
        const healthy = await this.checkHealth();
        if (!healthy && !this.isShuttingDown) {
          log.warn(`[${this.name}] Health check failed`);
          this.updateState({ status: 'degraded' });
        } else if (healthy && this.state.status === 'degraded') {
          this.updateState({ status: 'running' });
        }
      } catch (error) {
        log.error(`[${this.name}] Health check error:`, error);
      }
    }, 30000); // Check every 30 seconds
  }

  /**
   * Stop health check interval
   */
  protected stopHealthCheck(): void {
    if (this.healthCheckInterval) {
      clearInterval(this.healthCheckInterval);
      this.healthCheckInterval = null;
    }
  }

  /**
   * Handle service crash
   */
  protected async handleCrash(): Promise<void> {
    if (this.isShuttingDown) return;
    
    if (!this.config.restartOnCrash) {
      log.info(`[${this.name}] Auto-restart disabled`);
      return;
    }

    if (this.state.restartCount >= this.config.maxRestarts) {
      log.error(`[${this.name}] Max restarts (${this.config.maxRestarts}) reached`);
      this.updateState({ status: 'error', lastError: 'Max restarts exceeded' });
      return;
    }

    this.updateState({ restartCount: this.state.restartCount + 1 });
    log.info(`[${this.name}] Attempting restart (${this.state.restartCount}/${this.config.maxRestarts})...`);
    
    await new Promise(resolve => setTimeout(resolve, 2000)); // Wait before restart
    await this.start();
  }

  /**
   * Stop the service
   */
  async stop(): Promise<void> {
    this.isShuttingDown = true;
    this.stopHealthCheck();

    if (!this.process) {
      this.updateState({ status: 'stopped' });
      return;
    }

    log.info(`[${this.name}] Stopping service...`);

    return new Promise((resolve) => {
      const pid = this.process?.pid;
      
      if (!pid) {
        this.updateState({ status: 'stopped' });
        resolve();
        return;
      }

      // Set a timeout for forced kill
      const timeout = setTimeout(() => {
        log.warn(`[${this.name}] Graceful shutdown timeout, forcing kill`);
        kill(pid, 'SIGKILL', (err) => {
          if (err) log.error(`[${this.name}] Force kill error:`, err);
          this.process = null;
          this.updateState({ status: 'stopped', pid: undefined });
          resolve();
        });
      }, 5000);

      // Attempt graceful shutdown
      kill(pid, 'SIGTERM', (err) => {
        clearTimeout(timeout);
        if (err) {
          log.error(`[${this.name}] SIGTERM error:`, err);
        }
        this.process = null;
        this.updateState({ status: 'stopped', pid: undefined });
        log.info(`[${this.name}] Service stopped`);
        resolve();
      });
    });
  }

  /**
   * Restart the service
   */
  async restart(): Promise<boolean> {
    log.info(`[${this.name}] Restarting service...`);
    this.state.restartCount = 0; // Reset restart count on manual restart
    await this.stop();
    return this.start();
  }
}
