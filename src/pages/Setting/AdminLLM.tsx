import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import {
  AlertCircle,
  Check,
  ChevronDown,
  ChevronUp,
  Copy,
  Database,
  DollarSign,
  Edit2,
  Eye,
  EyeOff,
  Key,
  Loader2,
  Percent,
  Plus,
  RefreshCw,
  Save,
  Server,
  Settings,
  Trash2,
  X,
} from "lucide-react";
import { proxyFetchGet, proxyFetchPost, proxyFetchPut, proxyFetchDelete, fetchPost } from "@/api/http";
import { toast } from "sonner";
import { useTranslation } from "react-i18next";
import { useAuthStore } from "@/store/authStore";

// Types
interface AdminLLMConfig {
  id: number;
  provider_name: string;
  display_name: string;
  api_key_masked: string;
  endpoint_url: string;
  model_type: string;
  extra_config: Record<string, any> | null;
  status: number;
  priority: number;
  rate_limit_rpm: number | null;
  rate_limit_tpm: number | null;
  notes: string;
  created_at: string;
  updated_at: string;
}

interface AdminModelPricing {
  id: number;
  provider_name: string;
  model_name: string;
  display_name: string;
  input_price_per_million: number;
  output_price_per_million: number;
  cost_tier: string;
  context_length: number | null;
  is_available: boolean;
  notes: string;
  created_at: string;
  updated_at: string;
}

interface ConfigFormData {
  provider_name: string;
  display_name: string;
  api_key: string;
  endpoint_url: string;
  model_type: string;
  extra_config: Record<string, any> | null;
  status: number;
  priority: number;
  rate_limit_rpm: number | null;
  rate_limit_tpm: number | null;
  notes: string;
}

interface PricingFormData {
  provider_name: string;
  model_name: string;
  display_name: string;
  input_price_per_million: number;
  output_price_per_million: number;
  cost_tier: string;
  context_length: number | null;
  is_available: boolean;
  notes: string;
}

// Providers whose validation should use "openai-compatible-model" as
// model_platform (they expose OpenAI-compatible endpoints via a gateway).
const OPENAI_COMPATIBLE_PROVIDERS = new Set([
  "hanggent",
  "new-api",
  "openrouter",
  "together",
  "minimax",
  "kimi",
  "z-ai",
  "xai",
]);

// Provider display info
const PROVIDER_INFO: Record<string, { name: string; defaultEndpoint: string }> = {
  hanggent: { name: "Hanggent Api", defaultEndpoint: "https://api.hangent.com/v1" },
  openai: { name: "OpenAI", defaultEndpoint: "https://api.openai.com/v1" },
  anthropic: { name: "Anthropic", defaultEndpoint: "https://api.anthropic.com/v1" },
  google: { name: "Google AI (Gemini)", defaultEndpoint: "https://generativelanguage.googleapis.com/v1beta/openai/" },
  azure: { name: "Azure OpenAI", defaultEndpoint: "" },
  groq: { name: "Groq", defaultEndpoint: "https://api.groq.com/openai/v1" },
  deepseek: { name: "DeepSeek", defaultEndpoint: "https://api.deepseek.com" },
  openrouter: { name: "OpenRouter", defaultEndpoint: "https://openrouter.ai/api/v1" },
  together: { name: "Together AI", defaultEndpoint: "https://api.together.xyz/v1" },
  minimax: { name: "MiniMax", defaultEndpoint: "https://api.minimax.io/v1" },
  kimi: { name: "KIMI (Moonshot)", defaultEndpoint: "https://api.moonshot.ai/v1" },
  "z-ai": { name: "Z.ai", defaultEndpoint: "https://api.z.ai/api/coding/paas/v4/" },
  qwen: { name: "Qwen (Tongyi Qianwen)", defaultEndpoint: "https://dashscope-intl.aliyuncs.com/compatible-mode/v1" },
  xai: { name: "xAI", defaultEndpoint: "https://api.x.ai/v1" },
};

const COST_TIERS = [
  { value: "cheap", label: "Cheap", color: "bg-green-500" },
  { value: "standard", label: "Standard", color: "bg-blue-500" },
  { value: "premium", label: "Premium", color: "bg-purple-500" },
];

const emptyConfigForm: ConfigFormData = {
  provider_name: "",
  display_name: "",
  api_key: "",
  endpoint_url: "",
  model_type: "",
  extra_config: null,
  status: 1,
  priority: 0,
  rate_limit_rpm: null,
  rate_limit_tpm: null,
  notes: "",
};

const emptyPricingForm: PricingFormData = {
  provider_name: "",
  model_name: "",
  display_name: "",
  input_price_per_million: 0,
  output_price_per_million: 0,
  cost_tier: "standard",
  context_length: null,
  is_available: true,
  notes: "",
};

