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

import {
  proxyFetchGet,
} from '@/api/http';
import { useModelStore } from '@/store/modelStore';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { INIT_PROVODERS } from '@/lib/llm';
import { useAuthStore } from '@/store/authStore';
import { Provider } from '@/types';
import {
  Check,
  ChevronDown,
  ChevronUp,
  Cloud,
  Eye,
  EyeOff,
  Info,
  Key,
  Loader2,
  Plus,
  Server,
  Settings,
  Trash2,
} from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';

// Import model images
import anthropicImage from '@/assets/model/anthropic.svg';
import azureImage from '@/assets/model/azure.svg';
import bedrockImage from '@/assets/model/bedrock.svg';
import deepseekImage from '@/assets/model/deepseek.svg';
import hanggentImage from '@/assets/model/hanggent.svg';
import geminiImage from '@/assets/model/gemini.svg';
import lmstudioImage from '@/assets/model/lmstudio.svg';
import minimaxImage from '@/assets/model/minimax.svg';
import modelarkImage from '@/assets/model/modelark.svg';
import moonshotImage from '@/assets/model/moonshot.svg';
import ollamaImage from '@/assets/model/ollama.svg';
import openaiImage from '@/assets/model/openai.svg';
import openrouterImage from '@/assets/model/openrouter.svg';
import qwenImage from '@/assets/model/qwen.svg';
import sglangImage from '@/assets/model/sglang.svg';
import vllmImage from '@/assets/model/vllm.svg';
import zaiImage from '@/assets/model/zai.svg';

const LOCAL_PROVIDER_NAMES = ['ollama', 'vllm', 'sglang', 'lmstudio'];
const TEMPLATE_PROVIDER_IDS = new Set(INIT_PROVODERS.filter(p => p.id !== 'local').map(p => p.id));
const TEMPLATE_LOCAL_PLATFORMS = new Set(LOCAL_PROVIDER_NAMES);

// Sidebar tab types
type SidebarTab =
  | 'cloud'
  | 'byok'
  | `byok-${string}`
  | 'local'
  | `local-${string}`;

