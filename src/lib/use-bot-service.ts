/**
 * React hooks for managing per-user OpenClaw bot instances via the web API.
 *
 * In Electron mode, the existing useServiceStatus/useServiceControl hooks
 * communicate via IPC to the local sidecar. In web mode, these hooks call
 * the hanggent-server's /api/bot/* endpoints which proxy to the OpenClaw
 * supervisor running in K8s.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { proxyFetchGet, proxyFetchPost } from '@/api/http';
import { getAuthStore } from '@/store/authStore';

// ── Types ──────────────────────────────────────────────────────────────────────

export type BotStatus = 'stopped' | 'starting' | 'running' | 'stopping' | 'error';

export interface BotState {
  userId: string | null;
  port: number | null;
  status: BotStatus;
  lastActiveAt: number | null;
  startedAt: number | null;
  lastError: string | null;
  health: {
    healthy: boolean;
    status: string;
    data?: Record<string, any>;
  } | null;
}

const DEFAULT_STATE: BotState = {
  userId: null,
  port: null,
  status: 'stopped',
  lastActiveAt: null,
  startedAt: null,
  lastError: null,
  health: null,
};

// ── useBotStatus ───────────────────────────────────────────────────────────────

interface UseBotStatusOptions {
  /** Auto-refresh interval in ms (0 to disable) */
  refreshInterval?: number;
  /** Only poll when user is authenticated */
  requireAuth?: boolean;
}

/**
 * Hook for monitoring the current user's OpenClaw bot status.
 * Works in web mode by polling the server's /api/bot/status endpoint.
 */
export function useBotStatus(options: UseBotStatusOptions = {}) {
  const { refreshInterval = 5000, requireAuth = true } = options;

  const [state, setState] = useState<BotState>(DEFAULT_STATE);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchStatus = useCallback(async () => {
    if (requireAuth) {
      const { token } = getAuthStore();
      if (!token) {
        setLoading(false);
        return;
      }
    }

    try {
      const result = await proxyFetchGet('/api/bot/status');
      if (result) {
        setState({
          userId: result.userId ?? null,
          port: result.port ?? null,
          status: result.status ?? 'stopped',
          lastActiveAt: result.lastActiveAt ?? null,
          startedAt: result.startedAt ?? null,
          lastError: result.lastError ?? null,
          health: result.health ?? null,
        });
        setError(null);
      }
    } catch (err) {
      // If server is unreachable or unauthorized, show stopped
      setState(DEFAULT_STATE);
      setError(err instanceof Error ? err.message : 'Failed to fetch bot status');
    } finally {
      setLoading(false);
    }
  }, [requireAuth]);

  useEffect(() => {
    fetchStatus();
    if (refreshInterval > 0) {
      const id = setInterval(fetchStatus, refreshInterval);
      return () => clearInterval(id);
    }
  }, [fetchStatus, refreshInterval]);

  return {
    state,
    loading,
    error,
    refresh: fetchStatus,
    isRunning: state.status === 'running',
    isStarting: state.status === 'starting',
    isStopped: state.status === 'stopped',
  };
}

// ── useBotControl ──────────────────────────────────────────────────────────────

/**
 * Hook for starting/stopping the current user's OpenClaw bot.
 */
export function useBotControl() {
  const [actionLoading, setActionLoading] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const start = useCallback(async () => {
    setActionLoading(true);
    setActionError(null);
    try {
      const result = await proxyFetchPost('/api/bot/start');
      return result;
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to start bot';
      setActionError(msg);
      return null;
    } finally {
      setActionLoading(false);
    }
  }, []);

  const stop = useCallback(async () => {
    setActionLoading(true);
    setActionError(null);
    try {
      const result = await proxyFetchPost('/api/bot/stop');
      return result;
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to stop bot';
      setActionError(msg);
      return null;
    } finally {
      setActionLoading(false);
    }
  }, []);

  return {
    start,
    stop,
    loading: actionLoading,
    error: actionError,
  };
}

// ── useBotChannels ─────────────────────────────────────────────────────────────

