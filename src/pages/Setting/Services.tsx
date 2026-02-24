// ========= Copyright 2025-2026 @ Hanggent.AI All Rights Reserved. =========
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
// ========= Copyright 2025-2026 @ Hanggent.AI All Rights Reserved. =========

import { Button } from '@/components/ui/button';
import { getPlatformService } from '@/service/platform';
import { proxyFetchGet, proxyFetchPost } from '@/api/http';
import { getAuthStore } from '@/store/authStore';
import {
  Activity,
  AlertCircle,
  CheckCircle2,
  CloudOff,
  Loader2,
  Play,
  RefreshCcw,
  ScrollText,
  Square,
  Trash,
} from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

// ── Status styling ─────────────────────────────────────────────────────────────

type ExtendedStatus = ServiceStatus | 'stopping' | 'not_deployed';

const STATUS_COLORS: Record<ExtendedStatus, string> = {
  stopped: 'text-text-tertiary',
  starting: 'text-amber-500',
  running: 'text-emerald-500',
  stopping: 'text-amber-500',
  error: 'text-red-500',
  degraded: 'text-amber-500',
  not_deployed: 'text-text-tertiary',
};

const STATUS_ICONS: Record<ExtendedStatus, React.ReactNode> = {
  stopped: <Square size={14} />,
  starting: <Loader2 size={14} className="animate-spin" />,
  running: <CheckCircle2 size={14} />,
  stopping: <Loader2 size={14} className="animate-spin" />,
  error: <AlertCircle size={14} />,
  degraded: <AlertCircle size={14} />,
  not_deployed: <CloudOff size={14} />,
};

interface ServiceCardProps {
  name: ServiceName;
  label: string;
  description: string;
  state: ServiceState | null;
  readOnly?: boolean;
  statusOverride?: ExtendedStatus;
  statusLabel?: string;
  onStart: () => void;
  onStop: () => void;
  onRestart: () => void;
}

function ServiceCard({
  name,
  label,
  description,
  state,
  readOnly,
  statusOverride,
  statusLabel,
  onStart,
  onStop,
  onRestart,
}: ServiceCardProps) {
  const { t } = useTranslation();
  const status: ExtendedStatus = statusOverride ?? state?.status ?? 'stopped';
  const isRunning = status === 'running';
  const isBusy = status === 'starting' || status === 'stopping';

  return (
    <div className="flex items-center justify-between rounded-xl border border-solid border-border-primary bg-surface-secondary p-4">
      <div className="flex items-center gap-3">
        <div className={`flex items-center gap-1.5 ${STATUS_COLORS[status]}`}>
          {STATUS_ICONS[status]}
          <span className="text-xs font-semibold uppercase">
            {statusLabel ?? status}
          </span>
        </div>
        <div>
          <div className="text-sm font-semibold text-text-primary">{label}</div>
          <div className="text-xs text-text-tertiary">{description}</div>
          {state?.lastError && (
            <div className="mt-1 text-xs text-red-500">{state.lastError}</div>
          )}
        </div>
      </div>
      {!readOnly && (
        <div className="flex items-center gap-1">
          {!isRunning && !isBusy && (
            <Button size="sm" variant="ghost" onClick={onStart}>
              <Play size={14} />
              <span className="ml-1 text-xs">
                {t('setting.services.start', 'Start')}
              </span>
            </Button>
          )}
          {isRunning && (
            <Button size="sm" variant="ghost" onClick={onStop}>
              <Square size={14} />
              <span className="ml-1 text-xs">
                {t('setting.services.stop', 'Stop')}
              </span>
            </Button>
          )}
          <Button size="sm" variant="ghost" onClick={onRestart} disabled={isBusy}>
            <RefreshCcw size={14} />
          </Button>
        </div>
      )}
    </div>
  );
}

/** Log entry from the web SSE stream (different shape from Electron LogEntry) */
interface WebLogEntry {
  ts: number;
  level: string;
  msg: string;
}

/** Normalize to a common display shape */
interface DisplayLog {
  timestamp: number;
  level: string;
  message: string;
}

