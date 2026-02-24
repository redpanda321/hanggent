/**
 * ExternalServices Settings Panel
 * 
 * UI component for managing external services (OpenCode, OpenClaw)
 * - View service status
 * - Start/Stop/Restart services
 * - Configure service settings
 */

import * as React from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';
import {
  useServiceStatus,
  useServiceControl,
  useServiceConfig,
  ServiceName,
  ServiceStatus,
  getStatusBadgeVariant,
} from '@/lib/use-service-status';
import {
  Play,
  Square,
  RefreshCw,
  Activity,
  AlertCircle,
  CheckCircle,
  Loader2,
  Settings,
  Code,
  MessageSquare,
} from 'lucide-react';

interface ServiceCardProps {
  name: ServiceName;
  title: string;
  description: string;
  icon: React.ReactNode;
}

function ServiceCard({ name, title, description, icon }: ServiceCardProps) {
  const { status } = useServiceStatus();
  const { start, stop, restart, loading: actionLoading, error: actionError } = useServiceControl(name);
  const { config, updateConfig } = useServiceConfig();

  const serviceState = status[name];
  const serviceConfig = config?.[name];

  const currentStatus: ServiceStatus = serviceState?.status || 'stopped';
  const isRunning = currentStatus === 'running';
  const isTransitioning = currentStatus === 'starting' || currentStatus === 'stopping';

  const formatUptime = (startTime?: number) => {
    if (!startTime) return 'N/A';
    const seconds = Math.floor((Date.now() - startTime) / 1000);
    if (seconds < 60) return `${seconds}s`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
    return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
  };

  return (
    <Card className="w-full">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-muted">
              {icon}
            </div>
            <div>
              <CardTitle className="text-lg">{title}</CardTitle>
              <CardDescription className="text-sm">{description}</CardDescription>
            </div>
          </div>
          <Badge variant={getStatusBadgeVariant(currentStatus)}>
            {currentStatus}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Service Stats */}
        {serviceState && (
          <div className="grid grid-cols-3 gap-4 text-sm">
            <div className="space-y-1">
              <p className="text-muted-foreground">Uptime</p>
              <p className="font-medium">{formatUptime(serviceState.startTime)}</p>
            </div>
            <div className="space-y-1">
              <p className="text-muted-foreground">Restarts</p>
              <p className="font-medium">{serviceState.restartCount}</p>
            </div>
            <div className="space-y-1">
              <p className="text-muted-foreground">Health</p>
              <div className="flex items-center gap-1">
                {serviceState.healthCheck?.healthy ? (
                  <>
                    <CheckCircle className="h-4 w-4 text-green-500" />
                    <span className="font-medium text-green-500">OK</span>
                  </>
                ) : (
                  <>
                    <AlertCircle className="h-4 w-4 text-yellow-500" />
                    <span className="font-medium text-yellow-500">Unknown</span>
                  </>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Error Display */}
        {(serviceState?.lastError || actionError) && (
          <div className="p-3 rounded-lg bg-destructive/10 border border-destructive/20">
            <div className="flex items-start gap-2">
              <AlertCircle className="h-4 w-4 text-destructive mt-0.5" />
              <p className="text-sm text-destructive">
                {actionError || serviceState?.lastError}
              </p>
            </div>
          </div>
        )}

        {/* Service Configuration */}
        {serviceConfig && (
          <div className="space-y-3 pt-2 border-t">
            <div className="flex items-center justify-between">
              <Label htmlFor={`${name}-enabled`} className="text-sm">
                Auto-start on launch
              </Label>
              <Switch
                id={`${name}-enabled`}
                checked={serviceConfig.enabled}
                onCheckedChange={(checked) => updateConfig(name, { enabled: checked })}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor={`${name}-url`} className="text-sm text-muted-foreground">
                Service URL
              </Label>
              <Input
                id={`${name}-url`}
                value={serviceConfig.url}
                onChange={(e) => updateConfig(name, { url: e.target.value })}
                placeholder="http://localhost:4096"
                className="h-8 text-sm"
              />
            </div>
          </div>
        )}

        {/* Action Buttons */}
        <div className="flex gap-2 pt-2">
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
              Start
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
                onClick={restart}
                disabled={actionLoading || isTransitioning}
              >
                <RefreshCw className={cn("h-4 w-4", actionLoading && "animate-spin")} />
              </Button>
            </>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

/**
 * Main External Services Settings Panel
 */
export function ExternalServices() {
  const { isAvailable, loading } = useServiceStatus();

  if (!isAvailable) {
    return (
      <div className="p-4 text-center text-muted-foreground">
        <Settings className="h-8 w-8 mx-auto mb-2 opacity-50" />
        <p className="text-sm">External services are only available in desktop mode</p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="p-4 flex items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-4 p-4">
      <div className="space-y-1">
        <h3 className="text-lg font-semibold">External Services</h3>
        <p className="text-sm text-muted-foreground">
          Manage external AI services that enhance Hanggent's capabilities
        </p>
      </div>

      <div className="grid gap-4">
        <ServiceCard
          name="opencode"
          title="OpenCode"
          description="AI coding agent for development tasks"
          icon={<Code className="h-5 w-5" />}
        />
        <ServiceCard
          name="openclaw"
          title="OpenClaw"
          description="Messaging gateway for multi-channel communication"
          icon={<MessageSquare className="h-5 w-5" />}
        />
      </div>

      <div className="pt-4 border-t">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Activity className="h-4 w-4" />
          <span>Services run locally and enhance agent capabilities when available</span>
        </div>
      </div>
    </div>
  );
}

export default ExternalServices;