export interface BotChannel {
  name: string;
  type: string;
  connected: boolean;
  [key: string]: any;
}

/**
 * Hook for fetching the user's bot channel connections.
 */
export function useBotChannels(options: { refreshInterval?: number } = {}) {
  const { refreshInterval = 10000 } = options;

  const [channels, setChannels] = useState<BotChannel[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchChannels = useCallback(async () => {
    try {
      const result = await proxyFetchGet('/api/bot/channels');
      if (result && Array.isArray(result)) {
        setChannels(result);
      } else if (result?.channels) {
        setChannels(result.channels);
      }
    } catch {
      // Bot may not be running
      setChannels([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchChannels();
    if (refreshInterval > 0) {
      const id = setInterval(fetchChannels, refreshInterval);
      return () => clearInterval(id);
    }
  }, [fetchChannels, refreshInterval]);

  return { channels, loading, refresh: fetchChannels };
}

// ── useBotWebSocket ────────────────────────────────────────────────────────────

interface UseBotWebSocketOptions {
  /** Auto-connect when hook mounts */
  autoConnect?: boolean;
  /** Reconnect delay in ms */
  reconnectDelay?: number;
  /** Max reconnect attempts (0 = infinite) */
  maxReconnects?: number;
}

/**
 * Hook for a WebSocket connection to the user's OpenClaw gateway.
 * Connects through the server's /api/bot/ws proxy endpoint.
 */
export function useBotWebSocket(options: UseBotWebSocketOptions = {}) {
  const { autoConnect = false, reconnectDelay = 3000, maxReconnects = 5 } = options;

  const [connected, setConnected] = useState(false);
  const [messages, setMessages] = useState<any[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectCountRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const getWsUrl = useCallback(() => {
    const { token } = getAuthStore();
    if (!token) return null;

    // Derive WS URL from the base URL
    const isDev = import.meta.env.DEV;
    let baseUrl: string;

    if (isDev) {
      const proxyUrl = import.meta.env.VITE_PROXY_URL;
      baseUrl = proxyUrl || 'http://localhost:3001';
    } else {
      // Check runtime config first (set by runtime-env.sh in Docker)
      const runtimeBaseUrl = typeof window !== 'undefined' && (window as any).__ENV?.VITE_BASE_URL;
      baseUrl = runtimeBaseUrl || import.meta.env.VITE_BASE_URL || window.location.origin;
    }

    const wsBase = baseUrl.replace(/^http/, 'ws');
    return `${wsBase}/api/bot/ws?token=${encodeURIComponent(token)}`;
  }, []);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const url = getWsUrl();
    if (!url) return;

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      reconnectCountRef.current = 0;
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        setMessages((prev) => {
          const next = [...prev, data];
          return next.length > 500 ? next.slice(-500) : next;
        });
      } catch {
        setMessages((prev) => {
          const next = [...prev, { raw: event.data }];
          return next.length > 500 ? next.slice(-500) : next;
        });
      }
    };

    ws.onclose = () => {
      setConnected(false);
      wsRef.current = null;

      // Auto-reconnect
      if (maxReconnects === 0 || reconnectCountRef.current < maxReconnects) {
        reconnectCountRef.current++;
        reconnectTimerRef.current = setTimeout(connect, reconnectDelay);
      }
    };

    ws.onerror = () => {
      // onclose will handle reconnection
    };
  }, [getWsUrl, reconnectDelay, maxReconnects]);

  const disconnect = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    reconnectCountRef.current = maxReconnects; // prevent reconnect
    wsRef.current?.close();
    wsRef.current = null;
    setConnected(false);
  }, [maxReconnects]);

  const send = useCallback((data: any) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(typeof data === 'string' ? data : JSON.stringify(data));
      return true;
    }
    return false;
  }, []);

  const clearMessages = useCallback(() => {
    setMessages([]);
  }, []);

  // Auto-connect
  useEffect(() => {
    if (autoConnect) connect();
    return () => disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoConnect]);

  return {
    connected,
    messages,
    connect,
    disconnect,
    send,
    clearMessages,
  };
}