function toDisplayLog(entry: LogEntry): DisplayLog {
  return {
    timestamp:
      typeof entry.timestamp === 'number'
        ? entry.timestamp
        : new Date(entry.timestamp).getTime(),
    level: entry.level,
    message: entry.message,
  };
}

function webLogToDisplay(entry: WebLogEntry): DisplayLog {
  return { timestamp: entry.ts, level: entry.level, message: entry.msg };
}

/**
 * Build the SSE URL for bot log streaming in web mode.
 * Uses the same base URL logic as `proxyFetchGet`.
 */
function getBotLogStreamUrl(): string {
  const isDev = import.meta.env.DEV;
  let base: string;
  if (isDev) {
    base = import.meta.env.VITE_PROXY_URL || 'http://localhost:3001';
  } else {
    // Check runtime config first (set by runtime-env.sh in Docker)
    const runtimeBaseUrl = typeof window !== 'undefined' && (window as any).__ENV?.VITE_BASE_URL;
    base = runtimeBaseUrl || import.meta.env.VITE_BASE_URL || '';
  }
  return `${base}/api/bot/logs/stream`;
}

function ServiceLogs({
  name,
  webLogsAvailable,
}: {
  name: ServiceName;
  webLogsAvailable?: boolean;
}) {
  const { t } = useTranslation();
  const platform = getPlatformService();
  const [logs, setLogs] = useState<DisplayLog[]>([]);
  const [expanded, setExpanded] = useState(false);
  const eventSourceRef = useRef<EventSource | null>(null);

  // ── Electron: IPC logs ───────────────────────────────────────────
  const fetchElectronLogs = useCallback(async () => {
    if (!platform.isElectron) return;
    try {
      const result = await (window as any).electronAPI.services.getLogs(name);
      setLogs((result ?? []).map(toDisplayLog));
    } catch {
      // noop
    }
  }, [name, platform.isElectron]);

  useEffect(() => {
    if (!platform.isElectron) return;
    fetchElectronLogs();

    const unsub = (window as any).electronAPI.services.onLog(
      (entry: LogEntry) => {
        if (entry.source === name) {
          setLogs((prev) => [...prev.slice(-199), toDisplayLog(entry)]);
        }
      }
    );
    return () => unsub?.();
  }, [name, fetchElectronLogs, platform.isElectron]);

  // ── Web: SSE logs (OpenClaw only) ────────────────────────────────
  const fetchWebLogs = useCallback(async () => {
    if (platform.isElectron || !webLogsAvailable) return;
    try {
      const result = await proxyFetchGet('/api/bot/logs');
      if (result?.entries) {
        setLogs(result.entries.map(webLogToDisplay));
      }
    } catch {
      // noop
    }
  }, [platform.isElectron, webLogsAvailable]);

  useEffect(() => {
    if (platform.isElectron || !webLogsAvailable || !expanded) return;
    fetchWebLogs();

    // Connect SSE for real-time streaming
    const { token } = getAuthStore();
    const url = getBotLogStreamUrl();
    const es = new EventSource(
      `${url}${url.includes('?') ? '&' : '?'}token=${encodeURIComponent(token ?? '')}`,
    );
    eventSourceRef.current = es;

    es.onmessage = (ev) => {
      try {
        const data: WebLogEntry = JSON.parse(ev.data);
        setLogs((prev) => [...prev.slice(-499), webLogToDisplay(data)]);
      } catch {
        // non-JSON keep-alive comments, ignore
      }
    };

    es.onerror = () => {
      // EventSource auto-reconnects; nothing to do
    };

    return () => {
      es.close();
      eventSourceRef.current = null;
    };
  }, [platform.isElectron, webLogsAvailable, expanded, fetchWebLogs]);

  // ── Clear ────────────────────────────────────────────────────────
  const handleClear = async () => {
    if (platform.isElectron) {
      await (window as any).electronAPI.services.clearLogs(name);
    }
    setLogs([]);
  };

  // ── Desktop-only notice for services without web log support ────
  if (!platform.isElectron && !webLogsAvailable) {
    return (
      <div className="text-xs text-text-tertiary">
        {t(
          'setting.services.logs-desktop-only',
          'Logs available in desktop mode only',
        )}
      </div>
    );
  }

  if (!expanded) {
    return (
      <button
        onClick={() => setExpanded(true)}
        className="flex items-center gap-1 bg-transparent text-xs text-text-tertiary transition-colors hover:text-text-primary"
      >
        <ScrollText size={12} />
        {t('setting.services.show-logs', 'Show logs')} ({logs.length})
      </button>
    );
  }

  return (
    <div className="mt-2 flex flex-col gap-1">
      <div className="flex items-center justify-between">
        <button
          onClick={() => setExpanded(false)}
          className="bg-transparent text-xs text-text-tertiary hover:text-text-primary"
        >
          {t('setting.services.hide-logs', 'Hide logs')}
        </button>
        <button
          onClick={handleClear}
          className="flex items-center gap-1 bg-transparent text-xs text-text-tertiary hover:text-red-500"
        >
          <Trash size={10} />
          {t('setting.services.clear', 'Clear')}
        </button>
      </div>
      <div className="scrollbar max-h-48 overflow-y-auto rounded-lg bg-black/80 p-2 font-mono text-[10px] leading-4 text-green-400">
        {logs.length === 0 ? (
          <div className="text-text-tertiary">No logs</div>
        ) : (
          logs.map((log, i) => (
            <div key={i} className="whitespace-pre-wrap break-all">
              <span className="text-gray-500">
                {new Date(log.timestamp).toLocaleTimeString()}
              </span>{' '}
              <span
                className={
                  log.level === 'error'
                    ? 'text-red-400'
                    : log.level === 'warn'
                      ? 'text-amber-400'
                      : 'text-green-400'
                }
              >
                [{log.level}]
              </span>{' '}
              {log.message}
            </div>
          ))
        )}
      </div>
    </div>
  );
}

