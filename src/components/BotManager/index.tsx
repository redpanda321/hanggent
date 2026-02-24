/**
 * BotManager – Web-mode UI for managing per-user OpenClaw bot instances.
 *
 * Displays bot status, start/stop controls, channel connections, and
 * a real-time event feed via WebSocket.
 *
 * In Electron mode this panel is hidden (the ExternalServices panel is
 * used instead).
 */

import * as React from 'react';
import { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { getPlatformService } from '@/service/platform';
import { useBotStatus, useBotControl, useBotChannels, type BotStatus } from '@/lib/use-bot-service';
import {
  Play,
  Square,
  RefreshCw,
  Activity,
  AlertCircle,
  CheckCircle,
  Loader2,
  MessageSquare,
  Wifi,
  WifiOff,
  Bot,
  Clock,
} from 'lucide-react';

// ── Helpers ────────────────────────────────────────────────────────────────────

function statusBadgeVariant(s: BotStatus): 'default' | 'secondary' | 'destructive' | 'outline' {
  switch (s) {
    case 'running':
      return 'default';
    case 'starting':
    case 'stopping':
      return 'secondary';
    case 'error':
      return 'destructive';
    default:
      return 'outline';
  }
}

function formatUptime(startedAt: number | null): string {
  if (!startedAt) return '—';
  const seconds = Math.floor((Date.now() - startedAt) / 1000);
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
}

// ── Sub-components ─────────────────────────────────────────────────────────────

function StatusSection({ status, startedAt, lastError, health }: {
  status: BotStatus;
  startedAt: number | null;
  lastError: string | null;
  health: { healthy: boolean; status: string } | null;
}) {
  return (
    <div className="grid grid-cols-3 gap-4 text-sm">
      <div className="space-y-1">
        <p className="text-muted-foreground flex items-center gap-1">
          <Clock className="h-3.5 w-3.5" /> Uptime
        </p>
        <p className="font-medium">{formatUptime(startedAt)}</p>
      </div>
      <div className="space-y-1">
        <p className="text-muted-foreground flex items-center gap-1">
          <Activity className="h-3.5 w-3.5" /> Status
        </p>
        <p className="font-medium capitalize">{status}</p>
      </div>
      <div className="space-y-1">
        <p className="text-muted-foreground flex items-center gap-1">Health</p>
        <div className="flex items-center gap-1">
          {health?.healthy ? (
            <>
              <CheckCircle className="h-4 w-4 text-green-500" />
              <span className="font-medium text-green-500">OK</span>
            </>
          ) : (
            <>
              <AlertCircle className="h-4 w-4 text-yellow-500" />
              <span className="font-medium text-yellow-500">
                {status === 'stopped' ? 'Offline' : 'Unknown'}
              </span>
            </>
          )}
        </div>
      </div>
      {lastError && (
        <div className="col-span-3 p-3 rounded-lg bg-destructive/10 border border-destructive/20">
          <div className="flex items-start gap-2">
            <AlertCircle className="h-4 w-4 text-destructive mt-0.5 shrink-0" />
            <p className="text-sm text-destructive">{lastError}</p>
          </div>
        </div>
      )}
    </div>
  );
}

function ChannelList() {
  const { channels, loading } = useBotChannels();

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-muted-foreground text-sm">
        <Loader2 className="h-4 w-4 animate-spin" />
        Loading channels…
      </div>
    );
  }

  if (channels.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No channels connected. Start the bot and configure channels in OpenClaw.
      </p>
    );
  }

  return (
    <ul className="space-y-2">
      {channels.map((ch) => (
        <li
          key={ch.name}
          className="flex items-center justify-between rounded-md border px-3 py-2 text-sm"
        >
          <div className="flex items-center gap-2">
            {ch.connected ? (
              <Wifi className="h-4 w-4 text-green-500" />
            ) : (
              <WifiOff className="h-4 w-4 text-gray-400" />
            )}
            <span className="font-medium">{ch.name}</span>
            <span className="text-muted-foreground">({ch.type})</span>
          </div>
          <Badge variant={ch.connected ? 'default' : 'outline'} className="text-xs">
            {ch.connected ? 'Connected' : 'Disconnected'}
          </Badge>
        </li>
      ))}
    </ul>
  );
}

