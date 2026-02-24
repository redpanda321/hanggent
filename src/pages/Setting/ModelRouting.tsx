import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Switch } from "@/components/ui/switch";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  GitBranch,
  Loader2,
  Sparkles,
  Zap,
  DollarSign,
  Crown,
  Info,
  Check,
  RefreshCw,
  Shield,
  TrendingDown,
  AlertTriangle,
} from "lucide-react";
import { proxyFetchGet, proxyFetchPost } from "@/api/http";
import { toast } from "sonner";
import { useTranslation } from "react-i18next";
import { useAuthStore } from "@/store/authStore";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

// Agent display configuration
const AGENT_CONFIG: Record<string, { name: string; description: string; icon: React.ComponentType<any> }> = {
  task_agent: {
    name: "Task Planner",
    description: "Plans and decomposes tasks into subtasks",
    icon: GitBranch,
  },
  coordinator_agent: {
    name: "Coordinator",
    description: "Coordinates between agents",
    icon: GitBranch,
  },
  browser_agent: {
    name: "Browser Agent",
    description: "Web research and data gathering",
    icon: GitBranch,
  },
  developer_agent: {
    name: "Developer Agent",
    description: "Code execution and technical tasks",
    icon: GitBranch,
  },
  document_agent: {
    name: "Document Agent",
    description: "Document creation and processing",
    icon: GitBranch,
  },
  multi_modal_agent: {
    name: "Multi-Modal Agent",
    description: "Image, audio, and video processing",
    icon: GitBranch,
  },
  social_medium_agent: {
    name: "Social Media Agent",
    description: "Social platform interactions",
    icon: GitBranch,
  },
  mcp_agent: {
    name: "MCP Agent",
    description: "MCP tool integration",
    icon: GitBranch,
  },
  opencode_agent: {
    name: "OpenCode Agent",
    description: "AI coding agent for codebase-wide development tasks",
    icon: GitBranch,
  },
};

// Cost tier configuration
const COST_TIERS = [
  { value: "cheap", label: "Cheap", icon: DollarSign, color: "text-green-500" },
  { value: "standard", label: "Standard", icon: Zap, color: "text-blue-500" },
  { value: "premium", label: "Premium", icon: Crown, color: "text-amber-500" },
];

// Complexity badge colors
const COMPLEXITY_COLORS: Record<string, string> = {
  simple: "bg-green-100 text-green-800",
  moderate: "bg-blue-100 text-blue-800",
  complex: "bg-purple-100 text-purple-800",
};

interface ProviderRouting {
  id: number;
  provider_name: string;
  model_type: string;
  prefer: boolean;
  assigned_agents: string[];
  cost_tier: string;
}

interface RoutingConfig {
  available_agents: string[];
  agent_complexity: Record<string, string>;
  providers: ProviderRouting[];
  routing_config: any;
}

interface Recommendation {
  provider_id: number;
  provider_name: string;
  model_type: string;
  suggested_tier: string;
  suggested_agents: string[];
  reason: string;
}

interface AutoScalingConfig {
  fallback_enabled: boolean;
  fallback_provider_id: number | null;
  max_retries: number;
  retry_delay_seconds: number;
  cost_limit_enabled: boolean;
  daily_cost_limit: number | null;
  monthly_cost_limit: number | null;
  cost_limit_fallback_provider_id: number | null;
  warn_at_percentage: number;
  downgrade_at_percentage: number;
}