export default function SettingModels() {
  const { modelType, cloud_model_type, setModelType, setCloudModelType, token } =
    useAuthStore();
  const {
    customProviders,
    localProviders,
    migrated,
    setCustomProvider,
    removeCustomProvider,
    setCustomPrefer,
    setLocalProvider,
    removeLocalProvider,
    setLocalPrefer: setLocalPreferStore,
    migrateFromServer,
    setMigrated,
  } = useModelStore();
  const _navigate = useNavigate();
  const { t } = useTranslation();
  const getValidateMessage = (res: any) =>
    res?.message ??
    res?.detail?.message ??
    res?.detail?.error?.message ??
    res?.error?.message ??
    t('setting.validate-failed');
  const [items, _setItems] = useState<Provider[]>(
    INIT_PROVODERS.filter((p) => p.id !== 'local')
  );
  const [form, setForm] = useState(() =>
    INIT_PROVODERS.filter((p) => p.id !== 'local').map((p) => ({
      apiKey: p.apiKey,
      apiHost: p.apiHost,
      is_valid: p.is_valid ?? false,
      model_type: p.model_type ?? '',
      externalConfig: p.externalConfig
        ? p.externalConfig.map((ec) => ({ ...ec }))
        : undefined,
      provider_id: p.provider_id ?? undefined,
      prefer: p.prefer ?? false,
    }))
  );
  const [showApiKey, setShowApiKey] = useState(() =>
    INIT_PROVODERS.filter((p) => p.id !== 'local').map(() => false)
  );
  const [loading, setLoading] = useState<number | null>(null);
  const [errors, setErrors] = useState<
    {
      apiKey?: string;
      apiHost?: string;
      model_type?: string;
      externalConfig?: string;
    }[]
  >(() =>
    INIT_PROVODERS.filter((p) => p.id !== 'local').map(() => ({
      apiKey: '',
      apiHost: '',
    }))
  );
  const [_collapsed, _setCollapsed] = useState(false);

  // Sidebar selected tab - default to cloud
  const [selectedTab, setSelectedTab] = useState<SidebarTab>('cloud');

  // BYOK accordion state
  const [byokCollapsed, setByokCollapsed] = useState(false);

  // Local Model accordion state
  const [localCollapsed, setLocalCollapsed] = useState(false);

  // Local Model independent state - per platform
  const [localEnabled, setLocalEnabled] = useState(true);
  const [localPlatform, setLocalPlatform] = useState('ollama');
  const [localEndpoints, setLocalEndpoints] = useState<Record<string, string>>(
    {}
  );
  const [localTypes, setLocalTypes] = useState<Record<string, string>>({});
  const [localApiKeys, setLocalApiKeys] = useState<Record<string, string>>({});
  const [localShowApiKey, setLocalShowApiKey] = useState<Record<string, boolean>>({});
  const [localVerifying, setLocalVerifying] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const [localInputError, setLocalInputError] = useState(false);
  const [localPrefer, setLocalPrefer] = useState(false); // Local model prefer state (for current platform)

  // Default model dropdown state (removed - using DropdownMenu's built-in state)

  // Pending model to set as default after configuration
  const [pendingDefaultModel, setPendingDefaultModel] = useState<{
    category: 'cloud' | 'custom' | 'local';
    modelId: string;
  } | null>(null);

  const defaultModelTriggerRef = useRef<HTMLButtonElement | null>(null);

  const openDefaultModelSelector = () => {
    const trigger = defaultModelTriggerRef.current;
    if (!trigger) return;
    trigger.focus();
    trigger.click();
  };

  // Dynamic (user-added) custom provider form state
  const [dynamicApiKeys, setDynamicApiKeys] = useState<Record<string, string>>({});
  const [dynamicEndpoints, setDynamicEndpoints] = useState<Record<string, string>>({});
  const [dynamicModelTypes, setDynamicModelTypes] = useState<Record<string, string>>({});
  const [dynamicShowApiKey, setDynamicShowApiKey] = useState<Record<string, boolean>>({});

  // Add provider dialog
  const [addProviderMode, setAddProviderMode] = useState<'custom' | 'local' | null>(null);
  const [newProviderName, setNewProviderName] = useState('');
  const [newProviderEndpoint, setNewProviderEndpoint] = useState('');
  const [newProviderApiKey, setNewProviderApiKey] = useState('');
  const [newProviderModelType, setNewProviderModelType] = useState('');

  // Computed: extra providers not in templates
  const extraCustomIds = Object.keys(customProviders).filter(
    (name) => !TEMPLATE_PROVIDER_IDS.has(name)
  );
  const extraLocalIds = Object.keys(localProviders).filter(
    (name) => !TEMPLATE_LOCAL_PLATFORMS.has(name)
  );

  // Load provider list from localStorage (modelStore) with one-time DB migration
  useEffect(() => {
    (async () => {
      try {
        // One-time migration from server DB to localStorage
        if (!migrated) {
          try {
            const res = await proxyFetchGet('/api/providers');
            const providerList = Array.isArray(res) ? res : res.items || [];
            if (providerList.length > 0) {
              migrateFromServer(providerList);
            } else {
              setMigrated();
            }
          } catch {
            // Server unavailable — just mark migrated so we don't retry
            setMigrated();
          }
        }

        // Now load from modelStore (localStorage)
        const storeState = useModelStore.getState();

        // Populate custom model form from localStorage
        setForm((f) =>
          f.map((fi, idx) => {
            const item = items[idx];
            const stored = storeState.customProviders[item.id];
            if (stored) {
              // Decode base64 API key for display
              let decodedKey = '';
              try { decodedKey = atob(stored.apiKey); } catch { decodedKey = stored.apiKey; }
              return {
                ...fi,
                provider_id: item.id as any, // Use provider name as ID in localStorage mode
                apiKey: decodedKey,
                apiHost: stored.endpoint || '',
                is_valid: stored.isValid,
                prefer: stored.prefer ?? false,
                model_type: stored.modelType ?? '',
                externalConfig: fi.externalConfig
                  ? fi.externalConfig.map((ec) => {
                    if (
                      stored.encryptedConfig &&
                      stored.encryptedConfig[ec.key] !== undefined
                    ) {
                      return { ...ec, value: stored.encryptedConfig[ec.key] };
                    }
                    return ec;
                  })
                  : undefined,
              };
            }
            return fi;
          })
        );

        // Populate local model state from localStorage
        const endpoints: Record<string, string> = {};
        const types: Record<string, string> = {};
        const apiKeysMap: Record<string, string> = {};

        for (const [platform, config] of Object.entries(storeState.localProviders)) {
          endpoints[platform] = config.endpoint || '';
          types[platform] = config.modelType || '';
          let decodedKey = '';
          try { decodedKey = atob(config.apiKey); } catch { decodedKey = config.apiKey; }
          apiKeysMap[platform] = decodedKey;

          if (config.prefer) {
            setLocalPrefer(true);
            setLocalPlatform(platform);
          }
        }

        // Fill in any missing local platforms with empty defaults
        LOCAL_PROVIDER_NAMES.forEach((platform) => {
          if (!endpoints[platform]) {
            endpoints[platform] = '';
            types[platform] = '';
            apiKeysMap[platform] = '';
          }
        });

        setLocalEndpoints(endpoints);
        setLocalTypes(types);
        setLocalApiKeys(apiKeysMap);

        // Populate dynamic custom provider form state from localStorage
        const dynKeys: Record<string, string> = {};
        const dynEndpoints: Record<string, string> = {};
        const dynTypes: Record<string, string> = {};
        for (const [name, config] of Object.entries(storeState.customProviders)) {
          if (!TEMPLATE_PROVIDER_IDS.has(name)) {
            let dk = '';
            try { dk = atob(config.apiKey); } catch { dk = config.apiKey; }
            dynKeys[name] = dk;
            dynEndpoints[name] = config.endpoint || '';
            dynTypes[name] = config.modelType || '';
          }
        }
        setDynamicApiKeys(dynKeys);
        setDynamicEndpoints(dynEndpoints);
        setDynamicModelTypes(dynTypes);

        if (modelType === 'cloud') {
          setForm((f) => f.map((fi) => ({ ...fi, prefer: false })));
          setLocalPrefer(false);
        } else if (modelType === 'local') {
          setLocalEnabled(true);
          setForm((f) => f.map((fi) => ({ ...fi, prefer: false })));
          setLocalPrefer(true);
        } else if (modelType === 'custom') {
          // Restore activeModelIdx for custom (BYOK) mode
          setLocalPrefer(false);
          setForm((prev) => {
            const idx = prev.findIndex((fi) => fi.prefer);
            if (idx >= 0) {
              setActiveModelIdx(idx);
            }
            return prev;
          });
        } else {
          setLocalPrefer(false);
        }
      } catch (e) {
        console.error('Error loading providers from localStorage:', e);
      }
    })();

    if (import.meta.env.VITE_USE_LOCAL_PROXY !== 'true') {
      fetchSubscription();
      updateCredits();
    }
  }, [items, modelType, migrated]);

  // Get current default model display text
  const getDefaultModelDisplayText = (): string => {
    if (modelType === 'cloud') {
      const cloudModel = cloudModelOptions.find(
        (m) => m.id === cloud_model_type
      );
      const modelName = cloudModel
        ? cloudModel.name
        : cloud_model_type
          .replace(/-/g, ' ')
          .replace(/\b\w/g, (c) => c.toUpperCase());
      return `${t('setting.hanggent-cloud')} / ${modelName}`;
    }

    if (modelType === 'custom') {
      // Check for custom model preference
      const preferredIdx = form.findIndex((f) => f.prefer);
      if (preferredIdx !== -1) {
        const item = items[preferredIdx];
        const byokModelType = form[preferredIdx].model_type || '';
        return `${t('setting.custom-model')} / ${item.name}${byokModelType ? ` (${byokModelType})` : ''}`;
      }
      return t('setting.custom-model');
    }

    if (modelType === 'local') {
      if (localPlatform) {
        const localModel = localModelOptions.find((m) => m.id === localPlatform);
        const platformName = localModel
          ? localModel.name
          : localPlatform === 'ollama'
            ? 'Ollama'
            : localPlatform === 'vllm'
              ? 'vLLM'
              : localPlatform === 'sglang'
                ? 'SGLang'
                : 'LM Studio';
        const localModelType = localTypes[localPlatform] || '';
        return `${t('setting.local-model')} / ${platformName}${localModelType ? ` (${localModelType})` : ''}`;
      }
      return t('setting.local-model');
    }

    return t('setting.select-default-model');
  };

  // Check if a model is configured
  const isModelConfigured = (
    category: 'cloud' | 'custom' | 'local',
    modelId: string
  ): boolean => {
    if (category === 'cloud') {
      return import.meta.env.VITE_USE_LOCAL_PROXY !== 'true';
    }
    if (category === 'custom') {
      const templateIdx = items.findIndex((item) => item.id === modelId);
      if (templateIdx !== -1) {
        const templateForm = form[templateIdx];
        return !!templateForm?.provider_id && !!templateForm?.apiHost?.trim();
      }
      const stored = customProviders[modelId];
      return !!stored && !!stored.endpoint;
    }
    if (category === 'local') {
      const stored = localProviders[modelId];
      return !!stored && !!stored.endpoint;
    }
    return false;
  };

  const isAnthropicEndpoint = (endpoint: string): boolean =>
    endpoint.toLowerCase().includes('api.anthropic.com');

  const isClaudeModel = (modelType: string): boolean =>
    modelType.toLowerCase().startsWith('claude-');

  const normalizeOpenAICompatibleEndpoint = (endpoint: string): string => {
    const trimmed = endpoint.trim();
    const normalized = trimmed.replace(/\/+$/, '');
    const lower = normalized.toLowerCase();

    if (lower === 'https://api.minimax.io') {
      return 'https://api.minimax.io/v1';
    }
    if (lower === 'https://api.moonshot.ai') {
      return 'https://api.moonshot.ai/v1';
    }
    if (lower === 'https://open.bigmodel.cn' || lower === 'https://bigmodel.cn') {
      return 'https://open.bigmodel.cn/api/paas/v4/';
    }
    return trimmed;
  };

  const normalizeProviderEndpoint = (
    providerId: string,
    endpoint: string
  ): string => {
    const trimmed = endpoint.trim();
    const normalized = trimmed.replace(/\/+$/, '');

    if (providerId === 'anthropic') {
      if (normalized === 'https://api.anthropic.com') {
        return 'https://api.anthropic.com/v1';
      }
      return trimmed;
    }

    if (
      providerId === 'openai-compatible-model' ||
      providerId === 'minimax' ||
      providerId === 'kimi' ||
      providerId === 'glm'
    ) {
      return normalizeOpenAICompatibleEndpoint(trimmed);
    }

    return trimmed;
  };

  const getProviderCompatibilityError = (
    providerId: string,
    endpoint: string,
    modelType: string
  ): string | null => {
    if (providerId !== 'openai-compatible-model') return null;
    if (!isAnthropicEndpoint(endpoint) && !isClaudeModel(modelType)) return null;
    return t(
      'setting.provider-mismatch-anthropic',
      'This configuration looks like Anthropic. Please use the Anthropic provider card, or switch to a non-Anthropic OpenAI-compatible endpoint/model.'
    );
  };

  // Handle model selection from dropdown
  const handleDefaultModelSelect = async (
    category: 'cloud' | 'custom' | 'local',
    modelId: string
  ) => {
    const configured = isModelConfigured(category, modelId);

    if (!configured) {
      // Store pending model to set as default after configuration
      setPendingDefaultModel({ category, modelId });

      // Navigate to the appropriate tab for configuration
      if (category === 'cloud') {
        setSelectedTab('cloud');
      } else if (category === 'custom') {
        setSelectedTab(`byok-${modelId}` as SidebarTab);
        // Expand BYOK section if collapsed
        if (byokCollapsed) setByokCollapsed(false);
      } else if (category === 'local') {
        setSelectedTab(`local-${modelId}` as SidebarTab);
        // Expand Local section if collapsed
        if (localCollapsed) setLocalCollapsed(false);
      }
      return;
    }

    // Model is configured, set it as default
    await setModelAsDefault(category, modelId);
  };

  // Set a model as the default
  const setModelAsDefault = async (
    category: 'cloud' | 'custom' | 'local',
    modelId: string
  ) => {
    if (category === 'cloud') {
      setLocalPrefer(false);
      setActiveModelIdx(null);
      setForm((f) => f.map((fi) => ({ ...fi, prefer: false })));
      setModelType('cloud');
      // Clear modelStore preferences so custom/local don't persist across reloads
      setCustomPrefer(null as unknown as string);
      setLocalPreferStore(null);
      const targetCloudModel = modelId === 'cloud' ? cloud_model_type : modelId;
      if (targetCloudModel) {
        setCloudModelType(targetCloudModel as any);
      }
    } else if (category === 'custom') {
      const idx = items.findIndex((item) => item.id === modelId);
      if (idx !== -1) {
        await handleSwitch(idx, true);
      } else if (customProviders[modelId]?.endpoint) {
        // Dynamic custom provider
        setCustomPrefer(modelId);
        setModelType('custom');
        setActiveModelIdx(null);
        setLocalEnabled(false);
        setLocalPrefer(false);
        setLocalPreferStore(null);
        setForm((f) => f.map((fi) => ({ ...fi, prefer: false })));
      }
    } else if (category === 'local') {
      await handleLocalSwitch(true, modelId);
    }
    setPendingDefaultModel(null);
  };

  // Cloud model options — loaded dynamically from backend config
  const [cloudModelOptions, setCloudModelOptions] = useState<
    { id: string; name: string }[]
  >([]);
  const [cloudOptionsLoading, setCloudOptionsLoading] = useState(false);
  const [cloudOptionsError, setCloudOptionsError] = useState<string | null>(
    null
  );

  // Fetch cloud model options from admin config once auth is ready.
  // Retry once to avoid token-hydration race on production web login.
  useEffect(() => {
    if (import.meta.env.VITE_USE_LOCAL_PROXY === 'true') {
      setCloudModelOptions([]);
      setCloudOptionsError(null);
      return;
    }

    if (!token) {
      return;
    }

    let cancelled = false;

    const toOptions = (res: any) => {
      if (
        res &&
        typeof res === 'object' &&
        !Array.isArray(res) &&
        ((res.code === 13 && typeof res.text === 'string') ||
          String(res.text || '')
            .toLowerCase()
            .includes('could not validate credentials'))
      ) {
        throw new Error('AUTH_INVALID');
      }

      const providers =
        (Array.isArray(res) ? res : null) ??
        (Array.isArray((res as any)?.items) ? (res as any).items : null) ??
        (Array.isArray((res as any)?.data) ? (res as any).data : null) ??
        [];

      return providers.map((p: any) => ({
        id: p.model_type || p.provider_name,
        name: p.display_name || p.provider_name,
      }));
    };

    const fetchOnce = async () => {
      const res = await proxyFetchGet('/api/cloud/available-providers');
      return toOptions(res);
    };

    (async () => {
      setCloudOptionsLoading(true);
      setCloudOptionsError(null);
      try {
        let opts = await fetchOnce();
        if (opts.length === 0) {
          await new Promise((resolve) => setTimeout(resolve, 300));
          opts = await fetchOnce();
        }

        if (cancelled) return;

        setCloudModelOptions(opts);

        // If current cloud_model_type is empty or not in the list, auto-select first
        if (
          opts.length > 0 &&
          (!cloud_model_type ||
            !opts.some((o: { id: string }) => o.id === cloud_model_type))
        ) {
          setCloudModelType(opts[0].id);
        }

        if (opts.length === 0) {
          setCloudOptionsError(
            t(
              'setting.no-enabled-cloud-providers',
              'No enabled cloud providers configured by admin.'
            )
          );
        }
      } catch (error: any) {
        if (cancelled) return;
        setCloudModelOptions([]);
        if (error?.message === 'AUTH_INVALID') {
          setCloudOptionsError(
            t(
              'setting.failed-to-load-cloud-providers-auth',
              'Authentication expired. Please sign in again.'
            )
          );
        } else {
          setCloudOptionsError(
            t(
              'setting.failed-to-load-cloud-providers',
              'Failed to load cloud providers. Please try again later.'
            )
          );
        }
      } finally {
        if (!cancelled) {
          setCloudOptionsLoading(false);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [cloud_model_type, setCloudModelType, t, token]);

  // Local model options
  const localModelOptions = [
    { id: 'ollama', name: 'Ollama' },
    { id: 'vllm', name: 'vLLM' },
    { id: 'sglang', name: 'SGLang' },
    { id: 'lmstudio', name: 'LM Studio' },
  ];

  const handleVerify = async (idx: number) => {
    const { apiKey, apiHost, externalConfig, model_type } =
      form[idx];
    let hasError = false;
    const newErrors = [...errors];
    if (items[idx].id !== 'local') {
      if (!apiKey || apiKey.trim() === '') {
        newErrors[idx].apiKey = t('setting.api-key-can-not-be-empty');
        hasError = true;
      } else {
        newErrors[idx].apiKey = '';
      }
    }
    if (!apiHost || apiHost.trim() === '') {
      newErrors[idx].apiHost = t('setting.api-host-can-not-be-empty');
      hasError = true;
    } else {
      newErrors[idx].apiHost = '';
    }
    if (!model_type || model_type.trim() === '') {
      newErrors[idx].model_type = t('setting.model-type-can-not-be-empty');
      hasError = true;
    } else {
      newErrors[idx].model_type = '';
    }
    setErrors(newErrors);
    if (hasError) return;

    const item = items[idx];
    const normalizedApiHost = normalizeProviderEndpoint(item.id, apiHost);
    const compatibilityError = getProviderCompatibilityError(
      item.id,
      normalizedApiHost,
      model_type
    );
    if (compatibilityError) {
      toast.error(compatibilityError);
      return;
    }

    setLoading(idx);
    let external: any = {};
    if (form[idx]?.externalConfig) {
      form[idx]?.externalConfig.map((item) => {
        external[item.key] = item.value;
      });
    }

    try {
      // Save to localStorage via modelStore (no server validation)
      setCustomProvider(item.id, {
        apiKey: apiKey.trim(),
        endpoint: normalizedApiHost,
        modelType: model_type.trim(),
        providerName: item.id,
        encryptedConfig: Object.keys(external).length > 0 ? external : undefined,
        isValid: true,
        prefer: false,
      });

      // Update form state to reflect saved status
      setForm((f) =>
        f.map((fi, i) => {
          if (i !== idx) return fi;
          return {
            ...fi,
            provider_id: item.id as any,
            apiHost: normalizedApiHost,
            is_valid: true,
          };
        })
      );

      toast.success(t('setting.save-success', 'Configuration saved'));

      // Check if this was a pending default model selection
      if (
        pendingDefaultModel &&
        pendingDefaultModel.category === 'custom' &&
        pendingDefaultModel.modelId === item.id
      ) {
        await handleSwitch(idx, true);
        setPendingDefaultModel(null);
      }
      // No longer auto-set-as-default on every save;
      // user must explicitly click "Set as Default".
    } finally {
      setLoading(null);
    }
  };

  // Local Model verification
  const handleLocalVerify = async () => {
    setLocalVerifying(true);
    setLocalError(null);
    setLocalInputError(false);
    const targetPlatform = selectedTab.startsWith('local-')
      ? selectedTab.replace('local-', '')
      : localPlatform;
    const currentEndpoint = localEndpoints[targetPlatform] || '';
    const currentType = localTypes[targetPlatform] || '';
    const currentApiKey = localApiKeys[targetPlatform] || '';

    if (!currentEndpoint) {
      setLocalError(t('setting.endpoint-url-can-not-be-empty'));
      setLocalInputError(true);
      setLocalVerifying(false);
      return;
    }

    if (!currentType.trim()) {
      setLocalError(t('setting.model-type-can-not-be-empty'));
      setLocalInputError(true);
      setLocalVerifying(false);
      return;
    }

    try {
      // Save to localStorage via modelStore (no server validation)
      setLocalProvider(targetPlatform, {
        endpoint: currentEndpoint.trim(),
        modelType: currentType.trim(),
        apiKey: currentApiKey.trim(),
        platform: targetPlatform,
        isValid: true,
        prefer: false,
      });

      setLocalError(null);
      setLocalInputError(false);

      toast.success(t('setting.save-success', 'Configuration saved'));

      // Only switch to default if explicitly requested via pending default model
      if (
        pendingDefaultModel &&
        pendingDefaultModel.category === 'local' &&
        pendingDefaultModel.modelId === targetPlatform
      ) {
        handleLocalSwitch(true, targetPlatform);
        setPendingDefaultModel(null);
      }
    } catch (e: any) {
      setLocalError(
        e.message || t('setting.verification-failed-please-check-endpoint-url')
      );
      setLocalInputError(true);
    } finally {
      setLocalVerifying(false);
    }
  };

  const [activeModelIdx, setActiveModelIdx] = useState<number | null>(null); // Current active model idx

  // Switch linkage logic: only one switch can be enabled
  useEffect(() => {
    if (activeModelIdx !== null) {
      setLocalEnabled(false);
    } else {
      setLocalEnabled(true);
    }
  }, [activeModelIdx]);
  useEffect(() => {
    if (localEnabled) {
      setActiveModelIdx(null);
    }
  }, [localEnabled]);

  const handleSwitch = async (idx: number, checked: boolean) => {
    if (!checked) {
      setActiveModelIdx(null);
      setLocalEnabled(true);
      return;
    }
    try {
      // Save prefer to localStorage via modelStore
      const providerName = items[idx].id;
      setCustomPrefer(providerName);
      setModelType('custom');
      setActiveModelIdx(idx);
      setLocalEnabled(false);
      setForm((f) => f.map((fi, i) => ({ ...fi, prefer: i === idx }))); // Only one prefer allowed
      setLocalPrefer(false);
      setLocalPreferStore(null);

      void checkHasSearchKey().then((hasSearchKey) => {
        if (!hasSearchKey) {
          // Show warning toast instead of blocking
          toast(t('setting.warning-google-search-not-configured'), {
            description: t(
              'setting.search-functionality-may-be-limited-without-google-api'
            ),
            closeButton: true,
          });
        }
      });
    } catch (e) {
      console.error('Error switching model:', e);
    }
  };
  const handleLocalSwitch = async (
    checked: boolean,
    platformOverride?: string
  ) => {
    const targetPlatform = platformOverride || localPlatform;
    if (!checked) {
      setLocalEnabled(false);
      setLocalPrefer(false);
      return;
    }
    try {
      // Save prefer to localStorage via modelStore
      setLocalPreferStore(targetPlatform);
      setLocalPlatform(targetPlatform);
      setModelType('local');
      setLocalEnabled(true);
      setActiveModelIdx(null);
      setCustomPrefer(null as unknown as string); // Clear custom prefer in modelStore
      setForm((f) => f.map((fi) => ({ ...fi, prefer: false }))); // Set all others' prefer to false
      setLocalPrefer(true);

      void checkHasSearchKey().then((hasSearchKey) => {
        if (!hasSearchKey) {
          // Show warning toast instead of blocking
          toast(t('setting.warning-google-search-not-configured'), {
            description: t(
              'setting.search-functionality-may-be-limited-without-google-api'
            ),
            closeButton: true,
          });
        }
      });
    } catch (e) {
      console.error('Error switching local model:', e);
    }
  };

  const handleLocalReset = async (platformOverride?: string) => {
    const targetPlatform = platformOverride || localPlatform;
    const isDynamic = !TEMPLATE_LOCAL_PLATFORMS.has(targetPlatform);
    try {
      removeLocalProvider(targetPlatform);
      if (isDynamic) {
        // Fully remove dynamic local provider
        setLocalEndpoints((prev) => { const { [targetPlatform]: _, ...rest } = prev; return rest; });
        setLocalTypes((prev) => { const { [targetPlatform]: _, ...rest } = prev; return rest; });
        setLocalApiKeys((prev) => { const { [targetPlatform]: _, ...rest } = prev; return rest; });
        setSelectedTab('cloud');
      } else {
        setLocalEndpoints((prev) => ({ ...prev, [targetPlatform]: '' }));
        setLocalTypes((prev) => ({ ...prev, [targetPlatform]: '' }));
        setLocalApiKeys((prev) => ({ ...prev, [targetPlatform]: '' }));
      }
      if (localPrefer && localPlatform === targetPlatform) {
        setLocalPrefer(false);
      }
      setLocalEnabled(true);
      setActiveModelIdx(null);
      toast.success(t('setting.reset-success'));
    } catch (e) {
      console.error('Error resetting local model:', e);
      toast.error(t('setting.reset-failed'));
    }
  };
  const handleDelete = async (idx: number) => {
    try {
      const item = items[idx];
      // Remove from localStorage via modelStore
      removeCustomProvider(item.id);
      // reset single form entry to default empty values
      setForm((prev) =>
        prev.map((fi, i) => {
          if (i !== idx) return fi;
          const item = items[i];
          return {
            apiKey: '',
            apiHost: '',
            is_valid: false,
            model_type: '',
            externalConfig: item.externalConfig
              ? item.externalConfig.map((ec) => ({ ...ec, value: '' }))
              : undefined,
            provider_id: undefined,
            prefer: false,
          };
        })
      );
      setErrors((prev) =>
        prev.map((er, i) =>
          i === idx ? ({ apiKey: '', apiHost: '', model_type: '' } as any) : er
        )
      );
      if (activeModelIdx === idx) {
        setActiveModelIdx(null);
        setLocalEnabled(true);
      }
      toast.success(t('setting.reset-success'));
    } catch (e) {
      console.error('Error deleting model:', e);
      toast.error(t('setting.reset-failed'));
    }
  };

  // Dynamic custom provider CRUD
  const handleDynamicCustomSave = (providerId: string) => {
    const apiKey = dynamicApiKeys[providerId] || '';
    const endpoint = dynamicEndpoints[providerId] || '';
    const mtype = dynamicModelTypes[providerId] || '';
    if (!endpoint.trim()) { toast.error(t('setting.api-host-can-not-be-empty')); return; }
    if (!mtype.trim()) { toast.error(t('setting.model-type-can-not-be-empty')); return; }
    const normalizedEndpoint = normalizeProviderEndpoint(providerId, endpoint);
    const compatibilityError = getProviderCompatibilityError(
      providerId,
      normalizedEndpoint,
      mtype
    );
    if (compatibilityError) { toast.error(compatibilityError); return; }
    setCustomProvider(providerId, {
      apiKey: apiKey.trim(), endpoint: normalizedEndpoint, modelType: mtype.trim(),
      providerName: providerId, isValid: true, prefer: false,
    });
    setDynamicEndpoints((prev) => ({ ...prev, [providerId]: normalizedEndpoint }));
    toast.success(t('setting.save-success', 'Configuration saved'));
  };

  const handleDynamicCustomDelete = (providerId: string) => {
    removeCustomProvider(providerId);
    setDynamicApiKeys((prev) => { const { [providerId]: _, ...rest } = prev; return rest; });
    setDynamicEndpoints((prev) => { const { [providerId]: _, ...rest } = prev; return rest; });
    setDynamicModelTypes((prev) => { const { [providerId]: _, ...rest } = prev; return rest; });
    setSelectedTab('cloud');
    toast.success(t('setting.reset-success'));
  };

  const handleAddProvider = () => {
    const name = newProviderName.trim();
    if (!name) return;
    const id = name.toLowerCase().replace(/\s+/g, '-');
    if (addProviderMode === 'custom') {
      if (TEMPLATE_PROVIDER_IDS.has(id) || customProviders[id]) {
        toast.error('Provider already exists'); return;
      }
      const normalizedEndpoint = normalizeProviderEndpoint(id, newProviderEndpoint);
      setCustomProvider(id, {
        apiKey: newProviderApiKey.trim(), endpoint: normalizedEndpoint,
        modelType: newProviderModelType.trim(), providerName: id,
        isValid: !!normalizedEndpoint.trim(), prefer: false,
      });
      setDynamicApiKeys((prev) => ({ ...prev, [id]: newProviderApiKey.trim() }));
      setDynamicEndpoints((prev) => ({ ...prev, [id]: normalizedEndpoint }));
      setDynamicModelTypes((prev) => ({ ...prev, [id]: newProviderModelType.trim() }));
      setSelectedTab(`byok-${id}` as SidebarTab);
    } else {
      if (TEMPLATE_LOCAL_PLATFORMS.has(id) || localProviders[id]) {
        toast.error('Provider already exists'); return;
      }
      setLocalProvider(id, {
        endpoint: newProviderEndpoint.trim(), modelType: newProviderModelType.trim(),
        apiKey: newProviderApiKey.trim(), platform: id,
        isValid: !!newProviderEndpoint.trim(), prefer: false,
      });
      setLocalEndpoints((prev) => ({ ...prev, [id]: newProviderEndpoint.trim() }));
      setLocalTypes((prev) => ({ ...prev, [id]: newProviderModelType.trim() }));
      setLocalApiKeys((prev) => ({ ...prev, [id]: newProviderApiKey.trim() }));
      setSelectedTab(`local-${id}` as SidebarTab);
    }
    setAddProviderMode(null);
    setNewProviderName(''); setNewProviderEndpoint(''); setNewProviderApiKey(''); setNewProviderModelType('');
    toast.success('Provider added');
  };

  const checkHasSearchKey = async () => {
    const configsRes = await proxyFetchGet('/api/configs');
    const configs = Array.isArray(configsRes) ? configsRes : [];
    console.log(configsRes, configs);
    const _hasApiKey = configs.find(
      (item) => item.config_name === 'GOOGLE_API_KEY'
    );
    const _hasApiId = configs.find(
      (item) => item.config_name === 'SEARCH_ENGINE_ID'
    );
    return _hasApiKey && _hasApiId;
  };

  const [subscription, setSubscription] = useState<any>(null);
  const fetchSubscription = async () => {
    try {
      const res = await proxyFetchGet('/api/payment/subscription');
      if (res && !res.detail) {
        setSubscription(res);
      }
    } catch (error) {
      console.error('Failed to load subscription:', error);
    }
  };
  const [credits, setCredits] = useState<any>(0);
  const [loadingCredits, setLoadingCredits] = useState(false);
  const updateCredits = async () => {
    try {
      setLoadingCredits(true);
      const res = await proxyFetchGet(`/api/user/current_credits`);
      console.log(res?.credits);
      setCredits(res?.credits);
    } catch (error) {
      console.error(error);
    } finally {
      setLoadingCredits(false);
    }
  };

  // Helper to get model image based on model ID
  const getModelImage = (modelId: string | null): string | null => {
    if (!modelId) return null;
    const modelImageMap: Record<string, string> = {
      // Cloud version
      cloud: hanggentImage,
      // Cloud models
      openai: openaiImage,
      anthropic: anthropicImage,
      gemini: geminiImage,
      openrouter: openrouterImage,
      'tongyi-qianwen': qwenImage,
      deepseek: deepseekImage,
      minimax: minimaxImage,
      'Z.ai': zaiImage,
      kimi: moonshotImage,
      moonshot: moonshotImage,
      glm: openaiImage,
      bigmodel: openaiImage,
      ModelArk: modelarkImage,
      'aws-bedrock': bedrockImage,
      azure: azureImage,
      'openai-compatible-model': openaiImage, // Use OpenAI icon as fallback
      xai: openaiImage, // xAI uses OpenAI-compatible API
      // Local models
      ollama: ollamaImage,
      vllm: vllmImage,
      sglang: sglangImage,
      lmstudio: lmstudioImage,
      // Local model tab IDs
      'local-ollama': ollamaImage,
      'local-vllm': vllmImage,
      'local-sglang': sglangImage,
      'local-lmstudio': lmstudioImage,
    };
    return modelImageMap[modelId] || null;
  };

  // Helper to render sidebar tab item
  const renderSidebarItem = (
    tabId: SidebarTab,
    label: string,
    modelId: string | null,
    isActive: boolean,
    isSubItem: boolean = false,
    isConfigured: boolean = false
  ) => {
    const modelImage = getModelImage(modelId);
    const fallbackIcon =
      modelId === 'cloud' ? (
        <Cloud className="h-5 w-5" />
      ) : modelId?.startsWith('local') ? (
        <Server className="h-5 w-5" />
      ) : (
        <Key className="h-5 w-5" />
      );

    return (
      <button
        key={tabId}
        onClick={() => setSelectedTab(tabId)}
        className={`flex w-full items-center justify-between rounded-xl px-3 py-2 transition-all duration-200 ${isSubItem ? 'pl-3' : ''} ${isActive
          ? 'bg-fill-fill-transparent-active'
          : 'bg-fill-fill-transparent hover:bg-fill-fill-transparent-hover'
          } `}
      >
        <div className="flex items-center justify-center gap-3">
          {modelImage ? (
            <img src={modelImage} alt={label} className="h-5 w-5" />
          ) : (
            <span className={isActive ? 'text-text-body' : 'text-text-label'}>
              {fallbackIcon}
            </span>
          )}
          <span
            className={`text-body-sm font-medium ${isActive ? 'text-text-body' : 'text-text-label'}`}
          >
            {label}
          </span>
        </div>
        {isConfigured && (
          <div className="m-1 h-2 w-2 rounded-full bg-text-success" />
        )}
      </button>
    );
  };

  // Render content based on selected tab
  const renderContent = () => {
    // Cloud version content
    if (selectedTab === 'cloud') {
      if (import.meta.env.VITE_USE_LOCAL_PROXY === 'true') {
        return (
          <div className="flex h-64 items-center justify-center text-text-label">
            {t('setting.cloud-not-available-in-local-proxy')}
          </div>
        );
      }
      return (
        <div className="flex w-full flex-col rounded-2xl bg-surface-tertiary">
          <div className="mx-6 mb-4 flex flex-col justify-start self-stretch border-x-0 border-b-[0.5px] border-t-0 border-solid border-border-secondary pb-4 pt-2">
            <div className="inline-flex items-center justify-start gap-2 self-stretch">
              <div className="text-body-base my-2 flex-1 justify-center font-bold text-text-heading">
                {t('setting.hanggent-cloud')}
              </div>
              {modelType === 'cloud' ? (
                <Button
                  variant="success"
                  size="xs"
                  className="focus-none rounded-full"
                  onClick={() => {
                    openDefaultModelSelector();
                  }}
                >
                  {t('setting.default')}
                </Button>
              ) : (
                <Button
                  variant="ghost"
                  size="xs"
                  className="rounded-full !text-text-label"
                  onClick={() =>
                    handleDefaultModelSelect(
                      'cloud',
                      cloud_model_type || cloudModelOptions[0]?.id || 'cloud'
                    )
                  }
                >
                  {t('setting.set-as-default')}
                </Button>
              )}
            </div>
            <div className="justify-center self-stretch">
              <span className="text-body-sm text-text-label">
                {t('setting.you-are-currently-subscribed-to-the')}{' '}
                {subscription?.plan
                  ? subscription.plan.charAt(0).toUpperCase() + subscription.plan.slice(1)
                  : ''}
                . {t('setting.discover-more-about-our')}{' '}
              </span>
              <span
                onClick={() => {
                  window.location.href = `https://www.hangent.com/pricing`;
                }}
                className="cursor-pointer text-body-sm text-text-label underline"
              >
                {t('setting.pricing-options')}
              </span>
              <span className="text-label-sm font-normal text-text-body">
                .
              </span>
            </div>
          </div>
          {/*Content Area*/}
          <div className="flex w-full flex-row items-center justify-between gap-4 px-6 pb-4">
            <div className="text-body-sm text-text-body">
              {t('setting.credits')}:{' '}
              {loadingCredits ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                `$${Number(credits || 0).toFixed(2)}`
              )}
            </div>
            <Button
              onClick={() => {
                window.location.href = `https://www.hangent.com/dashboard`;
              }}
              variant="primary"
              size="sm"
            >
              {loadingCredits ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                subscription?.plan
                  ? subscription.plan.charAt(0).toUpperCase() + subscription.plan.slice(1)
                  : ''
              )}
              <Settings />
            </Button>
          </div>
          <div className="flex w-full flex-1 items-center justify-between px-6 pb-4">
            <div className="flex min-w-0 flex-1 items-center">
              <span className="overflow-hidden text-ellipsis whitespace-nowrap text-body-sm">
                {t('setting.select-model-type')}
              </span>
              <Tooltip>
                <TooltipTrigger asChild>
                  <span className="ml-1 inline-flex cursor-pointer items-center">
                    <Info className="h-4 w-4 text-icon-secondary" />
                  </span>
                </TooltipTrigger>
                <TooltipContent
                  side="top"
                  className="flex min-h-[40px] min-w-[220px] items-center justify-center text-center"
                >
                  <span className="flex w-full items-center justify-center">
                    {cloudModelOptions.find((m) => m.id === cloud_model_type)
                      ?.name || cloud_model_type}
                  </span>
                </TooltipContent>
              </Tooltip>
            </div>
            <div className="flex-shrink-0">
              <Select
                value={cloud_model_type}
                onValueChange={(value) => {
                  setModelType('cloud');
                  setCustomPrefer(null as unknown as string);
                  setLocalPreferStore(null);
                  setCloudModelType(value);
                  handleDefaultModelSelect('cloud', value);
                }}
              >
                <SelectTrigger size="sm">
                  <SelectValue placeholder={t('setting.select-model-type')} />
                </SelectTrigger>
                <SelectContent>
                  {cloudModelOptions.map((opt) => (
                    <SelectItem key={opt.id} value={opt.id}>
                      {opt.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          {(cloudOptionsLoading || cloudOptionsError) && (
            <div className="px-6 pb-4 text-body-sm text-text-label">
              {cloudOptionsLoading
                ? t('setting.loading', 'Loading...')
                : cloudOptionsError}
            </div>
          )}
        </div>
      );
    }

    // BYOK (Bring Your Own Key) content - show specific model
    if (selectedTab.startsWith('byok-')) {
      const modelId = selectedTab.replace('byok-', '');
      const idx = items.findIndex((item) => item.id === modelId);

      // Dynamic (user-added) custom provider
      if (idx === -1) {
        const dynConfig = customProviders[modelId];
        if (!dynConfig) return null;
        const showKey = dynamicShowApiKey[modelId] || false;
        return (
          <div className="flex w-full flex-col rounded-2xl bg-surface-tertiary">
            <div className="mx-6 mb-4 flex flex-col items-start justify-between border-x-0 border-b-[0.5px] border-t-0 border-solid border-border-secondary pb-4 pt-2">
              <div className="inline-flex items-center justify-between gap-2 self-stretch">
                <div className="text-body-base my-2 font-bold text-text-heading">
                  {modelId}
                </div>
                <div className="flex items-center gap-2">
                  <div className="h-2 w-2 shrink-0 rounded-full bg-text-success" />
                </div>
              </div>
              <div className="text-body-sm text-text-label">
                User-added custom provider.
              </div>
            </div>
            <div className="flex w-full flex-col items-center gap-4 px-6">
              <Input
                id={`dyn-apiKey-${modelId}`}
                type={showKey ? 'text' : 'password'}
                size="default"
                title={t('setting.api-key-setting')}
                placeholder={t('setting.enter-your-api-key')}
                backIcon={showKey ? <Eye className="h-5 w-5" /> : <EyeOff className="h-5 w-5" />}
                onBackIconClick={() => setDynamicShowApiKey((prev) => ({ ...prev, [modelId]: !showKey }))}
                value={dynamicApiKeys[modelId] || ''}
                onChange={(e) => setDynamicApiKeys((prev) => ({ ...prev, [modelId]: e.target.value }))}
              />
              <Input
                id={`dyn-endpoint-${modelId}`}
                size="default"
                title={t('setting.api-host-setting')}
                placeholder={t('setting.enter-your-api-host')}
                value={dynamicEndpoints[modelId] || ''}
                onChange={(e) => setDynamicEndpoints((prev) => ({ ...prev, [modelId]: e.target.value }))}
              />
              <Input
                id={`dyn-modelType-${modelId}`}
                size="default"
                title={t('setting.model-type-setting')}
                placeholder={t('setting.enter-your-model-type')}
                value={dynamicModelTypes[modelId] || ''}
                onChange={(e) => setDynamicModelTypes((prev) => ({ ...prev, [modelId]: e.target.value }))}
              />
            </div>
            <div className="flex justify-end gap-2 px-6 py-4">
              <Button variant="ghost" size="sm" className="!text-red-500" onClick={() => handleDynamicCustomDelete(modelId)}>
                <Trash2 className="mr-1 h-4 w-4" />
                {t('setting.delete', 'Delete')}
              </Button>
              <Button variant="primary" size="sm" onClick={() => handleDynamicCustomSave(modelId)}>
                <span className="text-text-inverse-primary">{t('setting.save')}</span>
              </Button>
            </div>
          </div>
        );
      }

      const item = items[idx];
      const canSwitch = !!form[idx].provider_id && !!form[idx].apiHost?.trim();

      return (
        <div className="flex w-full flex-col rounded-2xl bg-surface-tertiary">
          <div className="mx-6 mb-4 flex flex-col items-start justify-between border-x-0 border-b-[0.5px] border-t-0 border-solid border-border-secondary pb-4 pt-2">
            <div className="inline-flex items-center justify-between gap-2 self-stretch">
              <div className="text-body-base my-2 font-bold text-text-heading">
                {item.name}
              </div>
              <div className="flex items-center gap-2">
                {form[idx].prefer ? (
                  <span className="inline-flex items-center rounded-full px-2 py-1 text-label-xs font-bold text-text-success">
                    {t('setting.default')}
                  </span>
                ) : (
                  <Button
                    variant="ghost"
                    size="xs"
                    disabled={!canSwitch || loading === idx}
                    onClick={() => handleSwitch(idx, true)}
                    className={
                      canSwitch
                        ? 'inline-flex items-center rounded-full bg-button-transparent-fill-hover !text-text-label shadow-none hover:bg-button-transparent-fill-active'
                        : 'inline-flex items-center gap-1.5'
                    }
                  >
                    {!canSwitch
                      ? t('setting.not-configured')
                      : t('setting.set-as-default')}
                  </Button>
                )}
                {form[idx].provider_id ? (
                  <div className="h-2 w-2 shrink-0 rounded-full bg-text-success" />
                ) : (
                  <div className="h-2 w-2 shrink-0 rounded-full bg-text-label opacity-10" />
                )}
              </div>
            </div>
            <div className="text-body-sm text-text-label">
              {item.description}
            </div>
          </div>
          <div className="flex w-full flex-col items-center gap-4 px-6">
            {/* API Key Setting */}
            <Input
              id={`apiKey-${item.id}`}
              type={showApiKey[idx] ? 'text' : 'password'}
              size="default"
              title={t('setting.api-key-setting')}
              state={errors[idx]?.apiKey ? 'error' : 'default'}
              note={errors[idx]?.apiKey ?? undefined}
              placeholder={` ${t('setting.enter-your-api-key')} ${item.name
                } ${t('setting.key')}`}
              backIcon={
                showApiKey[idx] ? (
                  <Eye className="h-5 w-5" />
                ) : (
                  <EyeOff className="h-5 w-5" />
                )
              }
              onBackIconClick={() =>
                setShowApiKey((arr) => arr.map((v, i) => (i === idx ? !v : v)))
              }
              value={form[idx].apiKey}
              onChange={(e) => {
                const v = e.target.value;
                setForm((f) =>
                  f.map((fi, i) => (i === idx ? { ...fi, apiKey: v } : fi))
                );
                setErrors((errs) =>
                  errs.map((er, i) => (i === idx ? { ...er, apiKey: '' } : er))
                );
              }}
            />
            {/* API Host Setting */}
            <Input
              id={`apiHost-${item.id}`}
              size="default"
              title={t('setting.api-host-setting')}
              state={errors[idx]?.apiHost ? 'error' : 'default'}
              note={errors[idx]?.apiHost ?? undefined}
              placeholder={`${t('setting.enter-your-api-host')} ${item.name
                } ${t('setting.url')}`}
              value={form[idx].apiHost}
              onChange={(e) => {
                const v = e.target.value;
                setForm((f) =>
                  f.map((fi, i) => (i === idx ? { ...fi, apiHost: v } : fi))
                );
                setErrors((errs) =>
                  errs.map((er, i) => (i === idx ? { ...er, apiHost: '' } : er))
                );
              }}
            />
            {/* Model Type Setting */}
            <Input
              id={`modelType-${item.id}`}
              size="default"
              title={t('setting.model-type-setting')}
              state={errors[idx]?.model_type ? 'error' : 'default'}
              note={errors[idx]?.model_type ?? undefined}
              placeholder={`${t('setting.enter-your-model-type')} ${item.name
                } ${t('setting.model-type')}`}
              value={form[idx].model_type}
              onChange={(e) => {
                const v = e.target.value;
                setForm((f) =>
                  f.map((fi, i) => (i === idx ? { ...fi, model_type: v } : fi))
                );
                setErrors((errs) =>
                  errs.map((er, i) =>
                    i === idx ? { ...er, model_type: '' } : er
                  )
                );
              }}
            />
            {/* externalConfig render */}
            {item.externalConfig &&
              form[idx].externalConfig &&
              form[idx].externalConfig.map((ec, ecIdx) => (
                <div key={ec.key} className="flex h-full w-full flex-col gap-4">
                  {ec.options && ec.options.length > 0 ? (
                    <Select
                      value={ec.value}
                      onValueChange={(v) => {
                        setForm((f) =>
                          f.map((fi, i) =>
                            i === idx
                              ? {
                                ...fi,
                                externalConfig: fi.externalConfig?.map(
                                  (eec, i2) =>
                                    i2 === ecIdx ? { ...eec, value: v } : eec
                                ),
                              }
                              : fi
                          )
                        );
                      }}
                    >
                      <SelectTrigger
                        size="default"
                        title={ec.name}
                        state={
                          errors[idx]?.externalConfig ? 'error' : undefined
                        }
                        note={errors[idx]?.externalConfig ?? undefined}
                      >
                        <SelectValue placeholder={t('setting.please-select')} />
                      </SelectTrigger>
                      <SelectContent>
                        {ec.options.map((opt) => (
                          <SelectItem key={opt.value} value={opt.value}>
                            {opt.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  ) : (
                    <Input
                      size="default"
                      title={ec.name}
                      state={errors[idx]?.externalConfig ? 'error' : undefined}
                      note={errors[idx]?.externalConfig ?? undefined}
                      value={ec.value}
                      onChange={(e) => {
                        const v = e.target.value;
                        setForm((f) =>
                          f.map((fi, i) =>
                            i === idx
                              ? {
                                ...fi,
                                externalConfig: fi.externalConfig?.map(
                                  (eec, i2) =>
                                    i2 === ecIdx ? { ...eec, value: v } : eec
                                ),
                              }
                              : fi
                          )
                        );
                      }}
                    />
                  )}
                </div>
              ))}
          </div>
          {/* Action Button */}
          <div className="flex justify-end gap-2 px-6 py-4">
            <Button
              variant="ghost"
              size="sm"
              className="!text-text-label"
              onClick={() => handleDelete(idx)}
            >
              {t('setting.reset')}
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={() => handleVerify(idx)}
              disabled={loading === idx}
            >
              <span className="text-text-inverse-primary">
                {loading === idx ? t('setting.configuring') : t('setting.save')}
              </span>
            </Button>
          </div>
        </div>
      );
    }

    // Local model content - specific platforms
    if (selectedTab.startsWith('local-')) {
      const platform = selectedTab.replace('local-', '');

      const currentEndpoint = localEndpoints[platform] || '';
      const currentType = localTypes[platform] || '';
      const currentApiKey = localApiKeys[platform] || '';
      const showKey = localShowApiKey[platform] || false;
      const isConnected = !!currentEndpoint;
      const isPreferred = modelType === 'local' && localPlatform === platform;

      return (
        <div className="flex w-full flex-col rounded-2xl bg-surface-tertiary">
          <div className="mx-6 mb-4 flex flex-col items-start justify-between border-x-0 border-b-[0.5px] border-t-0 border-solid border-border-secondary pb-4 pt-2">
            <div className="inline-flex items-center justify-between gap-2 self-stretch">
              <div className="flex items-center gap-2">
                <div className="text-body-base my-2 font-bold text-text-heading">
                  {platform === 'ollama'
                    ? 'Ollama'
                    : platform === 'vllm'
                      ? 'vLLM'
                      : platform === 'sglang'
                        ? 'SGLang'
                        : platform === 'lmstudio'
                          ? 'LM Studio'
                          : platform}
                </div>
                {isPreferred ? (
                  <Button
                    variant="success"
                    size="xs"
                    className="focus-none rounded-full shadow-none"
                    disabled={!isConnected}
                    onClick={() => openDefaultModelSelector()}
                  >
                    {t('setting.default')}
                  </Button>
                ) : (
                  <Button
                    variant="ghost"
                    size="xs"
                    disabled={!isConnected}
                    onClick={() => handleLocalSwitch(true, platform)}
                    className={
                      isConnected
                        ? 'rounded-full bg-button-transparent-fill-hover !text-text-label shadow-none'
                        : ''
                    }
                  >
                    {!isConnected
                      ? t('setting.not-configured')
                      : t('setting.set-as-default')}
                  </Button>
                )}
              </div>
              {isConnected ? (
                <div className="h-2 w-2 rounded-full bg-text-success" />
              ) : (
                <div className="h-2 w-2 rounded-full bg-text-label opacity-10" />
              )}
            </div>
          </div>
          {/* Model Endpoint URL Setting */}
          <div className="flex w-full flex-col items-center gap-4 px-6">
            <Input
              size="default"
              title={t('setting.model-endpoint-url')}
              state={localInputError ? 'error' : 'default'}
              value={currentEndpoint}
              onChange={(e) => {
                setLocalEndpoints((prev) => ({
                  ...prev,
                  [platform]: e.target.value,
                }));
                setLocalInputError(false);
                setLocalError(null);
              }}
              placeholder={
                platform === 'ollama'
                  ? 'http://localhost:11434/v1'
                  : platform === 'lmstudio'
                    ? 'http://localhost:1234/v1'
                    : 'http://localhost:8000/v1'
              }
              note={localError ?? undefined}
            />
            <Input
              size="default"
              title={t('setting.model-type')}
              state={localInputError ? 'error' : 'default'}
              placeholder={t('setting.enter-your-local-model-type')}
              value={currentType}
              onChange={(e) =>
                setLocalTypes((prev) => ({
                  ...prev,
                  [platform]: e.target.value,
                }))
              }
            />
            <Input
              size="default"
              title={`${t('setting.api-key-setting')} (${t('setting.optional', 'Optional')})`}
              type={showKey ? 'text' : 'password'}
              placeholder={`${t('setting.enter-your-api-key')} (${t('setting.optional', 'Optional')})`}
              value={currentApiKey}
              onChange={(e) =>
                setLocalApiKeys((prev) => ({
                  ...prev,
                  [platform]: e.target.value,
                }))
              }
              backIcon={
                showKey ? (
                  <Eye className="h-5 w-5" />
                ) : (
                  <EyeOff className="h-5 w-5" />
                )
              }
              onBackIconClick={() =>
                setLocalShowApiKey((prev) => ({
                  ...prev,
                  [platform]: !showKey,
                }))
              }
            />
          </div>
          {/* Action Button */}
          <div className="flex justify-end gap-2 px-6 py-4">
            <Button
              variant="ghost"
              size="sm"
              className="!text-text-label"
              onClick={() => handleLocalReset(platform)}
            >
              {t('setting.reset')}
            </Button>
            <Button
              onClick={handleLocalVerify}
              disabled={localVerifying}
              variant="primary"
              size="sm"
            >
              <span className="text-text-inverse-primary">
                {localVerifying ? t('setting.configuring') : t('setting.save')}
              </span>
            </Button>
          </div>
        </div>
      );
    }

    return null;
  };

  return (
    <div className="m-auto flex h-auto w-full flex-1 flex-col">
      {/* Header Section */}
      <div className="sticky top-0 z-10 flex w-full items-center justify-between bg-surface-primary px-6 pb-6 pt-8">
        <div className="flex w-full flex-col items-start justify-between gap-4">
          <div className="flex flex-col">
            <div className="text-heading-sm font-bold text-text-heading">
              {t('setting.models')}
            </div>
          </div>
        </div>
      </div>
      {/* Content Section */}
      <div className="mb-8 flex flex-col gap-6">
        {/* Default Model Cascading Dropdown */}
        <div className="flex w-full flex-row items-center justify-between gap-4 rounded-2xl bg-surface-secondary px-6 py-4">
          <div className="flex w-full flex-col items-start justify-center gap-1">
            <div className="text-body-base font-bold text-text-heading">
              {t('setting.models-default-setting-title')}
            </div>
            <div className="text-body-sm">
              {t('setting.models-default-setting-description')}
            </div>
          </div>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                ref={defaultModelTriggerRef}
                className="flex w-fit items-center justify-between gap-2 rounded-lg border-[0.5px] border-solid border-border-success bg-surface-success px-3 py-1 font-semibold text-text-success transition-colors hover:opacity-70 active:opacity-90"
              >
                <span className="whitespace-nowrap text-body-sm">
                  {getDefaultModelDisplayText()}
                </span>
                <ChevronDown className="h-4 w-4 flex-shrink-0 text-text-success" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="max-h-[480px] w-[240px] overflow-y-auto">
              {/* Hanggent Cloud */}
              {import.meta.env.VITE_USE_LOCAL_PROXY !== 'true' && (
                <>
                  <DropdownMenuLabel className="text-xs text-text-label">
                    {t('setting.hanggent-cloud')}
                  </DropdownMenuLabel>
                  <DropdownMenuSub>
                    <DropdownMenuSubTrigger className="gap-2">
                      <img src={hanggentImage} alt="Cloud" className="h-4 w-4" />
                      <span className="text-body-sm">
                        {t('setting.hanggent-cloud')}
                      </span>
                      {modelType === 'cloud' && (
                        <Check className="ml-auto h-4 w-4 text-text-success" />
                      )}
                    </DropdownMenuSubTrigger>
                    <DropdownMenuSubContent className="max-h-[300px] w-[200px] overflow-y-auto">
                      {cloudModelOptions.map((model) => (
                        <DropdownMenuItem
                          key={model.id}
                          onClick={() =>
                            handleDefaultModelSelect('cloud', model.id)
                          }
                          className="flex items-center justify-between"
                        >
                          <span className="text-body-sm">{model.name}</span>
                          {modelType === 'cloud' && cloud_model_type === model.id && (
                            <Check className="h-4 w-4 text-text-success" />
                          )}
                        </DropdownMenuItem>
                      ))}
                    </DropdownMenuSubContent>
                  </DropdownMenuSub>
                  <DropdownMenuSeparator />
                </>
              )}

              {/* Custom Model (BYOK) Providers — flat list */}
              <DropdownMenuLabel className="text-xs text-text-label">
                {t('setting.custom-model')}
              </DropdownMenuLabel>
              {items.map((item, idx) => {
                const isConfigured = !!form[idx]?.provider_id;
                const isPreferred = modelType === 'custom' && form[idx]?.prefer;
                const modelImage = getModelImage(item.id);

                return (
                  <DropdownMenuItem
                    key={item.id}
                    onClick={() => {
                      if (isConfigured) {
                        handleDefaultModelSelect('custom', item.id);
                      } else {
                        setSelectedTab(`byok-${item.id}` as SidebarTab);
                        if (byokCollapsed) setByokCollapsed(false);
                      }
                    }}
                    className="flex items-center justify-between"
                  >
                    <div className="flex items-center gap-2">
                      {modelImage ? (
                        <img
                          src={modelImage}
                          alt={item.name}
                          className={`h-4 w-4 ${!isConfigured ? 'opacity-40' : ''}`}
                        />
                      ) : (
                        <Key className={`h-4 w-4 ${!isConfigured ? 'text-icon-secondary opacity-40' : 'text-icon-secondary'}`} />
                      )}
                      <span
                        className={`text-body-sm ${isConfigured ? 'text-text-body' : 'text-text-label opacity-60'}`}
                      >
                        {item.name}
                      </span>
                    </div>
                    <div className="flex items-center gap-1">
                      {isPreferred && (
                        <Check className="h-4 w-4 text-text-success" />
                      )}
                      {isConfigured && !isPreferred && (
                        <div className="h-2 w-2 rounded-full bg-text-success" />
                      )}
                    </div>
                  </DropdownMenuItem>
                );
              })}

              {extraCustomIds.map((id) => {
                const isConfigured = !!customProviders[id]?.endpoint;
                const isPreferred = modelType === 'custom' && !!customProviders[id]?.prefer;

                return (
                  <DropdownMenuItem
                    key={id}
                    onClick={() => {
                      if (isConfigured) {
                        handleDefaultModelSelect('custom', id);
                      } else {
                        setSelectedTab(`byok-${id}` as SidebarTab);
                        if (byokCollapsed) setByokCollapsed(false);
                      }
                    }}
                    disabled={!isConfigured}
                    className="flex items-center justify-between"
                  >
                    <div className="flex items-center gap-2">
                      <Key className={`h-4 w-4 ${!isConfigured ? 'text-icon-secondary opacity-40' : 'text-icon-secondary'}`} />
                      <span
                        className={`text-body-sm ${isConfigured ? 'text-text-body' : 'text-text-label opacity-60'}`}
                      >
                        {customProviders[id]?.providerName || id}
                      </span>
                    </div>
                    <div className="flex items-center gap-1">
                      {isPreferred && <Check className="h-4 w-4 text-text-success" />}
                      {isConfigured && !isPreferred && (
                        <div className="h-2 w-2 rounded-full bg-text-success" />
                      )}
                    </div>
                  </DropdownMenuItem>
                );
              })}

              <DropdownMenuSeparator />

              {/* Local Model Providers — flat list */}
              <DropdownMenuLabel className="text-xs text-text-label">
                {t('setting.local-model')}
              </DropdownMenuLabel>
              {localModelOptions.map((model) => {
                const isConfigured = !!localEndpoints[model.id];
                const isPreferred = modelType === 'local' && localPlatform === model.id;
                const modelImage = getModelImage(`local-${model.id}`);

                return (
                  <DropdownMenuItem
                    key={model.id}
                    onClick={() => {
                      if (isConfigured) {
                        handleDefaultModelSelect('local', model.id);
                      } else {
                        setSelectedTab(`local-${model.id}` as SidebarTab);
                        if (localCollapsed) setLocalCollapsed(false);
                      }
                    }}
                    disabled={!isConfigured}
                    className="flex items-center justify-between"
                  >
                    <div className="flex items-center gap-2">
                      {modelImage ? (
                        <img
                          src={modelImage}
                          alt={model.name}
                          className={`h-4 w-4 ${!isConfigured ? 'opacity-40' : ''}`}
                        />
                      ) : (
                        <Server className={`h-4 w-4 ${!isConfigured ? 'text-icon-secondary opacity-40' : 'text-icon-secondary'}`} />
                      )}
                      <span
                        className={`text-body-sm ${isConfigured ? 'text-text-body' : 'text-text-label opacity-60'}`}
                      >
                        {model.name}
                      </span>
                    </div>
                    <div className="flex items-center gap-1">
                      {isPreferred && (
                        <Check className="h-4 w-4 text-text-success" />
                      )}
                      {isConfigured && !isPreferred && (
                        <div className="h-2 w-2 rounded-full bg-text-success" />
                      )}
                    </div>
                  </DropdownMenuItem>
                );
              })}

              {extraLocalIds.map((id) => {
                const isConfigured = !!localEndpoints[id];
                const isPreferred = modelType === 'local' && localPlatform === id;

                return (
                  <DropdownMenuItem
                    key={id}
                    onClick={() => {
                      if (isConfigured) {
                        handleDefaultModelSelect('local', id);
                      } else {
                        setSelectedTab(`local-${id}` as SidebarTab);
                        if (localCollapsed) setLocalCollapsed(false);
                      }
                    }}
                    disabled={!isConfigured}
                    className="flex items-center justify-between"
                  >
                    <div className="flex items-center gap-2">
                      <Server className={`h-4 w-4 ${!isConfigured ? 'text-icon-secondary opacity-40' : 'text-icon-secondary'}`} />
                      <span
                        className={`text-body-sm ${isConfigured ? 'text-text-body' : 'text-text-label opacity-60'}`}
                      >
                        {id}
                      </span>
                    </div>
                    <div className="flex items-center gap-1">
                      {isPreferred && <Check className="h-4 w-4 text-text-success" />}
                      {isConfigured && !isPreferred && (
                        <div className="h-2 w-2 rounded-full bg-text-success" />
                      )}
                    </div>
                  </DropdownMenuItem>
                );
              })}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        {/* Content Section with Sidebar */}
        <div className="flex w-full flex-col items-start justify-between gap-2 rounded-2xl bg-surface-secondary px-6 py-4">
          <div className="text-body-base sticky top-[86px] z-10 mb-2 w-full border-x-0 border-b-[0.5px] border-t-0 border-solid border-border-secondary bg-surface-secondary pb-4 font-bold text-text-heading">
            {t('setting.models-configuration')}
          </div>

          <div className="flex w-full flex-row items-start justify-between">
            {/* Sidebar */}
            <div className="-ml-2 mr-4 h-full w-[240px] rounded-2xl bg-surface-secondary">
              <div className="flex flex-col gap-4">
                {/* Hanggent Cloud Section */}
                <div className="flex flex-col gap-1">
                  <div className="px-3 py-2 text-body-sm font-bold text-text-heading">
                    {t('setting.hanggent-cloud')}
                  </div>
                  {import.meta.env.VITE_USE_LOCAL_PROXY !== 'true' &&
                    renderSidebarItem(
                      'cloud',
                      modelType === 'cloud' && cloud_model_type
                        ? `${t('setting.hanggent-cloud')} · ${cloud_model_type}`
                        : t('setting.hanggent-cloud'),
                      'cloud',
                      selectedTab === 'cloud',
                      false,
                      modelType === 'cloud'
                    )}
                </div>
                {/* Bring Your Own Key Section */}
                <div className="flex flex-col gap-1">
                  <button
                    onClick={() => setByokCollapsed(!byokCollapsed)}
                    className="flex items-center justify-between rounded-lg bg-transparent px-3 py-2 transition-colors hover:bg-surface-secondary"
                  >
                    <div className="text-body-sm font-bold text-text-heading">
                      {t('setting.custom-model')}
                    </div>
                    {byokCollapsed ? (
                      <ChevronDown className="h-4 w-4 text-text-label" />
                    ) : (
                      <ChevronUp className="h-4 w-4 text-text-label" />
                    )}
                  </button>
                  <div
                    className={`overflow-hidden transition-all duration-300 ease-in-out ${byokCollapsed
                      ? 'max-h-0 opacity-0'
                      : 'max-h-[2000px] opacity-100'
                      }`}
                  >
                    {items.map((item, idx) =>
                      renderSidebarItem(
                        `byok-${item.id}` as SidebarTab,
                        item.name,
                        item.id,
                        selectedTab === `byok-${item.id}`,
                        true,
                        !!form[idx].provider_id
                      )
                    )}
                    {extraCustomIds.map((id) =>
                      renderSidebarItem(
                        `byok-${id}` as SidebarTab,
                        customProviders[id]?.providerName || id,
                        id,
                        selectedTab === `byok-${id}`,
                        true,
                        true
                      )
                    )}
                    <button
                      onClick={() => setAddProviderMode('custom')}
                      className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-body-sm font-medium text-text-label transition-colors hover:bg-fill-fill-transparent-hover"
                    >
                      <Plus className="h-4 w-4" />
                      {t('setting.add', 'Add')}
                    </button>
                  </div>
                </div>

                {/* Local Model Section */}
                <div className="flex flex-col gap-1">
                  <button
                    onClick={() => setLocalCollapsed(!localCollapsed)}
                    className="flex items-center justify-between rounded-lg bg-transparent px-3 py-2 transition-colors hover:bg-surface-secondary"
                  >
                    <div className="text-body-sm font-bold text-text-heading">
                      {t('setting.local-model')}
                    </div>
                    {localCollapsed ? (
                      <ChevronDown className="h-4 w-4 text-text-label" />
                    ) : (
                      <ChevronUp className="h-4 w-4 text-text-label" />
                    )}
                  </button>
                  <div
                    className={`overflow-hidden transition-all duration-300 ease-in-out ${localCollapsed
                      ? 'max-h-0 opacity-0'
                      : 'max-h-[2000px] opacity-100'
                      }`}
                  >
                    {renderSidebarItem('local-ollama', 'Ollama', 'local-ollama', selectedTab === 'local-ollama', true, !!localEndpoints['ollama'])}
                    {renderSidebarItem('local-vllm', 'vLLM', 'local-vllm', selectedTab === 'local-vllm', true, !!localEndpoints['vllm'])}
                    {renderSidebarItem('local-sglang', 'SGLang', 'local-sglang', selectedTab === 'local-sglang', true, !!localEndpoints['sglang'])}
                    {renderSidebarItem('local-lmstudio', 'LM Studio', 'local-lmstudio', selectedTab === 'local-lmstudio', true, !!localEndpoints['lmstudio'])}
                    {extraLocalIds.map((id) =>
                      renderSidebarItem(
                        `local-${id}` as SidebarTab,
                        id,
                        id,
                        selectedTab === `local-${id}`,
                        true,
                        !!localEndpoints[id]
                      )
                    )}
                    <button
                      onClick={() => setAddProviderMode('local')}
                      className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-body-sm font-medium text-text-label transition-colors hover:bg-fill-fill-transparent-hover"
                    >
                      <Plus className="h-4 w-4" />
                      {t('setting.add', 'Add')}
                    </button>
                  </div>
                </div>
              </div>
            </div>
            {/* Main Content */}
            <div className="sticky top-[136px] z-10 min-w-0 flex-1">
              {renderContent()}
            </div>
          </div>
        </div>
      </div>

      {/* Add Provider Dialog */}
      <Dialog open={addProviderMode !== null} onOpenChange={(open) => { if (!open) setAddProviderMode(null); }}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>
              {addProviderMode === 'custom' ? t('setting.add-custom-provider', 'Add Custom Provider') : t('setting.add-local-provider', 'Add Local Provider')}
            </DialogTitle>
            <DialogDescription>
              {addProviderMode === 'custom'
                ? t('setting.add-custom-provider-desc', 'Add a new custom model provider with your own API key.')
                : t('setting.add-local-provider-desc', 'Add a new local model endpoint.')}
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-4 py-4">
            <Input
              size="default"
              title={t('setting.provider-name', 'Provider Name')}
              placeholder={addProviderMode === 'custom' ? 'e.g. groq' : 'e.g. custom-ollama'}
              value={newProviderName}
              onChange={(e) => setNewProviderName(e.target.value)}
            />
            <Input
              size="default"
              title={t('setting.api-host-setting')}
              placeholder="e.g. https://api.example.com/v1"
              value={newProviderEndpoint}
              onChange={(e) => setNewProviderEndpoint(e.target.value)}
            />
            <Input
              size="default"
              title={t('setting.model-type-setting')}
              placeholder="e.g. gpt-4o"
              value={newProviderModelType}
              onChange={(e) => setNewProviderModelType(e.target.value)}
            />
            <Input
              size="default"
              title={`${t('setting.api-key-setting')} (${t('setting.optional', 'Optional')})`}
              type="password"
              placeholder={t('setting.enter-your-api-key')}
              value={newProviderApiKey}
              onChange={(e) => setNewProviderApiKey(e.target.value)}
            />
          </div>
          <DialogFooter>
            <Button variant="ghost" size="sm" onClick={() => setAddProviderMode(null)}>
              {t('setting.cancel', 'Cancel')}
            </Button>
            <Button variant="primary" size="sm" onClick={handleAddProvider}>
              <span className="text-text-inverse-primary">{t('setting.add', 'Add')}</span>
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