// ── Main component ─────────────────────────────────────────────────────────────

export function BotManager() {
  const { state, loading, isRunning, isStarting, isStopped } = useBotStatus({ refreshInterval: 5000 });
  const { start, stop, loading: actionLoading, error: actionError } = useBotControl();
  const [showChannels, setShowChannels] = useState(false);

  const isElectron = getPlatformService().isElectron;

  // In Electron mode, fall back to ExternalServices panel
  if (isElectron) return null;

  if (loading) {
    return (
      <div className="p-4 flex items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const isTransitioning = isStarting || state.status === 'stopping';

  return (
    <div className="space-y-4 p-4">
      <div className="space-y-1">
        <h3 className="text-lg font-semibold flex items-center gap-2">
          <Bot className="h-5 w-5" /> Bot Manager
        </h3>
        <p className="text-sm text-muted-foreground">
          Manage your personal OpenClaw messaging bot
        </p>
      </div>

      {/* Main status card */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-muted">
                <MessageSquare className="h-5 w-5" />
              </div>
              <div>
                <CardTitle className="text-lg">OpenClaw</CardTitle>
                <CardDescription>Multi-channel messaging gateway</CardDescription>
              </div>
            </div>
            <Badge variant={statusBadgeVariant(state.status)}>
              {state.status}
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Status details (visible when not stopped) */}
          {!isStopped && (
            <StatusSection
              status={state.status}
              startedAt={state.startedAt}
              lastError={state.lastError}
              health={state.health}
            />
          )}

          {/* Action error */}
          {actionError && (
            <div className="p-3 rounded-lg bg-destructive/10 border border-destructive/20">
              <div className="flex items-start gap-2">
                <AlertCircle className="h-4 w-4 text-destructive mt-0.5 shrink-0" />
                <p className="text-sm text-destructive">{actionError}</p>
              </div>
            </div>
          )}

          {/* Action buttons */}
          <div className="flex gap-2">
            {!isRunning ? (
              <Button
                size="sm"
                onClick={start}
                disabled={actionLoading || isTransitioning}
                className="flex-1"
              >
                {actionLoading || isTransitioning ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <Play className="h-4 w-4 mr-2" />
                )}
                Start Bot
              </Button>
            ) : (
              <>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={stop}
                  disabled={actionLoading || isTransitioning}
                  className="flex-1"
                >
                  {actionLoading ? (
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  ) : (
                    <Square className="h-4 w-4 mr-2" />
                  )}
                  Stop
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={async () => {
                    await stop();
                    // Wait for status to become stopped before restarting
                    const poll = setInterval(async () => {
                      try {
                        const s = await import('@/api/http').then(m => m.proxyFetchGet('/api/bot/status'));
                        if (!s || s.status === 'stopped' || s.status === 'error') {
                          clearInterval(poll);
                          start();
                        }
                      } catch {
                        clearInterval(poll);
                        start();
                      }
                    }, 500);
                    // Safety timeout
                    setTimeout(() => clearInterval(poll), 10000);
                  }}
                  disabled={actionLoading || isTransitioning}
                >
                  <RefreshCw className={cn('h-4 w-4', actionLoading && 'animate-spin')} />
                </Button>
              </>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Channels section (collapsible) */}
      {isRunning && (
        <Card>
          <CardHeader
            className="pb-3 cursor-pointer select-none"
            onClick={() => setShowChannels((v) => !v)}
          >
            <div className="flex items-center justify-between">
              <CardTitle className="text-base flex items-center gap-2">
                <Wifi className="h-4 w-4" /> Channels
              </CardTitle>
              <span className="text-xs text-muted-foreground">
                {showChannels ? 'Hide' : 'Show'}
              </span>
            </div>
          </CardHeader>
          {showChannels && (
            <CardContent>
              <ChannelList />
            </CardContent>
          )}
        </Card>
      )}

      {/* Footer hint */}
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Activity className="h-4 w-4" />
        <span>Your bot runs in the cloud and stays active while the instance is running</span>
      </div>
    </div>
  );
}

export default BotManager;