export default function AdminLLM() {
  const { t } = useTranslation();
  const { token } = useAuthStore();

  // LLM Configs state
  const [configs, setConfigs] = useState<AdminLLMConfig[]>([]);
  const [configsLoading, setConfigsLoading] = useState(true);
  const [configDialogOpen, setConfigDialogOpen] = useState(false);
  const [editingConfig, setEditingConfig] = useState<AdminLLMConfig | null>(null);
  const [configForm, setConfigForm] = useState<ConfigFormData>(emptyConfigForm);
  const [showApiKey, setShowApiKey] = useState(false);
  const [configSaving, setConfigSaving] = useState(false);
  const [validating, setValidating] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);

  // Per-config test state: config.id → { loading, result, message, metrics }
  const [testingConfigs, setTestingConfigs] = useState<Record<number, { loading: boolean; result?: "success" | "fail"; message?: string; responseTimeMs?: number; promptTokens?: number; completionTokens?: number; totalTokens?: number }>>({}); 

  // Model Pricing state
  const [pricing, setPricing] = useState<AdminModelPricing[]>([]);
  const [pricingLoading, setPricingLoading] = useState(true);
  const [pricingDialogOpen, setPricingDialogOpen] = useState(false);
  const [editingPricing, setEditingPricing] = useState<AdminModelPricing | null>(null);
  const [pricingForm, setPricingForm] = useState<PricingFormData>(emptyPricingForm);
  const [pricingSaving, setPricingSaving] = useState(false);
  const [pricingFilter, setPricingFilter] = useState<string>("all");

  // Additional Fee state
  const [additionalFeePercent, setAdditionalFeePercent] = useState<number>(5);
  const [feeLoading, setFeeLoading] = useState(false);
  const [feeSaving, setFeeSaving] = useState(false);

  // Access check state
  const [isAdmin, setIsAdmin] = useState<boolean | null>(null);

  // Check admin access
  useEffect(() => {
    if (!token) {
      setIsAdmin(false);
      return;
    }
    // Try to load configs - if we get 403, not admin
    loadConfigs();
  }, [token]);

  // Load LLM configs
  const loadConfigs = async () => {
    setConfigsLoading(true);
    try {
      const res = await proxyFetchGet("/api/admin/llm-configs");
      setConfigs(Array.isArray(res) ? res : []);
      setIsAdmin(true);
    } catch (e: any) {
      console.error("Failed to load admin configs:", e);
      if (e?.status === 403 || e?.detail?.includes("Admin")) {
        setIsAdmin(false);
      } else {
        toast.error("Failed to load LLM configurations");
      }
    } finally {
      setConfigsLoading(false);
    }
  };

  // Load model pricing
  const loadPricing = async () => {
    setPricingLoading(true);
    try {
      const res = await proxyFetchGet("/api/admin/model-pricing");
      setPricing(Array.isArray(res) ? res : []);
    } catch (e: any) {
      console.error("Failed to load pricing:", e);
      toast.error("Failed to load model pricing");
    } finally {
      setPricingLoading(false);
    }
  };

  // Load pricing when admin access confirmed
  useEffect(() => {
    if (isAdmin) {
      loadPricing();
      loadAdditionalFee();
    }
  }, [isAdmin]);

  // Seed defaults
  const seedDefaultConfigs = async () => {
    try {
      const res = await proxyFetchPost("/api/admin/llm-configs/seed-defaults", {});
      toast.success(res.message || "Default configurations seeded");
      loadConfigs();
    } catch (e) {
      console.error("Failed to seed configs:", e);
      toast.error("Failed to seed default configurations");
    }
  };

  const seedDefaultPricing = async () => {
    try {
      const res = await proxyFetchPost("/api/admin/model-pricing/seed-defaults", {});
      toast.success(res.message || "Default pricing seeded");
      loadPricing();
    } catch (e) {
      console.error("Failed to seed pricing:", e);
      toast.error("Failed to seed default pricing");
    }
  };

  // Additional Fee CRUD
  const loadAdditionalFee = async () => {
    setFeeLoading(true);
    try {
      const res = await proxyFetchGet("/api/admin/settings/additional_fee_percent");
      if (res && res.value !== undefined) {
        setAdditionalFeePercent(parseFloat(res.value) || 5);
      }
    } catch (e: any) {
      // If not found or table doesn't exist yet, use default
      console.warn("Could not load additional fee setting, using default 5%", e);
    } finally {
      setFeeLoading(false);
    }
  };

  const saveAdditionalFee = async () => {
    setFeeSaving(true);
    try {
      await proxyFetchPut("/api/admin/settings/additional_fee_percent", {
        value: String(additionalFeePercent),
        description: "Percentage fee added on top of base model token costs for cloud models",
      });
      toast.success(`Additional fee updated to ${additionalFeePercent}%`);
    } catch (e) {
      console.error("Failed to save additional fee:", e);
      toast.error("Failed to save additional fee");
    } finally {
      setFeeSaving(false);
    }
  };

  // Test a saved provider config (sends a live API call via the server)
  const testConfig = async (config: AdminLLMConfig) => {
    setTestingConfigs((prev) => ({ ...prev, [config.id]: { loading: true } }));
    try {
      const result = await proxyFetchPost(
        `/api/admin/llm-configs/${config.id}/validate`,
        {}
      );
      if (result?.is_valid && result?.is_tool_calls) {
        setTestingConfigs((prev) => ({
          ...prev,
          [config.id]: {
            loading: false,
            result: "success",
            message: "Model is working and supports tool calls",
            responseTimeMs: result.response_time_ms,
            promptTokens: result.prompt_tokens,
            completionTokens: result.completion_tokens,
            totalTokens: result.total_tokens,
          },
        }));
        const timePart = result.response_time_ms ? ` (${(result.response_time_ms / 1000).toFixed(1)}s)` : "";
        toast.success(`${config.display_name || config.provider_name}: Test passed${timePart}`, {
          description: "Model responded successfully with tool-call support.",
        });
      } else {
        const msg = result?.message || "Model did not pass validation — may not support function calling.";
        setTestingConfigs((prev) => ({
          ...prev,
          [config.id]: {
            loading: false,
            result: "fail",
            message: msg,
            responseTimeMs: result?.response_time_ms,
            promptTokens: result?.prompt_tokens,
            completionTokens: result?.completion_tokens,
            totalTokens: result?.total_tokens,
          },
        }));
        toast.error(`${config.display_name || config.provider_name}: Test failed`, {
          description: msg,
        });
      }
    } catch (e: any) {
      const msg =
        e?.detail?.message ||
        e?.message ||
        e?.detail ||
        "Test failed — please check API key and endpoint.";
      setTestingConfigs((prev) => ({
        ...prev,
        [config.id]: { loading: false, result: "fail", message: typeof msg === "string" ? msg : JSON.stringify(msg) },
      }));
      toast.error(`${config.display_name || config.provider_name}: Test failed`, {
        description: typeof msg === "string" ? msg : JSON.stringify(msg),
      });
    }
  };

  // Config CRUD
  const openConfigDialog = (config?: AdminLLMConfig) => {
    if (config) {
      setEditingConfig(config);
      setConfigForm({
        provider_name: config.provider_name,
        display_name: config.display_name,
        api_key: "", // Don't pre-fill API key
        endpoint_url: config.endpoint_url,
        model_type: config.model_type || "",
        extra_config: config.extra_config,
        status: config.status,
        priority: config.priority,
        rate_limit_rpm: config.rate_limit_rpm,
        rate_limit_tpm: config.rate_limit_tpm,
        notes: config.notes,
      });
    } else {
      setEditingConfig(null);
      setConfigForm(emptyConfigForm);
    }
    setShowApiKey(false);
    setValidating(false);
    setValidationError(null);
    setConfigDialogOpen(true);
  };

  const saveConfig = async () => {
    if (!configForm.provider_name) {
      toast.error("Provider name is required");
      return;
    }
    if (!editingConfig && !configForm.api_key) {
      toast.error("API key is required for new configurations");
      return;
    }
    if (!configForm.model_type) {
      toast.error("Model type is required");
      return;
    }

    // Determine whether credential-sensitive fields changed (requires re-validation).
    // For edits that only touch cosmetic fields (display_name, status, notes, etc.)
    // we skip the live API validation and save directly.
    const needsValidation = !editingConfig
      || !!configForm.api_key                                           // new API key entered
      || configForm.model_type !== editingConfig.model_type             // model changed
      || configForm.endpoint_url !== editingConfig.endpoint_url;        // endpoint changed

    // ── Step 1: Validate the key before saving (only when credentials changed) ──
    if (needsValidation) {
      setValidating(true);
      setValidationError(null);
      try {
        let validateResult: any;
        if (editingConfig) {
          // Existing config → proxy through Server so stored key stays secret
          validateResult = await proxyFetchPost(
            `/api/admin/llm-configs/${editingConfig.id}/validate`,
            {
              model_type: configForm.model_type,
              ...(configForm.api_key ? { api_key: configForm.api_key } : {}),
            }
          );
        } else {
          // New config → call Backend directly (key is user-typed, no secret)
          // For OpenAI-compatible gateways (e.g. hanggent/new-api), use
          // "openai-compatible-model" so CAMEL creates OpenAICompatibleModel.
          const validationPlatform = OPENAI_COMPATIBLE_PROVIDERS.has(configForm.provider_name)
            ? "openai-compatible-model"
            : configForm.provider_name;
          validateResult = await fetchPost("/model/validate", {
            model_platform: validationPlatform,
            model_type: configForm.model_type,
            api_key: configForm.api_key,
            url: configForm.endpoint_url || undefined,
          });
        }

        if (!validateResult?.is_valid || !validateResult?.is_tool_calls) {
          const msg =
            validateResult?.message ||
            validateResult?.detail?.message ||
            "Validation failed — this model may not support function calling.";
          setValidationError(msg);
          toast.error("Validation failed", { description: msg, closeButton: true });
          return;
        }

        toast.success("Key validated", {
          description: "Model verified — supports function calling.",
          closeButton: true,
        });
      } catch (e: any) {
        const msg =
          e?.detail?.message ||
          e?.message ||
          e?.detail ||
          "Validation failed — please check your API key and model type.";
        setValidationError(typeof msg === "string" ? msg : JSON.stringify(msg));
        toast.error("Validation failed", { description: typeof msg === "string" ? msg : JSON.stringify(msg), closeButton: true });
        return;
      } finally {
        setValidating(false);
      }
    }

    // ── Step 2: Persist (only reached if validation passed or was skipped) ──
    setConfigSaving(true);
    try {
      if (editingConfig) {
        // Update - only include changed fields
        const updateData: any = {};
        if (configForm.display_name !== editingConfig.display_name) updateData.display_name = configForm.display_name;
        if (configForm.api_key) updateData.api_key = configForm.api_key;
        if (configForm.endpoint_url !== editingConfig.endpoint_url) updateData.endpoint_url = configForm.endpoint_url;
        if (configForm.model_type !== editingConfig.model_type) updateData.model_type = configForm.model_type;
        if (configForm.status !== editingConfig.status) updateData.status = configForm.status;
        if (configForm.priority !== editingConfig.priority) updateData.priority = configForm.priority;
        if (configForm.rate_limit_rpm !== editingConfig.rate_limit_rpm) updateData.rate_limit_rpm = configForm.rate_limit_rpm;
        if (configForm.rate_limit_tpm !== editingConfig.rate_limit_tpm) updateData.rate_limit_tpm = configForm.rate_limit_tpm;
        if (configForm.notes !== editingConfig.notes) updateData.notes = configForm.notes;

        await proxyFetchPut(`/api/admin/llm-configs/${editingConfig.id}`, updateData);
        toast.success("Configuration updated");
      } else {
        // Create (backend upserts if provider already exists)
        await proxyFetchPost("/api/admin/llm-configs", configForm);
        toast.success("Configuration saved");
      }
      setConfigDialogOpen(false);
      loadConfigs();
    } catch (e: any) {
      console.error("Failed to save config:", e);
      toast.error(e?.detail || e?.message || "Failed to save configuration");
    } finally {
      setConfigSaving(false);
    }
  };

  const deleteConfig = async (config: AdminLLMConfig) => {
    if (!confirm(`Delete ${config.display_name || config.provider_name} configuration?`)) {
      return;
    }
    try {
      await proxyFetchDelete(`/api/admin/llm-configs/${config.id}`);
      toast.success("Configuration deleted");
      loadConfigs();
    } catch (e) {
      console.error("Failed to delete config:", e);
      toast.error("Failed to delete configuration");
    }
  };

  // Pricing CRUD
  const openPricingDialog = (item?: AdminModelPricing) => {
    if (item) {
      setEditingPricing(item);
      setPricingForm({
        provider_name: item.provider_name,
        model_name: item.model_name,
        display_name: item.display_name,
        input_price_per_million: item.input_price_per_million,
        output_price_per_million: item.output_price_per_million,
        cost_tier: item.cost_tier,
        context_length: item.context_length,
        is_available: item.is_available,
        notes: item.notes,
      });
    } else {
      setEditingPricing(null);
      setPricingForm(emptyPricingForm);
    }
    setPricingDialogOpen(true);
  };

  const savePricing = async () => {
    if (!pricingForm.provider_name || !pricingForm.model_name) {
      toast.error("Provider and model name are required");
      return;
    }

    setPricingSaving(true);
    try {
      if (editingPricing) {
        const updateData = {
          display_name: pricingForm.display_name,
          input_price_per_million: pricingForm.input_price_per_million,
          output_price_per_million: pricingForm.output_price_per_million,
          cost_tier: pricingForm.cost_tier,
          context_length: pricingForm.context_length,
          is_available: pricingForm.is_available,
          notes: pricingForm.notes,
        };
        await proxyFetchPut(`/api/admin/model-pricing/${editingPricing.id}`, updateData);
        toast.success("Pricing updated");
      } else {
        await proxyFetchPost("/api/admin/model-pricing", pricingForm);
        toast.success("Pricing created");
      }
      setPricingDialogOpen(false);
      loadPricing();
    } catch (e: any) {
      console.error("Failed to save pricing:", e);
      toast.error(e?.detail || "Failed to save pricing");
    } finally {
      setPricingSaving(false);
    }
  };

  const deletePricing = async (item: AdminModelPricing) => {
    if (!confirm(`Delete pricing for ${item.model_name}?`)) {
      return;
    }
    try {
      await proxyFetchDelete(`/api/admin/model-pricing/${item.id}`);
      toast.success("Pricing deleted");
      loadPricing();
    } catch (e) {
      console.error("Failed to delete pricing:", e);
      toast.error("Failed to delete pricing");
    }
  };

  // Filter pricing by provider
  const filteredPricing = pricingFilter === "all"
    ? pricing
    : pricing.filter(p => p.provider_name === pricingFilter);

  // Get unique providers from pricing for filter
  const pricingProviders = [...new Set(pricing.map(p => p.provider_name))];

  // Not admin - show access denied
  if (isAdmin === false) {
    return (
      <div className="flex flex-col items-center justify-center py-12">
        <AlertCircle className="w-16 h-16 text-muted-foreground mb-4" />
        <h2 className="text-xl font-semibold mb-2">Admin Access Required</h2>
        <p className="text-muted-foreground text-center max-w-md">
          This page is only accessible to administrators. If you believe you should have access,
          please contact your system administrator.
        </p>
      </div>
    );
  }

  // Loading state
  if (isAdmin === null || configsLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Admin LLM Configuration</h2>
        <p className="text-muted-foreground">
          Manage system-wide LLM provider API keys and model pricing. These settings serve as
          fallbacks for users who haven't configured their own API keys.
        </p>
      </div>

      <Tabs defaultValue="providers" className="space-y-4">
        <TabsList>
          <TabsTrigger value="providers" className="gap-2">
            <Key className="w-4 h-4" />
            Provider API Keys
          </TabsTrigger>
          <TabsTrigger value="pricing" className="gap-2">
            <DollarSign className="w-4 h-4" />
            Model Pricing
          </TabsTrigger>
        </TabsList>

        {/* Provider API Keys Tab */}
        <TabsContent value="providers" className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" onClick={loadConfigs}>
                <RefreshCw className="w-4 h-4 mr-2" />
                Refresh
              </Button>
              <Button variant="outline" size="sm" onClick={seedDefaultConfigs}>
                <Database className="w-4 h-4 mr-2" />
                Seed Defaults
              </Button>
            </div>
            <Button onClick={() => openConfigDialog()}>
              <Plus className="w-4 h-4 mr-2" />
              Add Provider
            </Button>
          </div>

          {configs.length === 0 ? (
            <Card>
              <CardContent className="py-12 text-center">
                <Server className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
                <h3 className="text-lg font-medium mb-2">No Provider Configurations</h3>
                <p className="text-muted-foreground mb-4">
                  Click "Seed Defaults" to create default provider entries, then add your API keys.
                </p>
                <Button onClick={seedDefaultConfigs}>
                  <Database className="w-4 h-4 mr-2" />
                  Seed Default Providers
                </Button>
              </CardContent>
            </Card>
          ) : (
            <div className="grid gap-4">
              {configs.map((config) => (
                <Card key={config.id}>
                  <CardHeader className="pb-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <CardTitle className="text-lg">
                          {config.display_name || PROVIDER_INFO[config.provider_name]?.name || config.provider_name}
                        </CardTitle>
                        <Badge variant={config.status === 1 ? "default" : "secondary"}>
                          {config.status === 1 ? "Enabled" : "Disabled"}
                        </Badge>
                        {config.priority > 0 && (
                          <Badge variant="outline">Priority: {config.priority}</Badge>
                        )}
                      </div>
                      <div className="flex items-center gap-2">
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => testConfig(config)}
                              disabled={testingConfigs[config.id]?.loading || !config.model_type}
                            >
                              {testingConfigs[config.id]?.loading ? (
                                <Loader2 className="w-4 h-4 animate-spin" />
                              ) : testingConfigs[config.id]?.result === "success" ? (
                                <Check className="w-4 h-4 text-green-500" />
                              ) : testingConfigs[config.id]?.result === "fail" ? (
                                <AlertCircle className="w-4 h-4 text-destructive" />
                              ) : (
                                <RefreshCw className="w-4 h-4" />
                              )}
                            </Button>
                          </TooltipTrigger>
                          <TooltipContent>
                            {testingConfigs[config.id]?.loading
                              ? "Testing…"
                              : testingConfigs[config.id]?.message || "Test this provider"}
                          </TooltipContent>
                        </Tooltip>
                        <Button variant="ghost" size="sm" onClick={() => openConfigDialog(config)}>
                          <Edit2 className="w-4 h-4" />
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => deleteConfig(config)}>
                          <Trash2 className="w-4 h-4 text-destructive" />
                        </Button>
                      </div>
                    </div>
                    <CardDescription>{config.provider_name}</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-2 gap-4 text-sm">
                      <div>
                        <span className="text-muted-foreground">API Key:</span>{" "}
                        <code className="bg-muted px-2 py-0.5 rounded">{config.api_key_masked}</code>
                      </div>
                      <div>
                        <span className="text-muted-foreground">Model:</span>{" "}
                        <code className="bg-muted px-2 py-0.5 rounded">
                          {config.model_type || "(not set)"}
                        </code>
                      </div>
                      <div className="col-span-2">
                        <span className="text-muted-foreground">Endpoint:</span>{" "}
                        <code className="bg-muted px-2 py-0.5 rounded text-xs">
                          {config.endpoint_url || "(default)"}
                        </code>
                      </div>
                      {(config.rate_limit_rpm || config.rate_limit_tpm) && (
                        <div className="col-span-2">
                          <span className="text-muted-foreground">Rate Limits:</span>{" "}
                          {config.rate_limit_rpm && <span>{config.rate_limit_rpm} RPM</span>}
                          {config.rate_limit_rpm && config.rate_limit_tpm && " / "}
                          {config.rate_limit_tpm && <span>{config.rate_limit_tpm} TPM</span>}
                        </div>
                      )}
                      {config.notes && (
                        <div className="col-span-2 text-muted-foreground italic">
                          {config.notes}
                        </div>
                      )}
                      {testingConfigs[config.id]?.result && (
                        <div
                          className={`col-span-2 text-xs flex flex-col gap-1 ${
                            testingConfigs[config.id]?.result === "success"
                              ? "text-green-600 dark:text-green-400"
                              : "text-destructive"
                          }`}
                        >
                          <div className="flex items-center gap-1.5">
                            {testingConfigs[config.id]?.result === "success" ? (
                              <Check className="w-3.5 h-3.5" />
                            ) : (
                              <AlertCircle className="w-3.5 h-3.5" />
                            )}
                            {testingConfigs[config.id]?.message}
                          </div>
                          {(testingConfigs[config.id]?.responseTimeMs != null || testingConfigs[config.id]?.totalTokens != null) && (
                            <div className="flex items-center gap-3 text-muted-foreground ml-5">
                              {testingConfigs[config.id]?.responseTimeMs != null && (
                                <span>{(testingConfigs[config.id]!.responseTimeMs! / 1000).toFixed(1)}s</span>
                              )}
                              {testingConfigs[config.id]?.totalTokens != null && (
                                <span>{testingConfigs[config.id]!.totalTokens!.toLocaleString()} tokens</span>
                              )}
                              {testingConfigs[config.id]?.promptTokens != null && testingConfigs[config.id]?.completionTokens != null && (
                                <span className="text-[11px]">
                                  ({testingConfigs[config.id]!.promptTokens!.toLocaleString()} in / {testingConfigs[config.id]!.completionTokens!.toLocaleString()} out)
                                </span>
                              )}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>

        {/* Model Pricing Tab */}
        <TabsContent value="pricing" className="space-y-4">
          {/* Additional Fee Card */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <Percent className="w-4 h-4" />
                Additional Fee
              </CardTitle>
              <CardDescription>
                Percentage markup applied on top of base model rates for all cloud models.
                Formula: <strong>effective price = base price × (1 + fee%)</strong>
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex items-end gap-4">
                <div className="flex-1 max-w-[200px]">
                  <Label htmlFor="additional-fee">Fee Percentage</Label>
                  <div className="relative mt-1.5">
                    <Input
                      id="additional-fee"
                      type="number"
                      min={0}
                      max={100}
                      step={0.1}
                      value={additionalFeePercent}
                      onChange={(e) => setAdditionalFeePercent(parseFloat(e.target.value) || 0)}
                      className="pr-8"
                      disabled={feeLoading}
                    />
                    <span className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground text-sm">%</span>
                  </div>
                </div>
                <Button onClick={saveAdditionalFee} disabled={feeSaving} size="sm">
                  {feeSaving ? (
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  ) : (
                    <Save className="w-4 h-4 mr-2" />
                  )}
                  Save
                </Button>
              </div>
              <p className="text-xs text-muted-foreground mt-3">
                Example: $2.50/1M input with {additionalFeePercent}% fee →{" "}
                <strong>${(2.5 * (1 + additionalFeePercent / 100)).toFixed(2)}/1M</strong> effective price
              </p>
            </CardContent>
          </Card>

          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" onClick={loadPricing}>
                <RefreshCw className="w-4 h-4 mr-2" />
                Refresh
              </Button>
              <Button variant="outline" size="sm" onClick={seedDefaultPricing}>
                <Database className="w-4 h-4 mr-2" />
                Seed Defaults
              </Button>
              <Select value={pricingFilter} onValueChange={setPricingFilter}>
                <SelectTrigger className="w-[180px]">
                  <SelectValue placeholder="Filter by provider" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Providers</SelectItem>
                  {pricingProviders.map((p) => (
                    <SelectItem key={p} value={p}>
                      {PROVIDER_INFO[p]?.name || p}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <Button onClick={() => openPricingDialog()}>
              <Plus className="w-4 h-4 mr-2" />
              Add Pricing
            </Button>
          </div>

          {pricingLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
            </div>
          ) : filteredPricing.length === 0 ? (
            <Card>
              <CardContent className="py-12 text-center">
                <DollarSign className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
                <h3 className="text-lg font-medium mb-2">No Model Pricing</h3>
                <p className="text-muted-foreground mb-4">
                  Click "Seed Defaults" to populate common model pricing data.
                </p>
                <Button onClick={seedDefaultPricing}>
                  <Database className="w-4 h-4 mr-2" />
                  Seed Default Pricing
                </Button>
              </CardContent>
            </Card>
          ) : (
            <Card>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Provider</TableHead>
                    <TableHead>Model</TableHead>
                    <TableHead className="text-right">Input $/1M</TableHead>
                    <TableHead className="text-right">Output $/1M</TableHead>
                    <TableHead>Tier</TableHead>
                    <TableHead className="text-right">Context</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="w-[100px]"></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredPricing.map((item) => (
                    <TableRow key={item.id}>
                      <TableCell className="font-medium">
                        {PROVIDER_INFO[item.provider_name]?.name || item.provider_name}
                      </TableCell>
                      <TableCell>
                        <div>
                          <div className="font-medium">{item.display_name || item.model_name}</div>
                          {item.display_name && (
                            <div className="text-xs text-muted-foreground">{item.model_name}</div>
                          )}
                        </div>
                      </TableCell>
                      <TableCell className="text-right font-mono">
                        ${Number(item.input_price_per_million).toFixed(2)}
                      </TableCell>
                      <TableCell className="text-right font-mono">
                        ${Number(item.output_price_per_million).toFixed(2)}
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant="outline"
                          className={
                            item.cost_tier === "cheap" ? "border-green-500 text-green-600" :
                              item.cost_tier === "premium" ? "border-purple-500 text-purple-600" :
                                "border-blue-500 text-blue-600"
                          }
                        >
                          {item.cost_tier}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right">
                        {item.context_length ? `${(item.context_length / 1000).toFixed(0)}K` : "-"}
                      </TableCell>
                      <TableCell>
                        {item.is_available ? (
                          <Check className="w-4 h-4 text-green-500" />
                        ) : (
                          <X className="w-4 h-4 text-muted-foreground" />
                        )}
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-1">
                          <Button variant="ghost" size="sm" onClick={() => openPricingDialog(item)}>
                            <Edit2 className="w-4 h-4" />
                          </Button>
                          <Button variant="ghost" size="sm" onClick={() => deletePricing(item)}>
                            <Trash2 className="w-4 h-4 text-destructive" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Card>
          )}
        </TabsContent>
      </Tabs>

      {/* Config Dialog */}
      <Dialog open={configDialogOpen} onOpenChange={setConfigDialogOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>
              {editingConfig ? "Edit Provider Configuration" : "Add Provider Configuration"}
            </DialogTitle>
            <DialogDescription>
              Configure API credentials for this LLM provider.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="provider_name">Provider</Label>
              <Select
                value={configForm.provider_name}
                onValueChange={(v) => {
                  setConfigForm({
                    ...configForm,
                    provider_name: v,
                    display_name: PROVIDER_INFO[v]?.name || v,
                    endpoint_url: PROVIDER_INFO[v]?.defaultEndpoint || "",
                  });
                }}
                disabled={!!editingConfig}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select provider" />
                </SelectTrigger>
                <SelectContent>
                  {Object.entries(PROVIDER_INFO).map(([key, info]) => (
                    <SelectItem key={key} value={key}>
                      {info.name}
                    </SelectItem>
                  ))}
                  <SelectItem value="custom">Custom Provider</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="display_name">Display Name</Label>
              <Input
                id="display_name"
                value={configForm.display_name}
                onChange={(e) => setConfigForm({ ...configForm, display_name: e.target.value })}
                placeholder="e.g., OpenAI Production"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="api_key">
                API Key {editingConfig && "(leave blank to keep existing)"}
              </Label>
              <div className="relative">
                <Input
                  id="api_key"
                  type={showApiKey ? "text" : "password"}
                  value={configForm.api_key}
                  onChange={(e) => setConfigForm({ ...configForm, api_key: e.target.value })}
                  placeholder={editingConfig ? "••••••••" : "sk-..."}
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="absolute right-0 top-0 h-full px-3"
                  onClick={() => setShowApiKey(!showApiKey)}
                >
                  {showApiKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </Button>
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="model_type">Model Type</Label>
              <Input
                id="model_type"
                value={configForm.model_type}
                onChange={(e) => {
                  setConfigForm({ ...configForm, model_type: e.target.value });
                  setValidationError(null);
                }}
                placeholder="e.g. gpt-4o"
              />
              {validationError && (
                <p className="text-sm text-destructive">{validationError}</p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="endpoint_url">Endpoint URL</Label>
              <Input
                id="endpoint_url"
                value={configForm.endpoint_url}
                onChange={(e) => setConfigForm({ ...configForm, endpoint_url: e.target.value })}
                placeholder="https://api.example.com/v1"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="rate_limit_rpm">Rate Limit (RPM)</Label>
                <Input
                  id="rate_limit_rpm"
                  type="number"
                  value={configForm.rate_limit_rpm ?? ""}
                  onChange={(e) => setConfigForm({
                    ...configForm,
                    rate_limit_rpm: e.target.value ? parseInt(e.target.value) : null
                  })}
                  placeholder="Requests/min"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="rate_limit_tpm">Rate Limit (TPM)</Label>
                <Input
                  id="rate_limit_tpm"
                  type="number"
                  value={configForm.rate_limit_tpm ?? ""}
                  onChange={(e) => setConfigForm({
                    ...configForm,
                    rate_limit_tpm: e.target.value ? parseInt(e.target.value) : null
                  })}
                  placeholder="Tokens/min"
                />
              </div>
            </div>

            <div className="flex items-center justify-between">
              <Label htmlFor="status">Enabled</Label>
              <Switch
                id="status"
                checked={configForm.status === 1}
                onCheckedChange={(checked) => setConfigForm({ ...configForm, status: checked ? 1 : 0 })}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="notes">Notes</Label>
              <Textarea
                id="notes"
                value={configForm.notes}
                onChange={(e) => setConfigForm({ ...configForm, notes: e.target.value })}
                placeholder="Optional notes about this configuration"
                rows={2}
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setConfigDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={saveConfig} disabled={configSaving || validating}>
              {(validating || configSaving) && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
              {validating ? "Validating…" : configSaving ? "Saving…" : editingConfig ? "Update" : "Validate & Create"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Pricing Dialog */}
      <Dialog open={pricingDialogOpen} onOpenChange={setPricingDialogOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>
              {editingPricing ? "Edit Model Pricing" : "Add Model Pricing"}
            </DialogTitle>
            <DialogDescription>
              Configure pricing information for token usage.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="pricing_provider">Provider</Label>
                <Select
                  value={pricingForm.provider_name}
                  onValueChange={(v) => setPricingForm({ ...pricingForm, provider_name: v })}
                  disabled={!!editingPricing}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select provider" />
                  </SelectTrigger>
                  <SelectContent>
                    {Object.entries(PROVIDER_INFO).map(([key, info]) => (
                      <SelectItem key={key} value={key}>
                        {info.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="model_name">Model Name</Label>
                <Input
                  id="model_name"
                  value={pricingForm.model_name}
                  onChange={(e) => setPricingForm({ ...pricingForm, model_name: e.target.value })}
                  placeholder="gpt-4o"
                  disabled={!!editingPricing}
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="pricing_display_name">Display Name</Label>
              <Input
                id="pricing_display_name"
                value={pricingForm.display_name}
                onChange={(e) => setPricingForm({ ...pricingForm, display_name: e.target.value })}
                placeholder="GPT-4o"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="input_price">Input Price ($/1M tokens)</Label>
                <Input
                  id="input_price"
                  type="number"
                  step="0.01"
                  value={pricingForm.input_price_per_million}
                  onChange={(e) => setPricingForm({
                    ...pricingForm,
                    input_price_per_million: parseFloat(e.target.value) || 0
                  })}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="output_price">Output Price ($/1M tokens)</Label>
                <Input
                  id="output_price"
                  type="number"
                  step="0.01"
                  value={pricingForm.output_price_per_million}
                  onChange={(e) => setPricingForm({
                    ...pricingForm,
                    output_price_per_million: parseFloat(e.target.value) || 0
                  })}
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="cost_tier">Cost Tier</Label>
                <Select
                  value={pricingForm.cost_tier}
                  onValueChange={(v) => setPricingForm({ ...pricingForm, cost_tier: v })}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {COST_TIERS.map((tier) => (
                      <SelectItem key={tier.value} value={tier.value}>
                        {tier.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="context_length">Context Length</Label>
                <Input
                  id="context_length"
                  type="number"
                  value={pricingForm.context_length ?? ""}
                  onChange={(e) => setPricingForm({
                    ...pricingForm,
                    context_length: e.target.value ? parseInt(e.target.value) : null
                  })}
                  placeholder="128000"
                />
              </div>
            </div>

            <div className="flex items-center justify-between">
              <Label htmlFor="is_available">Available</Label>
              <Switch
                id="is_available"
                checked={pricingForm.is_available}
                onCheckedChange={(checked) => setPricingForm({ ...pricingForm, is_available: checked })}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="pricing_notes">Notes</Label>
              <Textarea
                id="pricing_notes"
                value={pricingForm.notes}
                onChange={(e) => setPricingForm({ ...pricingForm, notes: e.target.value })}
                placeholder="Optional notes"
                rows={2}
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setPricingDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={savePricing} disabled={pricingSaving}>
              {pricingSaving && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
              {editingPricing ? "Update" : "Create"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