const SERVICES: {
  name: ServiceName;
  label: string;
  descriptionKey: string;
  defaultDescription: string;
  /** Whether this service can be controlled in web mode */
  webControllable: boolean;
  /** Whether this service has log streaming in web mode */
  webLogsAvailable: boolean;
}[] = [
  {
    name: 'opencode',
    label: 'OpenCode',
    descriptionKey: 'setting.services.opencode-desc',
    defaultDescription: 'AI coding agent service for developer tasks',
    webControllable: false,
    webLogsAvailable: false,
  },
  {
    name: 'openclaw',
    label: 'OpenClaw',
    descriptionKey: 'setting.services.openclaw-desc',
    defaultDescription: 'Multi-channel AI messaging gateway',
    webControllable: true,
    webLogsAvailable: true,
  },
];

export default function Services() {
  const { t } = useTranslation();
  const platform = getPlatformService();
  const isElectron = platform.isElectron;

  const [states, setStates] = useState<
    Record<ServiceName, ServiceState | null>
  >({ opencode: null, openclaw: null });

  // ── Electron: IPC-based status ───────────────────────────────────
  const fetchElectronStates = useCallback(async () => {
    if (!isElectron) return;
    const api = (window as any).electronAPI.services;
    const results = await Promise.all(
      SERVICES.map(async (s) => {
        try {
          const st = await api.getStatus(s.name);
          return [s.name, st] as const;
        } catch {
          return [s.name, null] as const;
        }
      }),
    );
    setStates(Object.fromEntries(results) as any);
  }, [isElectron]);

  useEffect(() => {
    if (!isElectron) return;
    fetchElectronStates();

    const unsub = (window as any).electronAPI.services.onStatusChange(
      (state: ServiceState) => {
        setStates((prev) => ({ ...prev, [state.name]: state }));
      },
    );
    return () => unsub?.();
  }, [fetchElectronStates, isElectron]);

  // ── Web: HTTP-based status for OpenClaw ──────────────────────────
  const fetchWebStates = useCallback(async () => {
    if (isElectron) return;
    try {
      const result = await proxyFetchGet('/api/bot/status');
      if (result) {
        setStates((prev) => ({
          ...prev,
          openclaw: {
            name: 'openclaw' as ServiceName,
            status: result.status ?? 'stopped',
            port: result.port ?? 0,
            url: '',
            restartCount: 0,
            lastError: result.lastError ?? undefined,
          },
        }));
      }
    } catch {
      setStates((prev) => ({ ...prev, openclaw: null }));
    }
  }, [isElectron]);

  useEffect(() => {
    if (isElectron) return;
    fetchWebStates();
    const id = setInterval(fetchWebStates, 5000);
    return () => clearInterval(id);
  }, [fetchWebStates, isElectron]);

  // ── Actions ──────────────────────────────────────────────────────
  const handleAction = async (
    name: ServiceName,
    action: 'start' | 'stop' | 'restart',
  ) => {
    if (isElectron) {
      const api = (window as any).electronAPI.services;
      try {
        await api[action](name);
      } catch (err) {
        console.error(`Failed to ${action} ${name}:`, err);
      }
      return;
    }

    // Web mode — only OpenClaw is controllable
    if (name !== 'openclaw') return;
    try {
      if (action === 'start') {
        await proxyFetchPost('/api/bot/start');
      } else if (action === 'stop') {
        await proxyFetchPost('/api/bot/stop');
      } else if (action === 'restart') {
        await proxyFetchPost('/api/bot/stop');
        await proxyFetchPost('/api/bot/start');
      }
      // Refresh status after action
      setTimeout(fetchWebStates, 1000);
    } catch (err) {
      console.error(`Failed to ${action} ${name}:`, err);
    }
  };

  // ── Render ───────────────────────────────────────────────────────
  return (
    <div className="flex flex-col gap-4 py-8">
      <div className="flex items-center gap-2">
        <Activity size={20} className="text-text-primary" />
        <h2 className="text-lg font-bold text-text-primary">
          {t('setting.services', 'Services')}
        </h2>
      </div>
      <p className="text-xs text-text-tertiary">
        {isElectron
          ? t(
              'setting.services.description',
              'Manage external services that power agent capabilities. Services are automatically started on launch.',
            )
          : t(
              'setting.services.web-mode-info',
              'Some services can be controlled here. Full management is available in desktop mode.',
            )}
      </p>
      <div className="flex flex-col gap-3">
        {/* Channel auto-start info */}
        <div className="rounded-lg bg-blue-50/50 dark:bg-blue-950/20 border border-blue-200/50 dark:border-blue-800/30 p-3 flex items-start gap-3">
          <Activity size={16} className="text-blue-500 mt-0.5 shrink-0" />
          <div className="text-sm">
            <span className="text-text-body">
              {t(
                'setting.services.openclawAutoStart',
                'OpenClaw starts automatically when you connect a messaging channel.',
              )}{' '}
            </span>
            <button
              onClick={() => {
                // Navigate to channels tab within settings
                const params = new URLSearchParams(window.location.search);
                params.set('settingsTab', 'channels');
                window.history.replaceState(null, '', `?${params.toString()}`);
                window.location.reload();
              }}
              className="text-blue-500 underline cursor-pointer text-sm"
            >
              {t('setting.services.manageChannels', 'Manage Channels →')}
            </button>
          </div>
        </div>
        {SERVICES.map((svc) => {
          const readOnly = !isElectron && !svc.webControllable;
          const statusOverride: ExtendedStatus | undefined =
            !isElectron && !svc.webControllable ? 'not_deployed' : undefined;
          const statusLabel =
            statusOverride === 'not_deployed'
              ? t('setting.services.not-deployed', 'Not deployed')
              : undefined;

          return (
            <div key={svc.name} className="flex flex-col gap-1">
              <ServiceCard
                name={svc.name}
                label={svc.label}
                description={
                  readOnly
                    ? t(
                        'setting.services.infrastructure-managed',
                        'Managed by deployment infrastructure',
                      )
                    : t(svc.descriptionKey, svc.defaultDescription)
                }
                state={states[svc.name]}
                readOnly={readOnly}
                statusOverride={statusOverride}
                statusLabel={statusLabel}
                onStart={() => handleAction(svc.name, 'start')}
                onStop={() => handleAction(svc.name, 'stop')}
                onRestart={() => handleAction(svc.name, 'restart')}
              />
              <ServiceLogs
                name={svc.name}
                webLogsAvailable={!isElectron && svc.webLogsAvailable}
              />
            </div>
          );
        })}
      </div>
    </div>
  );
}
