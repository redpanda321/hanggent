/**
 * LogRouter - Routes logs from external services to the renderer process
 */

import { BrowserWindow } from 'electron';
import log from 'electron-log';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { LogEntry, ServiceName, LoggingConfig } from './types';

export class LogRouter {
  private logBuffer: Map<ServiceName | 'hanggent', LogEntry[]> = new Map();
  private maxBufferLines: number;
  private logDir: string;
  private logStreams: Map<string, fs.WriteStream> = new Map();
  private mainWindow: BrowserWindow | null = null;

  constructor(config: LoggingConfig) {
    this.maxBufferLines = config.maxBufferLines;
    this.logDir = config.logDir.replace('~', os.homedir());
    
    // Initialize buffers
    this.logBuffer.set('opencode', []);
    this.logBuffer.set('openclaw', []);
    this.logBuffer.set('hanggent', []);

    // Ensure log directory exists
    if (config.persistToFile) {
      this.ensureLogDir();
    }
  }

  /**
   * Set the main window for IPC communication
   */
  setMainWindow(win: BrowserWindow | null): void {
    this.mainWindow = win;
  }

  /**
   * Ensure log directory exists
   */
  private ensureLogDir(): void {
    try {
      if (!fs.existsSync(this.logDir)) {
        fs.mkdirSync(this.logDir, { recursive: true });
      }
    } catch (error) {
      log.error('[LogRouter] Failed to create log directory:', error);
    }
  }

  /**
   * Get or create a write stream for a service
   */
  private getLogStream(source: ServiceName): fs.WriteStream {
    if (!this.logStreams.has(source)) {
      const logFile = path.join(this.logDir, `${source}.log`);
      const stream = fs.createWriteStream(logFile, { flags: 'a' });
      this.logStreams.set(source, stream);
    }
    return this.logStreams.get(source)!;
  }

  /**
   * Parse log level from message content
   */
  private parseLogLevel(message: string): 'debug' | 'info' | 'warn' | 'error' {
    const lowerMsg = message.toLowerCase();
    if (lowerMsg.includes('error') || lowerMsg.includes('fatal')) return 'error';
    if (lowerMsg.includes('warn')) return 'warn';
    if (lowerMsg.includes('debug') || lowerMsg.includes('trace')) return 'debug';
    return 'info';
  }

  /**
   * Route a log message from a service
   */
  route(source: ServiceName, data: string | Buffer, isError: boolean = false): void {
    const message = data.toString().trim();
    if (!message) return;

    // Split by newlines and process each line
    const lines = message.split('\n');
    
    for (const line of lines) {
      if (!line.trim()) continue;

      const entry: LogEntry = {
        timestamp: new Date(),
        source,
        level: isError ? 'error' : this.parseLogLevel(line),
        message: line.trim(),
      };

      // Add to buffer
      const buffer = this.logBuffer.get(source)!;
      buffer.push(entry);
      
      // Trim buffer if needed
      if (buffer.length > this.maxBufferLines) {
        buffer.shift();
      }

      // Write to file
      try {
        const stream = this.getLogStream(source);
        const logLine = `[${entry.timestamp.toISOString()}] [${entry.level.toUpperCase()}] ${entry.message}\n`;
        stream.write(logLine);
      } catch (error) {
        log.error(`[LogRouter] Failed to write log for ${source}:`, error);
      }

      // Send to renderer via IPC
      this.sendToRenderer(entry);

      // Also log to electron-log for debugging
      if (entry.level === 'error') {
        log.error(`[${source}] ${entry.message}`);
      } else if (entry.level === 'warn') {
        log.warn(`[${source}] ${entry.message}`);
      } else {
        log.info(`[${source}] ${entry.message}`);
      }
    }
  }

  /**
   * Send log entry to renderer process
   */
  private sendToRenderer(entry: LogEntry): void {
    if (this.mainWindow && !this.mainWindow.isDestroyed()) {
      try {
        this.mainWindow.webContents.send('service:log', {
          timestamp: entry.timestamp.toISOString(),
          source: entry.source,
          level: entry.level,
          message: entry.message,
        });
      } catch (error) {
        // Window might be closing, ignore
      }
    }
  }

  /**
   * Get buffered logs for a service
   */
  getBufferedLogs(source: ServiceName | 'hanggent'): LogEntry[] {
    return this.logBuffer.get(source) || [];
  }

  /**
   * Get all buffered logs
   */
  getAllLogs(): LogEntry[] {
    const allLogs: LogEntry[] = [];
    for (const buffer of this.logBuffer.values()) {
      allLogs.push(...buffer);
    }
    return allLogs.sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime());
  }

  /**
   * Clear logs for a service
   */
  clearLogs(source: ServiceName | 'hanggent'): void {
    this.logBuffer.set(source, []);
  }

  /**
   * Close all log streams
   */
  close(): void {
    for (const stream of this.logStreams.values()) {
      try {
        stream.end();
      } catch (error) {
        log.error('[LogRouter] Error closing log stream:', error);
      }
    }
    this.logStreams.clear();
  }
}
