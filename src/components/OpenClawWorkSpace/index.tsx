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

import Terminal from '@/components/Terminal';
import useChatStoreAdapter from '@/hooks/useChatStoreAdapter';
import { useBotWebSocket } from '@/lib/use-bot-service';
import { proxyFetchGet } from '@/api/http';
import {
  ChevronLeft,
  Globe,
  MessageSquare,
  Radio,
  Settings2,
  TerminalSquare,
} from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '../ui/button';

type TabId = 'dashboard' | 'control' | 'messages' | 'terminal';

interface ChannelStatus {
  name: string;
  channel: string;
  status: 'connected' | 'disconnected' | 'error' | string;
  messageCount?: number;
}

interface MessageEntry {
  id: string;
  direction: 'inbound' | 'outbound';
  channel: string;
  from: string;
  to: string;
  text: string;
  timestamp: string;
  status: string;
}

export default function OpenClawWorkSpace() {
  const { chatStore } = useChatStoreAdapter();
  const { t } = useTranslation();
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const [activeTab, setActiveTab] = useState<TabId>('dashboard');
  const [channels, setChannels] = useState<ChannelStatus[]>([]);
  const [loading, setLoading] = useState(false);
  const [gatewayAvailable, setGatewayAvailable] = useState<boolean | null>(
    null
  );

  // Wire up WebSocket for live messages
  const { messages: wsMessages, connect: wsConnect, connected: wsConnected } = useBotWebSocket({
    autoConnect: true,
    reconnectDelay: 5000,
    maxReconnects: 10,
  });

  // Map WS messages to MessageEntry format (keep last 500)
  const messages = useMemo<MessageEntry[]>(() => {
    return wsMessages
      .filter((m) => m.type === 'message' || m.direction)
      .slice(-500)
      .map((m, i) => ({
        id: m.id || `ws-${i}`,
        direction: m.direction || 'inbound',
        channel: m.channel || '',
        from: m.from || '',
        to: m.to || '',
        text: m.text || m.content || JSON.stringify(m),
        timestamp: m.timestamp || new Date().toISOString(),
        status: m.status || 'delivered',
      }));
  }, [wsMessages]);

  const activeTaskId = chatStore?.activeTaskId;
  const taskAssigning = chatStore?.tasks[activeTaskId as string]?.taskAssigning;
  const activeWorkSpace =
    chatStore?.tasks[activeTaskId as string]?.activeWorkSpace;

  const activeAgent = useMemo(() => {
    if (!chatStore || !taskAssigning) return null;
    return (
      taskAssigning.find((item) => item.agent_id === activeWorkSpace) || null
    );
  }, [chatStore, taskAssigning, activeWorkSpace]);

  // Fetch gateway health on mount via authenticated API
  useEffect(() => {
    const checkHealth = async () => {
      try {
        const data = await proxyFetchGet('/api/bot/status');
        setGatewayAvailable(data?.status === 'running');
      } catch {
        setGatewayAvailable(false);
      }
    };
    checkHealth();
    const interval = setInterval(checkHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  // Fetch channels when dashboard tab is active
  useEffect(() => {
    if (activeTab !== 'dashboard') return;
    const fetchChannels = async () => {
      setLoading(true);
      try {
        const data = await proxyFetchGet('/api/bot/channels');
        if (data) {
          const list = Array.isArray(data) ? data : (data?.channels ?? []);
          setChannels(list);
        }
      } catch {
        // Gateway may not be available
      } finally {
        setLoading(false);
      }
    };
    fetchChannels();
  }, [activeTab]);

  if (!chatStore) {
    return <div>{t('common.loading', 'Loading...')}</div>;
  }

  // Collect terminal content from agent tasks
  const terminalTasks =
    activeAgent?.tasks.filter(
      (task) => task?.terminal && task.terminal.length > 0
    ) ?? [];

  const tabs: {
    id: TabId;
    label: string;
    icon: React.ReactNode;
    count?: number;
  }[] = [
    {
      id: 'dashboard',
      label: t('workspace.dashboard', 'Dashboard'),
      icon: <Radio size={14} />,
      count: channels.filter((c) => c.status === 'connected').length,
    },
    {
      id: 'control',
      label: t('workspace.control-ui', 'Control UI'),
      icon: <Globe size={14} />,
    },
    {
      id: 'messages',
      label: t('workspace.messages', 'Messages'),
      icon: <MessageSquare size={14} />,
      count: messages.length,
    },
    {
      id: 'terminal',
      label: t('workspace.terminal', 'Terminal'),
      icon: <TerminalSquare size={14} />,
      count: terminalTasks.length,
    },
  ];

  return (
    <div className="flex h-[calc(100vh-104px)] w-full flex-1 items-center justify-center transition-all duration-300 ease-in-out">
      <div className="relative flex h-full w-full flex-col overflow-hidden rounded-2xl bg-menutabs-bg-default">
        {/* Header */}
        <div className="flex flex-shrink-0 items-center justify-between rounded-t-2xl px-2 pb-2 pt-3">
          <div className="flex items-center justify-start gap-sm">
            <Button
              size="icon"
              variant="ghost"
              onClick={() => {
                chatStore.setActiveWorkSpace(
                  chatStore.activeTaskId as string,
                  'workflow'
                );
              }}
            >
              <ChevronLeft size={16} />
            </Button>
            <div className="flex h-[26px] items-center gap-xs rounded-lg bg-violet-200 px-2 py-0.5">
              <Bot className="h-4 w-4 text-icon-primary" />
              <MessageSquare className="h-3 w-3 text-violet-700" />
              <div className="text-[10px] font-bold leading-17 text-violet-700">
                {t('workspace.openclaw-agent', 'OpenClaw Agent')}
              </div>
            </div>
            {/* Gateway status indicator */}
            <div className="flex items-center gap-1">
              <div
                className={`h-2 w-2 rounded-full ${
                  gatewayAvailable === true
                    ? 'bg-emerald-500'
                    : gatewayAvailable === false
                      ? 'bg-red-500'
                      : 'bg-gray-400'
                }`}
              />
              <span className="text-[10px] text-text-tertiary">
                {gatewayAvailable === true
                  ? t('workspace.connected', 'Connected')
                  : gatewayAvailable === false
                    ? t('workspace.offline', 'Offline')
                    : t('workspace.checking', 'Checking...')}
              </span>
            </div>
          </div>
          <div className="flex items-center gap-1">
            {/* Tab switcher */}
            <div className="flex items-center gap-0.5 rounded-lg border border-solid border-border-primary bg-transparent p-0.5">
              {tabs.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center gap-1 rounded-md px-2 py-1 text-[10px] font-medium transition-colors ${
                    activeTab === tab.id
                      ? 'bg-bg-fill-primary text-text-inverse-primary'
                      : 'text-text-tertiary hover:text-text-primary'
                  }`}
                >
                  {tab.icon}
                  {tab.label}
                  {tab.count !== undefined && tab.count > 0 && (
                    <span className="ml-0.5 rounded-full bg-violet-100 px-1 text-[9px] text-violet-700">
                      {tab.count}
                    </span>
                  )}
                </button>
              ))}
            </div>
            <Button size="icon" variant="ghost">
              <Settings2 size={16} />
            </Button>
          </div>
        </div>

        {/* Content area */}
        <div className="min-h-0 flex-1">
          {/* Dashboard tab — Channel status cards */}
          {activeTab === 'dashboard' && (
            <div className="scrollbar flex h-full flex-col gap-2 overflow-y-auto p-3">
              {loading ? (
                <div className="flex h-full items-center justify-center text-sm text-text-tertiary">
                  {t('workspace.loading-channels', 'Loading channels...')}
                </div>
              ) : channels.length === 0 ? (
                <div className="flex h-full flex-col items-center justify-center gap-2 text-sm text-text-tertiary">
                  <Radio size={24} className="text-text-quaternary" />
                  <p>
                    {gatewayAvailable
                      ? t(
                          'workspace.no-channels',
                          'No channels configured yet'
                        )
                      : t(
                          'workspace.gateway-offline',
                          'Gateway is offline — start OpenClaw to see channels'
                        )}
                  </p>
                </div>
              ) : (
                <div className="grid grid-cols-2 gap-2 lg:grid-cols-3">
                  {channels.map((ch) => (
                    <div
                      key={ch.name || ch.channel}
                      className="flex items-center gap-3 rounded-xl border border-solid border-border-primary bg-surface-secondary p-3"
                    >
                      <div
                        className={`h-3 w-3 rounded-full ${
                          ch.status === 'connected'
                            ? 'bg-emerald-500'
                            : ch.status === 'error'
                              ? 'bg-red-500'
                              : 'bg-gray-400'
                        }`}
                      />
                      <div className="min-w-0 flex-1">
                        <div className="truncate text-xs font-medium text-text-primary">
                          {ch.name || ch.channel}
                        </div>
                        <div className="text-[10px] text-text-tertiary">
                          {ch.status}
                          {ch.messageCount !== undefined &&
                            ` · ${ch.messageCount} msgs`}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Control UI tab — iframe */}
          {activeTab === 'control' && (
            <div className="h-full w-full">
              {gatewayAvailable ? (
                <iframe
                  src="/api/bot/ui/"
                  className="h-full w-full rounded-b-2xl border-0"
                  title={t('workspace.control-ui', 'OpenClaw Control UI')}
                  sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-modals"
                />
              ) : (
                <div className="flex h-full items-center justify-center text-sm text-text-tertiary">
                  {t(
                    'workspace.control-unavailable',
                    'Control UI unavailable — gateway is offline'
                  )}
                </div>
              )}
            </div>
          )}

          {/* Messages tab */}
          {activeTab === 'messages' && (
            <div className="scrollbar flex h-full flex-col gap-1 overflow-y-auto p-2">
              {messages.length === 0 ? (
                <div className="flex h-full flex-col items-center justify-center gap-2 text-sm text-text-tertiary">
                  <MessageSquare
                    size={24}
                    className="text-text-quaternary"
                  />
                  <p>
                    {t('workspace.no-messages', 'No messages yet')}
                  </p>
                </div>
              ) : (
                messages.map((msg, idx) => (
                  <div
                    key={msg.id || idx}
                    className={`flex items-start gap-2 rounded-lg border border-solid p-2 ${
                      msg.direction === 'outbound'
                        ? 'border-violet-200 bg-violet-50'
                        : 'border-border-primary bg-surface-secondary'
                    }`}
                  >
                    <div
                      className={`mt-0.5 text-[10px] font-bold ${
                        msg.direction === 'outbound'
                          ? 'text-violet-600'
                          : 'text-emerald-600'
                      }`}
                    >
                      {msg.direction === 'outbound' ? '↑' : '↓'}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] font-medium text-text-primary">
                          {msg.direction === 'outbound'
                            ? `→ ${msg.to}`
                            : `← ${msg.from}`}
                        </span>
                        <span className="rounded bg-gray-100 px-1 text-[9px] text-gray-500">
                          {msg.channel}
                        </span>
                      </div>
                      <div className="mt-0.5 text-xs text-text-secondary">
                        {msg.text}
                      </div>
                      <div className="mt-0.5 text-[9px] text-text-quaternary">
                        {msg.timestamp}
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          )}

          {/* Terminal tab */}
          {activeTab === 'terminal' && (
            <>
              {terminalTasks.length === 0 ? (
                <div className="flex h-full w-full items-center justify-center text-sm text-text-tertiary">
                  {t(
                    'workspace.no-terminal',
                    'No terminal output yet — OpenClaw agent is getting started...'
                  )}
                </div>
              ) : terminalTasks.length === 1 ? (
                <div className="h-full w-full rounded-b-2xl pt-sm">
                  <Terminal
                    instanceId={activeAgent?.activeWebviewIds?.[0]?.id}
                    content={terminalTasks[0].terminal}
                  />
                </div>
              ) : (
                <div
                  ref={scrollContainerRef}
                  className="scrollbar relative flex min-h-0 flex-1 flex-wrap justify-start gap-4 overflow-y-auto px-2 pb-2"
                >
                  {terminalTasks.map((task) => (
                    <div
                      key={task.id}
                      className="group relative h-[calc(50%-8px)] w-[calc(50%-8px)] cursor-pointer rounded-lg"
                    >
                      <Terminal instanceId={task.id} content={task.terminal} />
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
