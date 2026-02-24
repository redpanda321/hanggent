import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Progress } from "@/components/ui/progress";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  BarChart3,
  Loader2,
  Coins,
  Zap,
  Clock,
  TrendingUp,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  Bot,
  DollarSign,
} from "lucide-react";
import { proxyFetchGet } from "@/api/http";
import { toast } from "sonner";
import { useTranslation } from "react-i18next";
import { useAuthStore } from "@/store/authStore";

// Types for usage data - aligned with backend UsageDashboardData schema
interface UsageRecord {
  id: number;
  user_id: number;
  task_id: string;
  project_id?: string;
  agent_name: string;
  agent_step?: number;
  model_platform: string;
  model_type: string;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  estimated_cost: number;
  execution_time_ms?: number;
  success: boolean;
  error_message?: string;
  created_at: string;
}

interface UsageSummaryByAgent {
  agent_name: string;
  total_calls: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_tokens: number;
  total_cost: number;
  success_rate: number;
  avg_execution_time_ms?: number;
}

interface UsageSummaryByModel {
  model_platform: string;
  model_type: string;
  total_calls: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_tokens: number;
  total_cost: number;
}

interface UsageSummaryByDay {
  date: string;
  total_calls: number;
  total_tokens: number;
  total_cost: number;
}

interface UsageSummary {
  total_tokens: number;
  total_cost: number;
  total_calls: number;
  by_agent: UsageSummaryByAgent[];
  by_model: UsageSummaryByModel[];
  by_day: UsageSummaryByDay[];
  start_date?: string;
  end_date?: string;
}

// Time range options
const TIME_RANGES = [
  { value: "7", label: "Last 7 days" },
  { value: "30", label: "Last 30 days" },
  { value: "90", label: "Last 90 days" },
  { value: "all", label: "All time" },
];

// Agent display names
const AGENT_DISPLAY_NAMES: Record<string, string> = {
  task_agent: "Task Planner",
  coordinator_agent: "Coordinator",
  browser_agent: "Browser Agent",
  developer_agent: "Developer",
  document_agent: "Document Agent",
  multi_modal_agent: "Multi-Modal",
  social_medium_agent: "Social Media",
  mcp_agent: "MCP Agent",
  question_confirm_agent: "Question Confirm",
  task_summary_agent: "Task Summary",
  new_worker_agent: "Worker Agent",
};

// Color mapping for agents
const AGENT_COLORS: Record<string, string> = {
  task_agent: "bg-blue-500",
  coordinator_agent: "bg-purple-500",
  browser_agent: "bg-green-500",
  developer_agent: "bg-orange-500",
  document_agent: "bg-cyan-500",
  multi_modal_agent: "bg-pink-500",
  social_medium_agent: "bg-indigo-500",
  mcp_agent: "bg-yellow-500",
  question_confirm_agent: "bg-teal-500",
  task_summary_agent: "bg-rose-500",
  new_worker_agent: "bg-emerald-500",
};

