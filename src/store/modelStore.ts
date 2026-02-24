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

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

// Base64 helpers for API key obfuscation
const encodeKey = (key: string): string => {
  if (!key) return '';
  try {
    return btoa(key);
  } catch {
    return key;
  }
};

const decodeKey = (encoded: string): string => {
  if (!encoded) return '';
  try {
    return atob(encoded);
  } catch {
    return encoded;
  }
};

// Custom provider config (BYOK)
export interface CustomProviderConfig {
  apiKey: string; // base64-encoded
  endpoint: string;
  modelType: string;
  providerName: string;
  encryptedConfig?: Record<string, any>;
  isValid: boolean;
  prefer: boolean;
}

// Local provider config (Ollama, vLLM, SGLang, LM Studio)
export interface LocalProviderConfig {
  endpoint: string;
  modelType: string;
  apiKey: string; // base64-encoded
  platform: string;
  isValid: boolean;
  prefer: boolean;
}

// Active provider result (resolved config ready for backend)
export interface ActiveProviderResult {
  api_key: string;
  model_type: string;
  model_platform: string;
  api_url: string;
  extra_params: Record<string, any>;
}

interface ModelStoreState {
  // Custom model providers (BYOK) - keyed by provider name (e.g. "openai", "anthropic")
  customProviders: Record<string, CustomProviderConfig>;
  // Local model providers - keyed by platform (e.g. "ollama", "vllm")
  localProviders: Record<string, LocalProviderConfig>;

  // Preferred provider tracking
  preferredCustomProvider: string | null;
  preferredLocalPlatform: string | null;

  // Migration flag
  migrated: boolean;

  // Actions - Custom providers
  setCustomProvider: (name: string, config: CustomProviderConfig) => void;
  removeCustomProvider: (name: string) => void;
  setCustomPrefer: (name: string | null) => void;

  // Actions - Local providers
  setLocalProvider: (platform: string, config: LocalProviderConfig) => void;
  removeLocalProvider: (platform: string) => void;
  setLocalPrefer: (platform: string | null) => void;

  // Getters
  getActiveProvider: (modelType?: 'cloud' | 'local' | 'custom') => ActiveProviderResult | null;
  getPreferredCustom: () => CustomProviderConfig | null;
  getPreferredLocal: () => LocalProviderConfig | null;
  hasAnyLocalProvider: () => boolean;
  hasAnyCustomProvider: () => boolean;

  // Migration
  setMigrated: () => void;
  migrateFromServer: (providers: any[]) => void;
}

