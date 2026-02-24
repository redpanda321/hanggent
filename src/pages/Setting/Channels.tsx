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

import { useState, useEffect, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import {
  AlertCircle,
  Check,
  Copy,
  ExternalLink,
  Globe,
  Key,
  Link2,
  LinkIcon,
  Loader2,
  MessageCircle,
  MessageSquare,
  Phone,
  Plug,
  PlugZap,
  Send,
  Unplug,
} from 'lucide-react';
import { proxyFetchGet, proxyFetchPost } from '@/api/http';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';

// ── Channel Definitions ────────────────────────────────────────────────────────

interface ChannelDef {
  id: string;
  name: string;
  description: string;
  icon: React.ComponentType<any>;
  color: string;
  modes: ('shared' | 'own')[];
  requiresToken: boolean;
  tokenFields: { key: string; label: string; placeholder: string; secret?: boolean }[];
}

const CHANNELS: ChannelDef[] = [
  {
    id: 'telegram',
    name: 'Telegram',
    description: 'Connect via Telegram Bot — use the shared Hanggent bot or bring your own.',
    icon: Send,
    color: 'bg-blue-500',
    modes: ['shared', 'own'],
    requiresToken: false, // shared mode doesn't
    tokenFields: [
      { key: 'botToken', label: 'Bot Token', placeholder: 'Enter your Telegram bot token from @BotFather', secret: true },
    ],
  },
  {
    id: 'discord',
    name: 'Discord',
    description: 'Connect via a Discord bot — bring your own bot token.',
    icon: MessageCircle,
    color: 'bg-indigo-500',
    modes: ['own'],
    requiresToken: true,
    tokenFields: [
      { key: 'botToken', label: 'Bot Token', placeholder: 'Enter your Discord bot token', secret: true },
    ],
  },
  {
    id: 'slack',
    name: 'Slack',
    description: 'Connect via a Slack app — bring your own bot credentials.',
    icon: MessageSquare,
    color: 'bg-purple-500',
    modes: ['own'],
    requiresToken: true,
    tokenFields: [
      { key: 'botToken', label: 'Bot Token', placeholder: 'xoxb-...', secret: true },
      { key: 'signingSecret', label: 'Signing Secret', placeholder: 'Enter your Slack signing secret', secret: true },
      { key: 'appToken', label: 'App Token (Socket Mode)', placeholder: 'xapp-... (optional)', secret: true },
    ],
  },
  {
    id: 'whatsapp',
    name: 'WhatsApp',
    description: 'Connect via WhatsApp Web — pair by scanning a QR code.',
    icon: Phone,
    color: 'bg-green-500',
    modes: ['own'],
    requiresToken: false,
    tokenFields: [],
  },
  {
    id: 'webchat',
    name: 'Web Chat',
    description: 'Built-in web chat — always available when your bot is running. No configuration needed.',
    icon: Globe,
    color: 'bg-teal-500',
    modes: ['own'],
    requiresToken: false,
    tokenFields: [],
  },
];

// ── Types ──────────────────────────────────────────────────────────────────────

interface ChannelConfig {
  mode?: string;
  botToken?: string;
  signingSecret?: string;
  appToken?: string;
  chatId?: number;
  enabled?: boolean;
  [key: string]: any;
}

interface ChannelsState {
  channels: Record<string, ChannelConfig>;
  bot_status: string;
}

// ── Component ──────────────────────────────────────────────────────────────────

export default function Channels() {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(true);
  const [channelsState, setChannelsState] = useState<ChannelsState>({
    channels: {},
    bot_status: 'stopped',
  });
  const [expandedChannel, setExpandedChannel] = useState<string | null>(null);
  const [connecting, setConnecting] = useState<string | null>(null);
  const [disconnecting, setDisconnecting] = useState<string | null>(null);

  // Per-channel form state
  const [formData, setFormData] = useState<Record<string, Record<string, string>>>({});
  const [selectedMode, setSelectedMode] = useState<Record<string, 'shared' | 'own'>>({});

  // Telegram linking
  const [linkingCode, setLinkingCode] = useState<string | null>(null);
  const [linkingExpiry, setLinkingExpiry] = useState<string | null>(null);
  const [generatingCode, setGeneratingCode] = useState(false);

  const loadChannelConfig = useCallback(async () => {
    setLoading(true);
    try {
      const res = await proxyFetchGet('/api/bot/channels/config');
      setChannelsState(res as ChannelsState);
    } catch (e) {
      console.error('Failed to load channel config:', e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadChannelConfig();
  }, [loadChannelConfig]);

  const isChannelConnected = (channelId: string): boolean => {
    return !!channelsState.channels[channelId];
  };

  const getChannelStatus = (channelId: string): string => {
    if (!isChannelConnected(channelId)) return 'disconnected';
    if (channelsState.bot_status === 'running') return 'connected';
    if (channelsState.bot_status === 'starting') return 'starting';
    return 'configured';
  };

  const handleConnect = async (channelId: string) => {
    const def = CHANNELS.find((c) => c.id === channelId);
    if (!def) return;

    const mode = selectedMode[channelId] || def.modes[0];
    const form = formData[channelId] || {};

    // Validate required tokens for "own" mode
    if (mode === 'own' && def.requiresToken) {
      const missingFields = def.tokenFields.filter(
        (f) => !f.key.includes('optional') && !form[f.key]
      );
      // Only first field is truly required for most channels
      if (!form[def.tokenFields[0]?.key]) {
        toast.error(`Please enter the ${def.tokenFields[0]?.label}`);
        return;
      }
    }

    setConnecting(channelId);
    try {
      const config: Record<string, any> = { mode };
      if (mode === 'own') {
        Object.entries(form).forEach(([k, v]) => {
          if (v) config[k] = v;
        });
      }
      if (channelId === 'whatsapp') {
        config.enabled = true;
      }

      await proxyFetchPost('/api/bot/channels/connect', { channel: channelId, config });
      toast.success(`${def.name} connected successfully`);
      await loadChannelConfig();
      setExpandedChannel(null);
    } catch (e: any) {
      toast.error(`Failed to connect ${def.name}: ${e?.message || e}`);
    } finally {
      setConnecting(null);
    }
  };

  const handleDisconnect = async (channelId: string) => {
    const def = CHANNELS.find((c) => c.id === channelId);
    if (!def) return;

    setDisconnecting(channelId);
    try {
      await proxyFetchPost('/api/bot/channels/disconnect', { channel: channelId });
      toast.success(`${def.name} disconnected`);
      await loadChannelConfig();
    } catch (e: any) {
      toast.error(`Failed to disconnect ${def.name}`);
    } finally {
      setDisconnecting(null);
    }
  };

  const handleGenerateLinkCode = async () => {
    setGeneratingCode(true);
    try {
      const res = (await proxyFetchPost('/api/bot/channels/telegram/link-code', {})) as any;
      setLinkingCode(res.code);
      setLinkingExpiry(res.expires_at);
      toast.success('Linking code generated! Send it to @HanggentBot on Telegram.');
    } catch (e: any) {
      toast.error('Failed to generate linking code');
    } finally {
      setGeneratingCode(false);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    toast.success('Copied to clipboard');
  };

  // ── Render ─────────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="m-auto flex h-auto w-full flex-1 flex-col">
      {/* Header */}
      <div className="sticky top-0 z-10 flex w-full items-center justify-between bg-surface-primary px-6 pb-4 pt-8">
        <div className="flex flex-col">
          <h2 className="text-heading-sm font-bold text-text-heading">
            {t('setting.channels', 'Messaging Channels')}
          </h2>
          <p className="text-body-sm text-text-body mt-1">
            {t(
              'setting.channelsDescription',
              'Connect your AI assistant to messaging platforms like Telegram, Discord, Slack, and WhatsApp.'
            )}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge
            variant={channelsState.bot_status === 'running' ? 'default' : 'secondary'}
            className={
              channelsState.bot_status === 'running'
                ? 'bg-emerald-500/10 text-emerald-600 border-emerald-500/20'
                : ''
            }
          >
            {channelsState.bot_status === 'running' ? '● Running' : channelsState.bot_status}
          </Badge>
        </div>
      </div>

      {/* Channel Cards */}
      <div className="flex flex-col gap-4 px-6 pb-8">
        {CHANNELS.map((channel) => {
          const connected = isChannelConnected(channel.id);
          const status = getChannelStatus(channel.id);
          const isExpanded = expandedChannel === channel.id;
          const mode = selectedMode[channel.id] || channel.modes[0];
          const Icon = channel.icon;

          return (
            <Card
              key={channel.id}
              className={`transition-all ${
                connected
                  ? 'border-emerald-500/30 bg-emerald-50/5'
                  : 'hover:border-border/80'
              }`}
            >
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div
                      className={`flex h-10 w-10 items-center justify-center rounded-lg ${channel.color} text-white`}
                    >
                      <Icon className="h-5 w-5" />
                    </div>
                    <div>
                      <CardTitle className="text-base flex items-center gap-2">
                        {channel.name}
                        {connected && (
                          <Badge
                            variant="outline"
                            className="text-xs bg-emerald-500/10 text-emerald-600 border-emerald-500/20"
                          >
                            <Check className="h-3 w-3 mr-1" />
                            {status === 'connected' ? 'Connected' : status}
                          </Badge>
                        )}
                        {connected && channelsState.channels[channel.id]?.mode && (
                          <Badge variant="outline" className="text-xs">
                            {channelsState.channels[channel.id].mode === 'shared'
                              ? 'Shared Bot'
                              : 'Own Bot'}
                          </Badge>
                        )}
                      </CardTitle>
                      <CardDescription className="text-sm mt-0.5">
                        {channel.description}
                      </CardDescription>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {connected ? (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleDisconnect(channel.id)}
                        disabled={disconnecting === channel.id}
                        className="text-red-500 hover:text-red-600"
                      >
                        {disconnecting === channel.id ? (
                          <Loader2 className="h-4 w-4 animate-spin mr-1" />
                        ) : (
                          <Unplug className="h-4 w-4 mr-1" />
                        )}
                        Disconnect
                      </Button>
                    ) : channel.id === 'webchat' ? (
                      <Badge variant="secondary">Always Available</Badge>
                    ) : (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() =>
                          setExpandedChannel(isExpanded ? null : channel.id)
                        }
                      >
                        <Plug className="h-4 w-4 mr-1" />
                        {isExpanded ? 'Cancel' : 'Connect'}
                      </Button>
                    )}
                  </div>
                </div>
              </CardHeader>

              {/* Expanded Configuration Form */}
              {isExpanded && !connected && channel.id !== 'webchat' && (
                <CardContent className="pt-0">
                  <Separator className="mb-4" />

                  {/* Mode Selection (for channels that support both) */}
                  {channel.modes.length > 1 && (
                    <div className="mb-4">
                      <Label className="text-sm font-medium mb-2 block">
                        Connection Mode
                      </Label>
                      <div className="flex gap-3">
                        {channel.modes.includes('shared') && (
                          <button
                            onClick={() =>
                              setSelectedMode((s) => ({
                                ...s,
                                [channel.id]: 'shared',
                              }))
                            }
                            className={`flex-1 rounded-lg border-2 p-3 text-left transition-all ${
                              mode === 'shared'
                                ? 'border-primary bg-primary/5'
                                : 'border-border hover:border-border/80'
                            }`}
                          >
                            <div className="flex items-center gap-2 mb-1">
                              <LinkIcon className="h-4 w-4" />
                              <span className="font-medium text-sm">
                                Use Hanggent Bot
                              </span>
                              <Badge variant="secondary" className="text-xs">
                                Easy
                              </Badge>
                            </div>
                            <p className="text-xs text-muted-foreground">
                              Link your account to the shared @HanggentBot — no
                              setup needed.
                            </p>
                          </button>
                        )}
                        {channel.modes.includes('own') && (
                          <button
                            onClick={() =>
                              setSelectedMode((s) => ({
                                ...s,
                                [channel.id]: 'own',
                              }))
                            }
                            className={`flex-1 rounded-lg border-2 p-3 text-left transition-all ${
                              mode === 'own'
                                ? 'border-primary bg-primary/5'
                                : 'border-border hover:border-border/80'
                            }`}
                          >
                            <div className="flex items-center gap-2 mb-1">
                              <Key className="h-4 w-4" />
                              <span className="font-medium text-sm">
                                Bring Your Own Bot
                              </span>
                              <Badge variant="secondary" className="text-xs">
                                Advanced
                              </Badge>
                            </div>
                            <p className="text-xs text-muted-foreground">
                              Use your own bot token from @BotFather for full
                              control.
                            </p>
                          </button>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Shared Mode — Telegram Linking Flow */}
                  {channel.id === 'telegram' && mode === 'shared' && (
                    <div className="space-y-4">
                      <div className="rounded-lg bg-blue-50/50 dark:bg-blue-950/20 border border-blue-200/50 dark:border-blue-800/30 p-4">
                        <h4 className="font-medium text-sm mb-2 flex items-center gap-2">
                          <Link2 className="h-4 w-4 text-blue-500" />
                          Link your Telegram account
                        </h4>
                        <ol className="text-sm text-muted-foreground space-y-1.5 list-decimal list-inside">
                          <li>Click "Generate Linking Code" below</li>
                          <li>
                            Open{' '}
                            <a
                              href="https://t.me/HanggentBot"
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-blue-500 underline inline-flex items-center gap-1"
                            >
                              @HanggentBot
                              <ExternalLink className="h-3 w-3" />
                            </a>{' '}
                            on Telegram
                          </li>
                          <li>
                            Send <code className="bg-muted px-1 rounded">/link YOUR_CODE</code> to
                            the bot
                          </li>
                        </ol>
                      </div>

                      {linkingCode ? (
                        <div className="flex items-center gap-3 p-3 rounded-lg bg-muted/50">
                          <div className="flex-1">
                            <Label className="text-xs text-muted-foreground">
                              Your linking code (expires in 5 min)
                            </Label>
                            <div className="flex items-center gap-2 mt-1">
                              <code className="text-2xl font-mono font-bold tracking-widest">
                                {linkingCode}
                              </code>
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() =>
                                  copyToClipboard(`/link ${linkingCode}`)
                                }
                              >
                                <Copy className="h-4 w-4" />
                              </Button>
                            </div>
                          </div>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={handleGenerateLinkCode}
                            disabled={generatingCode}
                          >
                            {generatingCode ? (
                              <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                              'New Code'
                            )}
                          </Button>
                        </div>
                      ) : (
                        <Button
                          onClick={handleGenerateLinkCode}
                          disabled={generatingCode}
                        >
                          {generatingCode ? (
                            <Loader2 className="h-4 w-4 animate-spin mr-2" />
                          ) : (
                            <PlugZap className="h-4 w-4 mr-2" />
                          )}
                          Generate Linking Code
                        </Button>
                      )}
                    </div>
                  )}

                  {/* Own Mode — Token Input Fields */}
                  {mode === 'own' && channel.tokenFields.length > 0 && (
                    <div className="space-y-3">
                      {channel.tokenFields.map((field) => (
                        <div key={field.key}>
                          <Label className="text-sm">{field.label}</Label>
                          <Input
                            type={field.secret ? 'password' : 'text'}
                            placeholder={field.placeholder}
                            value={formData[channel.id]?.[field.key] || ''}
                            onChange={(e) =>
                              setFormData((fd) => ({
                                ...fd,
                                [channel.id]: {
                                  ...(fd[channel.id] || {}),
                                  [field.key]: e.target.value,
                                },
                              }))
                            }
                            className="mt-1"
                          />
                        </div>
                      ))}
                    </div>
                  )}

                  {/* WhatsApp — QR pairing notice */}
                  {channel.id === 'whatsapp' && (
                    <div className="rounded-lg bg-green-50/50 dark:bg-green-950/20 border border-green-200/50 dark:border-green-800/30 p-4">
                      <div className="flex items-start gap-2">
                        <AlertCircle className="h-4 w-4 text-green-500 mt-0.5" />
                        <div>
                          <h4 className="font-medium text-sm">
                            QR Code Pairing Required
                          </h4>
                          <p className="text-xs text-muted-foreground mt-1">
                            After connecting, you'll need to scan a QR code with
                            your WhatsApp app to pair this device. The pairing
                            UI will open automatically.
                          </p>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Connect Button */}
                  {(mode === 'own' || channel.id === 'whatsapp') && (
                    <div className="mt-4 flex justify-end">
                      <Button
                        onClick={() => handleConnect(channel.id)}
                        disabled={connecting === channel.id}
                      >
                        {connecting === channel.id ? (
                          <Loader2 className="h-4 w-4 animate-spin mr-2" />
                        ) : (
                          <Plug className="h-4 w-4 mr-2" />
                        )}
                        Connect {channel.name}
                      </Button>
                    </div>
                  )}
                </CardContent>
              )}
            </Card>
          );
        })}

        {/* Info Banner */}
        <div className="rounded-lg bg-muted/30 border border-border/50 p-4 mt-2">
          <div className="flex items-start gap-3">
            <AlertCircle className="h-5 w-5 text-muted-foreground mt-0.5" />
            <div>
              <h4 className="font-medium text-sm">
                {t('setting.channelsAutoStart', 'Automatic Gateway Management')}
              </h4>
              <p className="text-xs text-muted-foreground mt-1">
                {t(
                  'setting.channelsAutoStartDescription',
                  'Your OpenClaw AI gateway starts automatically when you connect a channel and stays running for 4 hours after the last activity. It will restart automatically when you receive a new message.'
                )}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
