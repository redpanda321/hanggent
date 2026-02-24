/**
 * React hooks for managing external service status (OpenCode, OpenClaw)
 * 
 * Provides real-time status updates and control functions for external services
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { proxyFetchGet, proxyFetchPost } from '@/api/http';

// Re-export types for convenience
export type ServiceName = 'opencode' | 'openclaw';
export type ServiceStatus = 'stopped' | 'starting' | 'running' | 'stopping' | 'error' | 'degraded';

export interface ServiceState {
  name: ServiceName;
  status: ServiceStatus;
  pid?: number;
  startTime?: number;
  restartCount: number;
  lastError?: string;
  healthCheck?: {
    healthy: boolean;
    lastCheck: number;
    responseTimeMs?: number;
  };
}

export interface ServicesStatus {
  opencode: ServiceState | null;
  openclaw: ServiceState | null;
}

interface UseServiceStatusOptions {
  /** Auto-refresh interval in ms (0 to disable) */
  refreshInterval?: number;
  /** Whether to subscribe to real-time updates */
  subscribeToUpdates?: boolean;
}

/**
 * Hook for monitoring service status
 */
export function useServiceStatus(options: UseServiceStatusOptions = {}) {
  const { refreshInterval = 5000, subscribeToUpdates = true } = options;
  
  const [status, setStatus] = useState<ServicesStatus>({
    opencode: null,
    openclaw: null,
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const unsubscribeRef = useRef<(() => void) | null>(null);

  // Check if we're in Electron environment
  const isElectron = typeof window !== 'undefined' && window.electronAPI?.services;

  // Fetch current status (Electron IPC or web API fallback for openclaw)
  const fetchStatus = useCallback(async () => {
    if (isElectron) {
      try {
        const result = await window.electronAPI.services.getStatus();
        setStatus(result);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to fetch service status');
      } finally {
        setLoading(false);
      }
      return;
    }

    // Web mode: fetch openclaw status via server API
    try {
      const result = await proxyFetchGet('/api/bot/status');
      if (result) {
        setStatus((prev) => ({
          ...prev,
          openclaw: {
            name: 'openclaw' as ServiceName,
            status: result.status ?? 'stopped',
            pid: undefined,
            startTime: result.startedAt ?? undefined,
            restartCount: 0,
            lastError: result.lastError ?? undefined,
            healthCheck: result.health
              ? {
                  healthy: result.health.healthy,
                  lastCheck: Date.now(),
                  responseTimeMs: undefined,
                }
              : undefined,
          },
        }));
        setError(null);
      }
    } catch (err) {
      // Server unreachable or user not authenticated
      setStatus((prev) => ({ ...prev, openclaw: null }));
      setError(err instanceof Error ? err.message : 'Failed to fetch bot status');
    } finally {
      setLoading(false);
    }
  }, [isElectron]);

  // Subscribe to real-time updates
  useEffect(() => {
    if (!isElectron || !subscribeToUpdates) return;

    unsubscribeRef.current = window.electronAPI.services.onStatusChange((state: ServiceState) => {
      setStatus((prev) => ({
        ...prev,
        [state.name]: state,
      }));
    });

    return () => {
      if (unsubscribeRef.current) {
        unsubscribeRef.current();
        unsubscribeRef.current = null;
      }
    };
  }, [isElectron, subscribeToUpdates]);

  // Initial fetch and periodic refresh
  useEffect(() => {
    fetchStatus();

    if (refreshInterval > 0) {
      const intervalId = setInterval(fetchStatus, refreshInterval);
      return () => clearInterval(intervalId);
    }
  }, [fetchStatus, refreshInterval]);

  return {
    status,
    loading,
    error,
    refresh: fetchStatus,
    isAvailable: !!isElectron || true, // Web mode supports openclaw via server API
  };
}

/**
 * Hook for controlling a specific service
 */
export function useServiceControl(serviceName: ServiceName) {
  const [actionLoading, setActionLoading] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const isElectron = typeof window !== 'undefined' && window.electronAPI?.services;

  // Web mode: openclaw control via server API
  const isWebOpenClaw = !isElectron && serviceName === 'openclaw';

  const start = useCallback(async () => {
    if (!isElectron && !isWebOpenClaw) return false;
    
    setActionLoading(true);
    setActionError(null);
    
    try {
      if (isWebOpenClaw) {
        await proxyFetchPost('/api/bot/start');
        return true;
      }
      return await window.electronAPI.services.start(serviceName);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to start service');
      return false;
    } finally {
      setActionLoading(false);
    }
  }, [isElectron, isWebOpenClaw, serviceName]);

  const stop = useCallback(async () => {
    if (!isElectron && !isWebOpenClaw) return false;
    
    setActionLoading(true);
    setActionError(null);
    
    try {
      if (isWebOpenClaw) {
        await proxyFetchPost('/api/bot/stop');
        return true;
      }
      return await window.electronAPI.services.stop(serviceName);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to stop service');
      return false;
    } finally {
      setActionLoading(false);
    }
  }, [isElectron, isWebOpenClaw, serviceName]);

  const restart = useCallback(async () => {
    if (!isElectron && !isWebOpenClaw) return false;
    
    setActionLoading(true);
    setActionError(null);
    
    try {
      if (isWebOpenClaw) {
        await proxyFetchPost('/api/bot/stop');
        await proxyFetchPost('/api/bot/start');
        return true;
      }
      return await window.electronAPI.services.restart(serviceName);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to restart service');
      return false;
    } finally {
      setActionLoading(false);
    }
  }, [isElectron, isWebOpenClaw, serviceName]);

  const checkHealth = useCallback(async () => {
    if (!isElectron && !isWebOpenClaw) return false;
    
    try {
      if (isWebOpenClaw) {
        const result = await proxyFetchGet('/api/bot/status');
        return result?.health?.healthy === true;
      }
      return await window.electronAPI.services.checkHealth(serviceName);
    } catch (err) {
      return false;
    }
  }, [isElectron, isWebOpenClaw, serviceName]);

  return {
    start,
    stop,
    restart,
    checkHealth,
    loading: actionLoading,
    error: actionError,
    isAvailable: !!isElectron || isWebOpenClaw,
  };
}

/**
 * Hook for fetching and subscribing to service logs
 */
export function useServiceLogs(source?: ServiceName | 'hanggent') {
  const [logs, setLogs] = useState<Array<{
    source: string;
    level: string;
    message: string;
    timestamp: number;
  }>>([]);
  const [loading, setLoading] = useState(true);
  const unsubscribeRef = useRef<(() => void) | null>(null);

  const isElectron = typeof window !== 'undefined' && window.electronAPI?.services;

  // Fetch existing logs
  const fetchLogs = useCallback(async () => {
    if (!isElectron) {
      setLoading(false);
      return;
    }

    try {
      const result = await window.electronAPI.services.getLogs(source);
      setLogs(result);
    } catch (err) {
      console.error('Failed to fetch logs:', err);
    } finally {
      setLoading(false);
    }
  }, [isElectron, source]);

  // Clear logs
  const clearLogs = useCallback(async () => {
    if (!isElectron || !source) return;

    try {
      await window.electronAPI.services.clearLogs(source);
      setLogs([]);
    } catch (err) {
      console.error('Failed to clear logs:', err);
    }
  }, [isElectron, source]);

  // Define log type for callback
  interface LogCallbackEntry {
    source: string;
    level: string;
    message: string;
    timestamp: number;
  }

  // Subscribe to real-time log updates
  useEffect(() => {
    if (!isElectron) return;

    unsubscribeRef.current = window.electronAPI.services.onLog((log: LogCallbackEntry) => {
      // Filter by source if specified
      if (!source || log.source === source) {
        setLogs((prev) => [...prev, log].slice(-1000)); // Keep last 1000 logs
      }
    });

    return () => {
      if (unsubscribeRef.current) {
        unsubscribeRef.current();
        unsubscribeRef.current = null;
      }
    };
  }, [isElectron, source]);

  // Initial fetch
  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  return {
    logs,
    loading,
    clearLogs,
    refresh: fetchLogs,
    isAvailable: isElectron,
  };
}

/**
 * Hook for service configuration
 */
export function useServiceConfig() {
  const [config, setConfig] = useState<{
    opencode: {
      enabled: boolean;
      port: number;
      url: string;
    };
    openclaw: {
      enabled: boolean;
      port: number;
      url: string;
    };
  } | null>(null);
  const [loading, setLoading] = useState(true);

  const isElectron = typeof window !== 'undefined' && window.electronAPI?.services;

  const fetchConfig = useCallback(async () => {
    if (!isElectron) {
      setLoading(false);
      return;
    }

    try {
      const result = await window.electronAPI.services.getConfig();
      setConfig({
        opencode: {
          enabled: result.opencode.enabled,
          port: result.opencode.port,
          url: result.opencode.url,
        },
        openclaw: {
          enabled: result.openclaw.enabled,
          port: result.openclaw.port,
          url: result.openclaw.url,
        },
      });
    } catch (err) {
      console.error('Failed to fetch config:', err);
    } finally {
      setLoading(false);
    }
  }, [isElectron]);

  const updateConfig = useCallback(async (
    name: ServiceName,
    updates: Partial<{ enabled: boolean; port: number; url: string }>
  ) => {
    if (!isElectron) return false;

    try {
      await window.electronAPI.services.updateConfig(name, updates);
      await fetchConfig(); // Refresh after update
      return true;
    } catch (err) {
      console.error('Failed to update config:', err);
      return false;
    }
  }, [isElectron, fetchConfig]);

  useEffect(() => {
    fetchConfig();
  }, [fetchConfig]);

  return {
    config,
    loading,
    updateConfig,
    refresh: fetchConfig,
    isAvailable: isElectron,
  };
}

/**
 * Utility function to get status color for UI
 */
export function getStatusColor(status: ServiceStatus): string {
  switch (status) {
    case 'running':
      return 'text-green-500';
    case 'starting':
    case 'stopping':
      return 'text-yellow-500';
    case 'degraded':
      return 'text-orange-500';
    case 'error':
      return 'text-red-500';
    case 'stopped':
    default:
      return 'text-gray-500';
  }
}

/**
 * Utility function to get status badge variant
 */
export function getStatusBadgeVariant(status: ServiceStatus): 'default' | 'secondary' | 'destructive' | 'outline' {
  switch (status) {
    case 'running':
      return 'default';
    case 'starting':
    case 'stopping':
    case 'degraded':
      return 'secondary';
    case 'error':
      return 'destructive';
    case 'stopped':
    default:
      return 'outline';
  }
}
