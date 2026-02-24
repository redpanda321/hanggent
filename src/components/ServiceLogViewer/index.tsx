/**
 * ServiceLogViewer - Log viewer component with tabs for different log sources
 * 
 * Displays logs from:
 * - Hanggent (main application)
 * - OpenCode (AI coding agent)
 * - OpenClaw (messaging gateway)
 */

import * as React from 'react';
import { useState, useEffect, useRef, useCallback } from 'react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { useServiceLogs, useServiceStatus, ServiceName } from '@/lib/use-service-status';
import { cn } from '@/lib/utils';
import {
  Trash2,
  Download,
  ArrowDown,
  Pause,
  Play,
  Terminal,
  Code,
  MessageSquare,
} from 'lucide-react';

interface LogEntry {
  source: string;
  level: string;
  message: string;
  timestamp: number;
}

interface LogPanelProps {
  logs: LogEntry[];
  loading: boolean;
  onClear: () => void;
  autoScroll: boolean;
}

function LogPanel({ logs, loading, onClear, autoScroll }: LogPanelProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const endRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new logs arrive
  useEffect(() => {
    if (autoScroll && endRef.current) {
      endRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, autoScroll]);

  const getLevelColor = (level: string) => {
    switch (level.toLowerCase()) {
      case 'error':
        return 'text-red-500';
      case 'warn':
      case 'warning':
        return 'text-yellow-500';
      case 'info':
        return 'text-blue-500';
      case 'debug':
        return 'text-gray-400';
      default:
        return 'text-foreground';
    }
  };

  const formatTimestamp = (ts: number) => {
    const date = new Date(ts);
    return date.toLocaleTimeString('en-US', {
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full text-muted-foreground">
        Loading logs...
      </div>
    );
  }

  if (logs.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-muted-foreground gap-2">
        <Terminal className="h-8 w-8 opacity-50" />
        <p>No logs yet</p>
      </div>
    );
  }

  return (
    <div 
      ref={containerRef}
      className="h-full overflow-y-auto font-mono text-xs bg-black/90 p-2 rounded-md"
    >
      {logs.map((log, index) => (
        <div 
          key={`${log.timestamp}-${index}`}
          className="flex gap-2 py-0.5 hover:bg-white/5"
        >
          <span className="text-gray-500 shrink-0">
            {formatTimestamp(log.timestamp)}
          </span>
          <span className={cn('uppercase w-12 shrink-0', getLevelColor(log.level))}>
            [{log.level}]
          </span>
          <span className="text-gray-300 break-all whitespace-pre-wrap">
            {log.message}
          </span>
        </div>
      ))}
      <div ref={endRef} />
    </div>
  );
}

type TabValue = 'hanggent' | 'opencode' | 'openclaw';

interface ServiceLogViewerProps {
  className?: string;
  defaultTab?: TabValue;
}

export function ServiceLogViewer({ className, defaultTab = 'hanggent' }: ServiceLogViewerProps) {
  const [activeTab, setActiveTab] = useState<TabValue>(defaultTab);
  const [autoScroll, setAutoScroll] = useState(true);

  const { status } = useServiceStatus();
  const hanggentLogs = useServiceLogs('hanggent');
  const opencodeLogs = useServiceLogs('opencode');
  const openclawLogs = useServiceLogs('openclaw');

  const getLogsForTab = useCallback((tab: TabValue) => {
    switch (tab) {
      case 'hanggent':
        return hanggentLogs;
      case 'opencode':
        return opencodeLogs;
      case 'openclaw':
        return openclawLogs;
    }
  }, [hanggentLogs, opencodeLogs, openclawLogs]);

  const currentLogs = getLogsForTab(activeTab);

  const handleDownload = useCallback(() => {
    const logs = currentLogs.logs;
    if (logs.length === 0) return;

    const content = logs
      .map(log => `[${new Date(log.timestamp).toISOString()}] [${log.level.toUpperCase()}] ${log.message}`)
      .join('\n');

    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${activeTab}-logs-${new Date().toISOString().slice(0, 10)}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  }, [currentLogs.logs, activeTab]);

  const getTabIcon = (tab: TabValue) => {
    switch (tab) {
      case 'hanggent':
        return <Terminal className="h-4 w-4" />;
      case 'opencode':
        return <Code className="h-4 w-4" />;
      case 'openclaw':
        return <MessageSquare className="h-4 w-4" />;
    }
  };

  const getServiceStatus = (name: ServiceName) => {
    return status[name]?.status || 'stopped';
  };

  const getStatusDot = (statusValue: string) => {
    const colors: Record<string, string> = {
      running: 'bg-green-500',
      starting: 'bg-yellow-500',
      stopping: 'bg-yellow-500',
      error: 'bg-red-500',
      degraded: 'bg-orange-500',
      stopped: 'bg-gray-500',
    };
    return colors[statusValue] || 'bg-gray-500';
  };

  return (
    <div className={cn('flex flex-col h-full', className)}>
      <Tabs 
        value={activeTab} 
        onValueChange={(v) => setActiveTab(v as TabValue)}
        className="flex flex-col h-full"
      >
        {/* Tab Header with Controls */}
        <div className="flex items-center justify-between border-b px-2 py-1">
          <TabsList className="h-8">
            <TabsTrigger value="hanggent" className="text-xs gap-1.5 px-2">
              {getTabIcon('hanggent')}
              Hanggent
            </TabsTrigger>
            <TabsTrigger value="opencode" className="text-xs gap-1.5 px-2">
              {getTabIcon('opencode')}
              OpenCode
              <span className={cn('w-2 h-2 rounded-full', getStatusDot(getServiceStatus('opencode')))} />
            </TabsTrigger>
            <TabsTrigger value="openclaw" className="text-xs gap-1.5 px-2">
              {getTabIcon('openclaw')}
              OpenClaw
              <span className={cn('w-2 h-2 rounded-full', getStatusDot(getServiceStatus('openclaw')))} />
            </TabsTrigger>
          </TabsList>

          {/* Controls */}
          <div className="flex items-center gap-1">
            <Badge variant="outline" className="text-xs">
              {currentLogs.logs.length} logs
            </Badge>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              onClick={() => setAutoScroll(!autoScroll)}
              title={autoScroll ? 'Pause auto-scroll' : 'Resume auto-scroll'}
            >
              {autoScroll ? (
                <Pause className="h-3.5 w-3.5" />
              ) : (
                <Play className="h-3.5 w-3.5" />
              )}
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              onClick={handleDownload}
              disabled={currentLogs.logs.length === 0}
              title="Download logs"
            >
              <Download className="h-3.5 w-3.5" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              onClick={currentLogs.clearLogs}
              disabled={currentLogs.logs.length === 0}
              title="Clear logs"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>

        {/* Tab Content */}
        <div className="flex-1 min-h-0">
          <TabsContent value="hanggent" className="h-full m-0 p-2">
            <LogPanel
              logs={hanggentLogs.logs}
              loading={hanggentLogs.loading}
              onClear={hanggentLogs.clearLogs}
              autoScroll={autoScroll}
            />
          </TabsContent>
          <TabsContent value="opencode" className="h-full m-0 p-2">
            <LogPanel
              logs={opencodeLogs.logs}
              loading={opencodeLogs.loading}
              onClear={opencodeLogs.clearLogs}
              autoScroll={autoScroll}
            />
          </TabsContent>
          <TabsContent value="openclaw" className="h-full m-0 p-2">
            <LogPanel
              logs={openclawLogs.logs}
              loading={openclawLogs.loading}
              onClear={openclawLogs.clearLogs}
              autoScroll={autoScroll}
            />
          </TabsContent>
        </div>
      </Tabs>
    </div>
  );
}

export default ServiceLogViewer;
