/**
 * Types for external service management
 */

export interface ServiceConfig {
  enabled: boolean;
  port: number;
  url: string;
  healthEndpoint: string;
  startupTimeoutMs: number;
  restartOnCrash: boolean;
  maxRestarts: number;
  command: string;
  args: string[];
  env: Record<string, string>;
}

export interface LoggingConfig {
  streamToViewer: boolean;
  maxBufferLines: number;
  persistToFile: boolean;
  logDir: string;
}

export interface ServicesConfig {
  opencode: ServiceConfig;
  openclaw: ServiceConfig;
  logging: LoggingConfig;
}

export type ServiceName = 'opencode' | 'openclaw';

export type ServiceStatus = 'stopped' | 'starting' | 'running' | 'error' | 'degraded';

export interface ServiceState {
  name: ServiceName;
  status: ServiceStatus;
  port: number;
  url: string;
  pid?: number;
  restartCount: number;
  lastError?: string;
  startedAt?: Date;
}

export interface LogEntry {
  timestamp: Date;
  source: ServiceName | 'hanggent';
  level: 'debug' | 'info' | 'warn' | 'error';
  message: string;
}

export interface ServiceEvents {
  'service:status': (state: ServiceState) => void;
  'service:log': (entry: LogEntry) => void;
  'service:error': (name: ServiceName, error: Error) => void;
}