export default function UsageDashboard() {
  const { t } = useTranslation();
  const { token } = useAuthStore();
  
  const [isLoading, setIsLoading] = useState(true);
  const [summary, setSummary] = useState<UsageSummary | null>(null);
  const [recentRecords, setRecentRecords] = useState<UsageRecord[]>([]);
  const [timeRange, setTimeRange] = useState("30");
  const [error, setError] = useState<string | null>(null);

  // Fetch usage data
  const fetchUsageData = async () => {
    if (!token) {
      console.log('[UsageDashboard] Skipping load - not authenticated');
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    setError(null);
    
    try {
      // Calculate date range
      const endDate = new Date().toISOString().split('T')[0];
      let startDate = '';
      if (timeRange !== 'all') {
        const start = new Date();
        start.setDate(start.getDate() - parseInt(timeRange));
        startDate = start.toISOString().split('T')[0];
      }

      // Fetch summary
      const summaryParams = new URLSearchParams();
      if (startDate) {
        summaryParams.append('start_date', startDate);
        summaryParams.append('end_date', endDate);
      }
      const summaryUrl = `/api/usage/summary${summaryParams.toString() ? `?${summaryParams.toString()}` : ''}`;
      const summaryRes = await proxyFetchGet(summaryUrl);
      // Server returns UsageDashboardData directly (no envelope).
      // Error responses have 'code' (app error) or 'detail' (HTTP error).
      if (summaryRes?.code || summaryRes?.detail) {
        throw new Error(summaryRes.text || summaryRes.detail || 'Failed to fetch summary');
      }
      setSummary(summaryRes);

      // Fetch recent records
      const recordsParams = new URLSearchParams();
      recordsParams.append('limit', '20');
      if (startDate) {
        recordsParams.append('start_date', startDate);
        recordsParams.append('end_date', endDate);
      }
      const recordsRes = await proxyFetchGet(`/api/usage?${recordsParams.toString()}`);
      // Server returns List[UsageRecordOut] directly (array, no envelope).
      if (Array.isArray(recordsRes)) {
        setRecentRecords(recordsRes);
      } else if (!recordsRes?.code && !recordsRes?.detail) {
        setRecentRecords([]);
      }
    } catch (err: any) {
      console.error('[UsageDashboard] Error fetching data:', err);
      setError(err.message || 'Failed to load usage data');
      toast.error(t("usage.fetch_error", "Failed to load usage data"));
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchUsageData();
  }, [token, timeRange]);

  // Format cost
  const formatCost = (cost: number): string => {
    if (cost < 0.01) return `$${cost.toFixed(4)}`;
    if (cost < 1) return `$${cost.toFixed(3)}`;
    return `$${cost.toFixed(2)}`;
  };

  // Format tokens
  const formatTokens = (tokens: number): string => {
    if (tokens >= 1000000) return `${(tokens / 1000000).toFixed(1)}M`;
    if (tokens >= 1000) return `${(tokens / 1000).toFixed(1)}K`;
    return tokens.toString();
  };

  // Format date
  const formatDate = (dateStr: string): string => {
    const date = new Date(dateStr);
    return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  };

  // Calculate max values for progress bars
  const getMaxAgentTokens = (): number => {
    if (!summary?.by_agent || summary.by_agent.length === 0) return 0;
    return Math.max(...summary.by_agent.map(a => a.total_tokens), 1);
  };

  if (!token) {
    return (
      <Card className="w-full">
        <CardContent className="flex flex-col items-center justify-center py-12">
          <AlertCircle className="w-12 h-12 text-muted-foreground mb-4" />
          <p className="text-muted-foreground">{t("usage.login_required", "Please log in to view usage statistics")}</p>
        </CardContent>
      </Card>
    );
  }

  if (isLoading) {
    return (
      <Card className="w-full">
        <CardContent className="flex flex-col items-center justify-center py-12">
          <Loader2 className="w-8 h-8 animate-spin text-primary mb-4" />
          <p className="text-muted-foreground">{t("usage.loading", "Loading usage data...")}</p>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="w-full">
        <CardContent className="flex flex-col items-center justify-center py-12">
          <AlertCircle className="w-12 h-12 text-destructive mb-4" />
          <p className="text-destructive mb-4">{error}</p>
          <Button onClick={fetchUsageData} variant="outline">
            <RefreshCw className="w-4 h-4 mr-2" />
            {t("common.retry", "Retry")}
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold flex items-center gap-2">
            <BarChart3 className="w-6 h-6" />
            {t("usage.title", "Usage Dashboard")}
          </h2>
          <p className="text-muted-foreground text-sm mt-1">
            {t("usage.description", "Track token usage and costs across agents and models")}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Select value={timeRange} onValueChange={setTimeRange}>
            <SelectTrigger className="w-[140px]">
              <SelectValue placeholder="Select range" />
            </SelectTrigger>
            <SelectContent>
              {TIME_RANGES.map(range => (
                <SelectItem key={range.value} value={range.value}>
                  {range.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button variant="outline" size="icon" onClick={fetchUsageData}>
            <RefreshCw className="w-4 h-4" />
          </Button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Cost */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">{t("usage.total_cost", "Total Cost")}</CardTitle>
            <DollarSign className="w-4 h-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{formatCost(summary?.total_cost || 0)}</div>
            <p className="text-xs text-muted-foreground">
              {summary?.total_calls || 0} {t("usage.requests", "requests")}
            </p>
          </CardContent>
        </Card>

        {/* Total Tokens */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">{t("usage.total_tokens", "Total Tokens")}</CardTitle>
            <Zap className="w-4 h-4 text-blue-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{formatTokens(summary?.total_tokens || 0)}</div>
            <p className="text-xs text-muted-foreground">
              {summary?.total_calls || 0} {t("usage.api_calls", "API calls")}
            </p>
          </CardContent>
        </Card>

        {/* Active Agents */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">{t("usage.active_agents", "Active Agents")}</CardTitle>
            <Bot className="w-4 h-4 text-purple-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{(summary?.by_agent || []).length}</div>
            <p className="text-xs text-muted-foreground">
              {t("usage.agents_used", "agents used")}
            </p>
          </CardContent>
        </Card>

        {/* Models Used */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">{t("usage.models_used", "Models Used")}</CardTitle>
            <TrendingUp className="w-4 h-4 text-orange-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{(summary?.by_model || []).length}</div>
            <p className="text-xs text-muted-foreground">
              {t("usage.different_models", "different models")}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Usage by Agent */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Bot className="w-5 h-5" />
            {t("usage.by_agent", "Usage by Agent")}
          </CardTitle>
          <CardDescription>
            {t("usage.by_agent_desc", "Token consumption breakdown by agent type")}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {summary?.by_agent && summary.by_agent.length > 0 ? (
            <div className="space-y-4">
              {[...summary.by_agent]
                .sort((a, b) => b.total_tokens - a.total_tokens)
                .map((agent) => (
                  <div key={agent.agent_name} className="space-y-2">
                    <div className="flex items-center justify-between text-sm">
                      <div className="flex items-center gap-2">
                        <div className={`w-3 h-3 rounded-full ${AGENT_COLORS[agent.agent_name] || 'bg-gray-500'}`} />
                        <span className="font-medium">
                          {AGENT_DISPLAY_NAMES[agent.agent_name] || agent.agent_name}
                        </span>
                        <Badge variant="secondary" className="text-xs">
                          {agent.total_calls} calls
                        </Badge>
                      </div>
                      <div className="flex items-center gap-4 text-muted-foreground">
                        <span>{formatTokens(agent.total_tokens)} tokens</span>
                        <span className="text-green-600 font-medium">{formatCost(agent.total_cost)}</span>
                      </div>
                    </div>
                    <Progress 
                      value={(agent.total_tokens / getMaxAgentTokens()) * 100} 
                      className="h-2" 
                    />
                  </div>
                ))}
            </div>
          ) : (
            <div className="text-center py-8 text-muted-foreground">
              {t("usage.no_agent_data", "No agent usage data available")}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Usage by Model */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Coins className="w-5 h-5" />
            {t("usage.by_model", "Usage by Model")}
          </CardTitle>
          <CardDescription>
            {t("usage.by_model_desc", "Cost and token breakdown by model")}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {summary?.by_model && summary.by_model.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {[...summary.by_model]
                .sort((a, b) => b.total_cost - a.total_cost)
                .map((model) => (
                  <div 
                    key={`${model.model_platform}/${model.model_type}`} 
                    className="p-4 rounded-lg border bg-card hover:bg-accent/50 transition-colors"
                  >
                    <div className="font-medium text-sm truncate" title={`${model.model_platform} / ${model.model_type}`}>
                      {model.model_type}
                    </div>
                    <div className="mt-2 flex items-center justify-between text-xs text-muted-foreground">
                      <span>{model.total_calls} calls</span>
                      <span>{formatTokens(model.total_tokens)} tokens</span>
                    </div>
                    <div className="mt-2 text-lg font-bold text-green-600">
                      {formatCost(model.total_cost)}
                    </div>
                  </div>
                ))}
            </div>
          ) : (
            <div className="text-center py-8 text-muted-foreground">
              {t("usage.no_model_data", "No model usage data available")}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Recent Activity */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Clock className="w-5 h-5" />
            {t("usage.recent_activity", "Recent Activity")}
          </CardTitle>
          <CardDescription>
            {t("usage.recent_activity_desc", "Latest usage records")}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {recentRecords.length > 0 ? (
            <div className="space-y-2">
              {recentRecords.map((record) => (
                <div 
                  key={record.id}
                  className="flex items-center justify-between p-3 rounded-lg border hover:bg-accent/50 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <div className={`w-2 h-2 rounded-full ${AGENT_COLORS[record.agent_name] || 'bg-gray-500'}`} />
                    <div>
                      <div className="font-medium text-sm">
                        {AGENT_DISPLAY_NAMES[record.agent_name] || record.agent_name}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {record.model_type} • {formatDate(record.created_at)}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-4 text-sm">
                    <Tooltip>
                      <TooltipTrigger>
                        <span className="text-muted-foreground">
                          {formatTokens(record.total_tokens)} tokens
                        </span>
                      </TooltipTrigger>
                      <TooltipContent>
                        <p>Input: {formatTokens(record.input_tokens)}</p>
                        <p>Output: {formatTokens(record.output_tokens)}</p>
                      </TooltipContent>
                    </Tooltip>
                    <span className="font-medium text-green-600">
                      {formatCost(record.estimated_cost)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8 text-muted-foreground">
              {t("usage.no_recent_activity", "No recent activity")}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