export default function ModelRouting() {
  const { t } = useTranslation();
  const { token } = useAuthStore();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [routingData, setRoutingData] = useState<RoutingConfig | null>(null);
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [useComplexityRouting, setUseComplexityRouting] = useState(false);
  const [providerAssignments, setProviderAssignments] = useState<Record<number, {
    assigned_agents: string[];
    cost_tier: string;
  }>>({});

  // Auto-scaling configuration state
  const [autoScaling, setAutoScaling] = useState<AutoScalingConfig>({
    fallback_enabled: true,
    fallback_provider_id: null,
    max_retries: 2,
    retry_delay_seconds: 1.0,
    cost_limit_enabled: false,
    daily_cost_limit: null,
    monthly_cost_limit: null,
    cost_limit_fallback_provider_id: null,
    warn_at_percentage: 80,
    downgrade_at_percentage: 90,
  });

  // Load routing configuration
  useEffect(() => {
    // Skip if not authenticated
    if (!token) {
      console.log('[ModelRouting] Skipping load - not authenticated');
      setLoading(false);
      return;
    }
    loadRoutingConfig();
  }, [token]);

  const loadRoutingConfig = async () => {
    try {
      setLoading(true);
      const [routingRes, recommendedRes] = await Promise.all([
        proxyFetchGet("/api/providers/routing"),
        proxyFetchGet("/api/providers/routing/recommended"),
      ]);
      
      setRoutingData(routingRes);
      setRecommendations(recommendedRes.recommendations || []);
      
      // Initialize local state from server data
      const assignments: Record<number, { assigned_agents: string[]; cost_tier: string }> = {};
      routingRes.providers?.forEach((p: ProviderRouting) => {
        assignments[p.id] = {
          assigned_agents: p.assigned_agents || [],
          cost_tier: p.cost_tier || "standard",
        };
      });
      setProviderAssignments(assignments);
      
      setUseComplexityRouting(routingRes.routing_config?.use_complexity_routing || false);
      
      // Load auto-scaling config if available
      if (routingRes.routing_config?.auto_scaling) {
        setAutoScaling(prev => ({
          ...prev,
          ...routingRes.routing_config.auto_scaling,
        }));
      }
    } catch (error) {
      console.error("Failed to load routing config:", error);
      toast.error("Failed to load model routing configuration");
    } finally {
      setLoading(false);
    }
  };

  // Save routing configuration
  const handleSave = async () => {
    try {
      setSaving(true);
      
      const updates = Object.entries(providerAssignments).map(([id, data]) => ({
        provider_id: parseInt(id),
        assigned_agents: data.assigned_agents,
        cost_tier: data.cost_tier,
      }));
      
      // Include auto-scaling config in the save
      const payload = {
        provider_updates: updates,
        use_complexity_routing: useComplexityRouting,
        auto_scaling: autoScaling,
      };
      
      await proxyFetchPost("/api/providers/routing", payload);
      toast.success("Model routing configuration saved");
      
      // Reload to confirm
      await loadRoutingConfig();
    } catch (error) {
      console.error("Failed to save routing config:", error);
      toast.error("Failed to save model routing configuration");
    } finally {
      setSaving(false);
    }
  };

  // Apply recommendations
  const applyRecommendations = () => {
    const newAssignments = { ...providerAssignments };
    
    recommendations.forEach((rec) => {
      if (newAssignments[rec.provider_id]) {
        newAssignments[rec.provider_id] = {
          assigned_agents: rec.suggested_agents,
          cost_tier: rec.suggested_tier,
        };
      }
    });
    
    setProviderAssignments(newAssignments);
    toast.info("Recommendations applied. Click Save to confirm.");
  };

  // Toggle agent assignment for a provider
  const toggleAgentAssignment = (providerId: number, agentId: string) => {
    setProviderAssignments((prev) => {
      const current = prev[providerId] || { assigned_agents: [], cost_tier: "standard" };
      const agents = current.assigned_agents.includes(agentId)
        ? current.assigned_agents.filter((a) => a !== agentId)
        : [...current.assigned_agents, agentId];
      
      return {
        ...prev,
        [providerId]: { ...current, assigned_agents: agents },
      };
    });
  };

  // Update cost tier for a provider
  const updateCostTier = (providerId: number, tier: string) => {
    setProviderAssignments((prev) => ({
      ...prev,
      [providerId]: {
        ...prev[providerId],
        cost_tier: tier,
      },
    }));
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!routingData?.providers?.length) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <GitBranch className="w-5 h-5" />
            Model Routing
          </CardTitle>
          <CardDescription>
            Configure which LLM models handle different agent types
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="text-center py-8 text-muted-foreground">
            <p>No providers configured yet.</p>
            <p className="text-sm mt-2">
              Add providers in the Models tab first, then configure routing here.
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <GitBranch className="w-5 h-5" />
                Model Routing
              </CardTitle>
              <CardDescription className="mt-1">
                Assign different LLM models to different agent types for optimized performance and cost
              </CardDescription>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={applyRecommendations}
                disabled={!recommendations.length}
              >
                <Sparkles className="w-4 h-4 mr-1" />
                Apply Recommendations
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={loadRoutingConfig}
              >
                <RefreshCw className="w-4 h-4 mr-1" />
                Refresh
              </Button>
              <Button
                onClick={handleSave}
                disabled={saving}
              >
                {saving ? (
                  <Loader2 className="w-4 h-4 mr-1 animate-spin" />
                ) : (
                  <Check className="w-4 h-4 mr-1" />
                )}
                Save Configuration
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <Switch
                checked={useComplexityRouting}
                onCheckedChange={setUseComplexityRouting}
              />
              <span className="text-sm">Enable complexity-based routing</span>
              <Tooltip>
                <TooltipTrigger>
                  <Info className="w-4 h-4 text-muted-foreground" />
                </TooltipTrigger>
                <TooltipContent>
                  <p className="max-w-xs">
                    When enabled, agents will be routed to models based on their
                    default complexity level if no specific agent override is set.
                  </p>
                </TooltipContent>
              </Tooltip>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Agent Complexity Overview */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Agent Complexity Levels</CardTitle>
          <CardDescription>
            Each agent has a default complexity level that determines model selection
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {routingData.available_agents.map((agentId) => {
              const config = AGENT_CONFIG[agentId] || { name: agentId, description: "" };
              const complexity = routingData.agent_complexity[agentId] || "moderate";
              
              return (
                <div
                  key={agentId}
                  className="p-3 border rounded-lg hover:bg-muted/50 transition-colors"
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-medium text-sm">{config.name}</span>
                    <Badge className={COMPLEXITY_COLORS[complexity]}>
                      {complexity}
                    </Badge>
                  </div>
                  <p className="text-xs text-muted-foreground">{config.description}</p>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* Provider Routing Configuration */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Provider Configuration</CardTitle>
          <CardDescription>
            Assign agents to each provider and set cost tiers
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {routingData.providers.map((provider) => {
            const assignment = providerAssignments[provider.id] || {
              assigned_agents: [],
              cost_tier: "standard",
            };
            const recommendation = recommendations.find((r) => r.provider_id === provider.id);
            
            return (
              <div
                key={provider.id}
                className="p-4 border rounded-lg space-y-4"
              >
                {/* Provider Header */}
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-semibold">{provider.provider_name}</span>
                        {provider.prefer && (
                          <Badge variant="secondary" className="text-xs">
                            Default
                          </Badge>
                        )}
                      </div>
                      <span className="text-sm text-muted-foreground">
                        {provider.model_type}
                      </span>
                    </div>
                  </div>
                  
                  {/* Cost Tier Selector */}
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-muted-foreground">Cost Tier:</span>
                    <Select
                      value={assignment.cost_tier}
                      onValueChange={(value) => updateCostTier(provider.id, value)}
                    >
                      <SelectTrigger className="w-32">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {COST_TIERS.map((tier) => (
                          <SelectItem key={tier.value} value={tier.value}>
                            <div className="flex items-center gap-2">
                              <tier.icon className={`w-4 h-4 ${tier.color}`} />
                              {tier.label}
                            </div>
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                
                {/* Recommendation hint */}
                {recommendation && (
                  <div className="text-xs text-muted-foreground bg-muted/50 p-2 rounded">
                    <Sparkles className="w-3 h-3 inline mr-1" />
                    Suggested: {recommendation.suggested_agents.join(", ")} ({recommendation.suggested_tier})
                  </div>
                )}
                
                <Separator />
                
                {/* Agent Assignment */}
                <div>
                  <span className="text-sm font-medium mb-2 block">Assigned Agents:</span>
                  <div className="flex flex-wrap gap-2">
                    {routingData.available_agents.map((agentId) => {
                      const isAssigned = assignment.assigned_agents.includes(agentId);
                      const config = AGENT_CONFIG[agentId] || { name: agentId };
                      
                      return (
                        <Button
                          key={agentId}
                          variant={isAssigned ? "primary" : "outline"}
                          size="sm"
                          onClick={() => toggleAgentAssignment(provider.id, agentId)}
                          className="text-xs"
                        >
                          {isAssigned && <Check className="w-3 h-3 mr-1" />}
                          {config.name}
                        </Button>
                      );
                    })}
                  </div>
                </div>
              </div>
            );
          })}
        </CardContent>
      </Card>

      {/* Routing Summary */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Routing Summary</CardTitle>
          <CardDescription>
            Current model assignment for each agent type
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            {routingData.available_agents.map((agentId) => {
              const config = AGENT_CONFIG[agentId] || { name: agentId };
              
              // Find which provider is assigned to this agent
              let assignedProvider: ProviderRouting | undefined;
              for (const [providerId, assignment] of Object.entries(providerAssignments)) {
                if (assignment.assigned_agents.includes(agentId)) {
                  assignedProvider = routingData.providers.find(
                    (p) => p.id === parseInt(providerId)
                  );
                  break;
                }
              }
              
              // Fallback to default provider
              if (!assignedProvider) {
                assignedProvider = routingData.providers.find((p) => p.prefer);
              }
              
              return (
                <div
                  key={agentId}
                  className="flex items-center justify-between py-2 px-3 bg-muted/30 rounded"
                >
                  <span className="font-medium">{config.name}</span>
                  <span className="text-sm text-muted-foreground">
                    {assignedProvider
                      ? `${assignedProvider.provider_name} (${assignedProvider.model_type})`
                      : "Default provider"}
                  </span>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* Auto-Scaling Configuration */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Shield className="w-5 h-5" />
            Auto-Scaling & Fallback
          </CardTitle>
          <CardDescription>
            Configure automatic fallback on errors and cost limit management
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Fallback on Error */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="space-y-0.5">
                <div className="flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-orange-500" />
                  <Label className="text-base font-medium">Fallback on Error</Label>
                </div>
                <p className="text-sm text-muted-foreground">
                  Automatically switch to a fallback model when the primary model fails
                </p>
              </div>
              <Switch
                checked={autoScaling.fallback_enabled}
                onCheckedChange={(checked) => 
                  setAutoScaling(prev => ({ ...prev, fallback_enabled: checked }))
                }
              />
            </div>

            {autoScaling.fallback_enabled && (
              <div className="pl-6 space-y-4 border-l-2 border-muted">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="fallback-provider">Fallback Model</Label>
                    <Select
                      value={autoScaling.fallback_provider_id?.toString() || "none"}
                      onValueChange={(value) => 
                        setAutoScaling(prev => ({ 
                          ...prev, 
                          fallback_provider_id: value === "none" ? null : parseInt(value) 
                        }))
                      }
                    >
                      <SelectTrigger id="fallback-provider">
                        <SelectValue placeholder="Select fallback model" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="none">No fallback</SelectItem>
                        {routingData.providers.map((p) => (
                          <SelectItem key={p.id} value={p.id.toString()}>
                            {p.provider_name} ({p.model_type})
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <p className="text-xs text-muted-foreground">
                      Tip: Choose a cheaper or more reliable model
                    </p>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="max-retries">Max Retries</Label>
                    <Input
                      id="max-retries"
                      type="number"
                      min={0}
                      max={5}
                      value={autoScaling.max_retries}
                      onChange={(e) => 
                        setAutoScaling(prev => ({ 
                          ...prev, 
                          max_retries: parseInt(e.target.value) || 0 
                        }))
                      }
                    />
                    <p className="text-xs text-muted-foreground">
                      Retry primary model before switching to fallback
                    </p>
                  </div>
                </div>
              </div>
            )}
          </div>

          <Separator />

          {/* Cost Limits */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="space-y-0.5">
                <div className="flex items-center gap-2">
                  <TrendingDown className="w-4 h-4 text-green-500" />
                  <Label className="text-base font-medium">Cost Limit Auto-Scaling</Label>
                </div>
                <p className="text-sm text-muted-foreground">
                  Automatically downgrade to cheaper models when approaching cost limits
                </p>
              </div>
              <Switch
                checked={autoScaling.cost_limit_enabled}
                onCheckedChange={(checked) => 
                  setAutoScaling(prev => ({ ...prev, cost_limit_enabled: checked }))
                }
              />
            </div>

            {autoScaling.cost_limit_enabled && (
              <div className="pl-6 space-y-4 border-l-2 border-muted">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="daily-limit">Daily Cost Limit (USD)</Label>
                    <div className="relative">
                      <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                      <Input
                        id="daily-limit"
                        type="number"
                        min={0}
                        step={0.1}
                        placeholder="e.g., 5.00"
                        className="pl-9"
                        value={autoScaling.daily_cost_limit || ""}
                        onChange={(e) => 
                          setAutoScaling(prev => ({ 
                            ...prev, 
                            daily_cost_limit: e.target.value ? parseFloat(e.target.value) : null 
                          }))
                        }
                      />
                    </div>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="monthly-limit">Monthly Cost Limit (USD)</Label>
                    <div className="relative">
                      <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                      <Input
                        id="monthly-limit"
                        type="number"
                        min={0}
                        step={1}
                        placeholder="e.g., 50.00"
                        className="pl-9"
                        value={autoScaling.monthly_cost_limit || ""}
                        onChange={(e) => 
                          setAutoScaling(prev => ({ 
                            ...prev, 
                            monthly_cost_limit: e.target.value ? parseFloat(e.target.value) : null 
                          }))
                        }
                      />
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="cost-fallback">Cost Limit Fallback Model</Label>
                    <Select
                      value={autoScaling.cost_limit_fallback_provider_id?.toString() || "none"}
                      onValueChange={(value) => 
                        setAutoScaling(prev => ({ 
                          ...prev, 
                          cost_limit_fallback_provider_id: value === "none" ? null : parseInt(value) 
                        }))
                      }
                    >
                      <SelectTrigger id="cost-fallback">
                        <SelectValue placeholder="Select cheaper model" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="none">No fallback</SelectItem>
                        {routingData.providers
                          .filter(p => providerAssignments[p.id]?.cost_tier === "cheap")
                          .map((p) => (
                            <SelectItem key={p.id} value={p.id.toString()}>
                              <div className="flex items-center gap-2">
                                <DollarSign className="w-3 h-3 text-green-500" />
                                {p.provider_name} ({p.model_type})
                              </div>
                            </SelectItem>
                          ))}
                        {routingData.providers
                          .filter(p => providerAssignments[p.id]?.cost_tier !== "cheap")
                          .map((p) => (
                            <SelectItem key={p.id} value={p.id.toString()}>
                              {p.provider_name} ({p.model_type})
                            </SelectItem>
                          ))}
                      </SelectContent>
                    </Select>
                    <p className="text-xs text-muted-foreground">
                      Model to use when cost limit threshold is reached
                    </p>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="downgrade-percent">Downgrade Threshold (%)</Label>
                    <Input
                      id="downgrade-percent"
                      type="number"
                      min={50}
                      max={100}
                      value={autoScaling.downgrade_at_percentage}
                      onChange={(e) => 
                        setAutoScaling(prev => ({ 
                          ...prev, 
                          downgrade_at_percentage: parseInt(e.target.value) || 90 
                        }))
                      }
                    />
                    <p className="text-xs text-muted-foreground">
                      Auto-downgrade when this % of limit is reached
                    </p>
                  </div>
                </div>

                <div className="p-3 bg-muted/50 rounded-lg text-sm">
                  <div className="flex items-start gap-2">
                    <Info className="w-4 h-4 text-blue-500 mt-0.5" />
                    <div>
                      <p className="font-medium">How it works:</p>
                      <ul className="text-muted-foreground mt-1 space-y-1">
                        <li>• At {autoScaling.warn_at_percentage}% of limit: Warning notification</li>
                        <li>• At {autoScaling.downgrade_at_percentage}% of limit: Auto-switch to cheaper model</li>
                        <li>• Usage resets daily/monthly as configured</li>
                      </ul>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
