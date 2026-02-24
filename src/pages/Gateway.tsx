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
import { useBotControl, useBotStatus } from '@/lib/use-bot-service';
import { useAuthStore } from '@/store/authStore';
import { Loader2, Play, Radio, RefreshCw } from 'lucide-react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

/**
 * Gateway page — embeds the full OpenClaw Control UI inside an iframe.
 *
 * The iframe loads via the server's `/api/bot/ui/` raw-proxy endpoint
 * which strips X-Frame-Options / CSP headers so embedding works.
 *
 * Authentication is forwarded via:
 *   - `?token=<gateway_token>` — auto-applied by the OpenClaw UI
 *   - `?gatewayUrl=<ws_url>` — tells the OpenClaw UI where its WS is
 *
 * The OpenClaw UI has its own sidebar with all 13 tabs (chat, overview,
 * channels, instances, sessions, usage, cron, agents, skills, nodes,
 * config, debug, logs) so we don't need to duplicate navigation.
 */
export default function Gateway() {
  const { t } = useTranslation();
  const token = useAuthStore((s) => s.token);
  const { state: botState, loading, refresh, isRunning, isStarting } = useBotStatus({
    refreshInterval: 5000,
  });
  const { start, loading: actionLoading } = useBotControl();
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [iframeLoaded, setIframeLoaded] = useState(false);
  const [iframeError, setIframeError] = useState(false);

  // Build the iframe src URL
  const iframeSrc = useMemo(() => {
    if (!isRunning || !token) return null;

    // The WS endpoint for the OpenClaw UI to connect to its gateway.
    // In production: wss://www.hanggent.com/api/bot/ws?token=...
    // In dev: ws://localhost:3001/api/bot/ws?token=...
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//${window.location.host}/api/bot/ws?token=${encodeURIComponent(token)}`;

    // The UI is served at /api/bot/ui/ via the raw proxy.
    // Pass token + gatewayUrl as query params — the OpenClaw UI auto-applies
    // and strips them from the URL.
    const params = new URLSearchParams({
      token,
      gatewayUrl: wsUrl,
    });

    return `/api/bot/ui/overview?${params.toString()}`;
  }, [isRunning, token]);

  // Handle start gateway
  const handleStart = useCallback(async () => {
    await start();
    // Refresh status after a short delay
    setTimeout(refresh, 1500);
  }, [start, refresh]);

  // Reset iframe state when src changes
  useEffect(() => {
    setIframeLoaded(false);
    setIframeError(false);
  }, [iframeSrc]);

  // Loading state
  if (loading) {
    return (
      <div className="flex h-full w-full items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-text-tertiary" />
      </div>
    );
  }

  // Gateway not running — show start prompt
  if (!isRunning) {
    return (
      <div className="flex h-full w-full flex-col items-center justify-center gap-4">
        <div className="flex flex-col items-center gap-2">
          <Radio className="h-10 w-10 text-text-quaternary" />
          <h2 className="text-lg font-semibold text-text-primary">
            {t('gateway.title', 'AI Gateway')}
          </h2>
          <p className="max-w-md text-center text-sm text-text-tertiary">
            {t(
              'gateway.description',
              'Start your personal AI gateway to manage channels, agents, sessions, and more.'
            )}
          </p>
        </div>

        {botState.lastError && (
          <div className="max-w-md rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-600">
            {botState.lastError}
          </div>
        )}

        <Button
          onClick={handleStart}
          disabled={actionLoading || isStarting}
          size="lg"
          className="gap-2"
        >
          {actionLoading || isStarting ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Play className="h-4 w-4" />
          )}
          {isStarting
            ? t('gateway.starting', 'Starting...')
            : t('gateway.start', 'Start Gateway')}
        </Button>
      </div>
    );
  }

  // Gateway running — show iframe
  return (
    <div className="relative h-full w-full">
      {/* Loading overlay while iframe loads */}
      {!iframeLoaded && !iframeError && (
        <div className="absolute inset-0 z-10 flex items-center justify-center bg-background">
          <div className="flex flex-col items-center gap-2">
            <Loader2 className="h-6 w-6 animate-spin text-text-tertiary" />
            <span className="text-sm text-text-tertiary">
              {t('gateway.loading', 'Loading Control UI...')}
            </span>
          </div>
        </div>
      )}

      {/* Error state */}
      {iframeError && (
        <div className="absolute inset-0 z-10 flex flex-col items-center justify-center gap-3 bg-background">
          <p className="text-sm text-text-tertiary">
            {t('gateway.load-error', 'Failed to load Control UI')}
          </p>
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setIframeError(false);
              setIframeLoaded(false);
              if (iframeRef.current && iframeSrc) {
                iframeRef.current.src = iframeSrc;
              }
            }}
            className="gap-1"
          >
            <RefreshCw className="h-3 w-3" />
            {t('gateway.retry', 'Retry')}
          </Button>
        </div>
      )}

      {iframeSrc && (
        <iframe
          ref={iframeRef}
          src={iframeSrc}
          className="h-full w-full border-0"
          title="OpenClaw Control UI"
          sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-modals allow-top-navigation-by-user-activation"
          onLoad={() => setIframeLoaded(true)}
          onError={() => setIframeError(true)}
        />
      )}
    </div>
  );
}