const modelStore = create<ModelStoreState>()(
  persist(
    (set, get) => ({
      customProviders: {},
      localProviders: {},
      preferredCustomProvider: null,
      preferredLocalPlatform: null,
      migrated: false,

      // Custom provider actions
      setCustomProvider: (name, config) => {
        set((state) => ({
          customProviders: {
            ...state.customProviders,
            [name]: {
              ...config,
              apiKey: encodeKey(config.apiKey),
            },
          },
        }));
      },

      removeCustomProvider: (name) => {
        set((state) => {
          const { [name]: _removed, ...rest } = state.customProviders;
          return {
            customProviders: rest,
            preferredCustomProvider:
              state.preferredCustomProvider === name
                ? null
                : state.preferredCustomProvider,
          };
        });
      },

      setCustomPrefer: (name) => {
        set((state) => {
          // Clear prefer on all custom providers, set on the target
          const updated: Record<string, CustomProviderConfig> = {};
          for (const [key, config] of Object.entries(state.customProviders)) {
            updated[key] = { ...config, prefer: key === name };
          }
          // Also clear local prefer
          const updatedLocal: Record<string, LocalProviderConfig> = {};
          for (const [key, config] of Object.entries(state.localProviders)) {
            updatedLocal[key] = { ...config, prefer: false };
          }
          return {
            customProviders: updated,
            localProviders: updatedLocal,
            preferredCustomProvider: name,
            preferredLocalPlatform: null,
          };
        });
      },

      // Local provider actions
      setLocalProvider: (platform, config) => {
        set((state) => ({
          localProviders: {
            ...state.localProviders,
            [platform]: {
              ...config,
              apiKey: encodeKey(config.apiKey),
            },
          },
        }));
      },

      removeLocalProvider: (platform) => {
        set((state) => {
          const { [platform]: _removed, ...rest } = state.localProviders;
          return {
            localProviders: rest,
            preferredLocalPlatform:
              state.preferredLocalPlatform === platform
                ? null
                : state.preferredLocalPlatform,
          };
        });
      },

      setLocalPrefer: (platform) => {
        set((state) => {
          // Clear prefer on all local providers, set on the target
          const updatedLocal: Record<string, LocalProviderConfig> = {};
          for (const [key, config] of Object.entries(state.localProviders)) {
            updatedLocal[key] = { ...config, prefer: key === platform };
          }
          // Also clear custom prefer
          const updatedCustom: Record<string, CustomProviderConfig> = {};
          for (const [key, config] of Object.entries(state.customProviders)) {
            updatedCustom[key] = { ...config, prefer: false };
          }
          return {
            localProviders: updatedLocal,
            customProviders: updatedCustom,
            preferredLocalPlatform: platform,
            preferredCustomProvider: null,
          };
        });
      },

      // Getters
      getPreferredCustom: () => {
        const { customProviders, preferredCustomProvider } = get();
        if (!preferredCustomProvider) return null;
        const provider = customProviders[preferredCustomProvider];
        return provider ? { ...provider, apiKey: decodeKey(provider.apiKey) } : null;
      },

      getPreferredLocal: () => {
        const { localProviders, preferredLocalPlatform } = get();
        if (!preferredLocalPlatform) return null;
        const provider = localProviders[preferredLocalPlatform];
        return provider ? { ...provider, apiKey: decodeKey(provider.apiKey) } : null;
      },

      hasAnyLocalProvider: () => {
        const { localProviders } = get();
        return Object.values(localProviders).some(
          (p) => p.isValid && p.endpoint
        );
      },

      hasAnyCustomProvider: () => {
        const { customProviders } = get();
        return Object.values(customProviders).some(
          (p) => p.isValid && p.endpoint
        );
      },

      // Get active provider based on modelType; returns null for cloud or when nothing matches
      getActiveProvider: (modelType?: 'cloud' | 'local' | 'custom') => {
        const state = get();

        // Cloud mode doesn't use local/custom providers
        if (modelType === 'cloud') return null;

        // Helper: find best local provider (preferred first, then any valid)
        const findLocal = (): ActiveProviderResult | null => {
          if (state.preferredLocalPlatform) {
            const local = state.localProviders[state.preferredLocalPlatform];
            if (local && local.isValid && local.endpoint) {
              return {
                api_key: decodeKey(local.apiKey) || 'not-required',
                model_type: local.modelType,
                model_platform: local.platform,
                api_url: local.endpoint,
                extra_params: {
                  model_platform: local.platform,
                  model_type: local.modelType,
                },
              };
            }
          }
          for (const [, local] of Object.entries(state.localProviders)) {
            if (local.isValid && local.endpoint) {
              return {
                api_key: decodeKey(local.apiKey) || 'not-required',
                model_type: local.modelType,
                model_platform: local.platform,
                api_url: local.endpoint,
                extra_params: {
                  model_platform: local.platform,
                  model_type: local.modelType,
                },
              };
            }
          }
          return null;
        };

        // Helper: find best custom provider (preferred first, then any valid)
        const findCustom = (): ActiveProviderResult | null => {
          if (state.preferredCustomProvider) {
            const custom = state.customProviders[state.preferredCustomProvider];
            if (custom && custom.isValid && custom.endpoint) {
              return {
                api_key: decodeKey(custom.apiKey),
                model_type: custom.modelType,
                model_platform: custom.providerName,
                api_url: custom.endpoint,
                extra_params: custom.encryptedConfig || {},
              };
            }
          }
          for (const [, custom] of Object.entries(state.customProviders)) {
            if (custom.isValid && custom.endpoint) {
              return {
                api_key: decodeKey(custom.apiKey),
                model_type: custom.modelType,
                model_platform: custom.providerName,
                api_url: custom.endpoint,
                extra_params: custom.encryptedConfig || {},
              };
            }
          }
          return null;
        };

        // When modelType is specified, only search the matching category
        if (modelType === 'local') return findLocal();
        if (modelType === 'custom') return findCustom();

        // Fallback (no modelType): local-first, then custom (backward compat)
        return findLocal() || findCustom() || null;
      },

      // Migration
      setMigrated: () => set({ migrated: true }),

      migrateFromServer: (providers: any[]) => {
        const customProviders: Record<string, CustomProviderConfig> = {};
        const localProviders: Record<string, LocalProviderConfig> = {};
        let preferredCustom: string | null = null;
        let preferredLocal: string | null = null;

        const LOCAL_NAMES = ['ollama', 'vllm', 'sglang', 'lmstudio'];

        for (const p of providers) {
          const name = p.provider_name;
          if (LOCAL_NAMES.includes(name)) {
            const platform =
              p.encrypted_config?.model_platform || name;
            localProviders[platform] = {
              endpoint: p.endpoint_url || '',
              modelType: p.encrypted_config?.model_type || p.model_type || '',
              apiKey: encodeKey(
                p.api_key === 'not-required' ? '' : (p.api_key || '')
              ),
              platform,
              isValid: !!p.is_valid || p.is_valid === 2,
              prefer: p.prefer ?? false,
            };
            if (p.prefer) preferredLocal = platform;
          } else {
            customProviders[name] = {
              apiKey: encodeKey(p.api_key || ''),
              endpoint: p.endpoint_url || '',
              modelType: p.model_type || '',
              providerName: name,
              encryptedConfig: p.encrypted_config || undefined,
              isValid: !!p.is_valid || p.is_valid === 2,
              prefer: p.prefer ?? false,
            };
            if (p.prefer) preferredCustom = name;
          }
        }

        set({
          customProviders,
          localProviders,
          preferredCustomProvider: preferredCustom,
          preferredLocalPlatform: preferredLocal,
          migrated: true,
        });
      },
    }),
    {
      name: 'model-storage',
      partialize: (state) => ({
        customProviders: state.customProviders,
        localProviders: state.localProviders,
        preferredCustomProvider: state.preferredCustomProvider,
        preferredLocalPlatform: state.preferredLocalPlatform,
        migrated: state.migrated,
      }),
    }
  )
);

// Hook version for components
export const useModelStore = modelStore;

// Non-hook version for non-components (e.g. chatStore)
export const getModelStore = () => modelStore.getState();
