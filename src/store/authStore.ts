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

// type definition
type InitState = 'permissions' | 'carousel' | 'done';
type ModelType = 'cloud' | 'local' | 'custom';
type PreferredIDE = 'vscode' | 'cursor' | 'system';
type CloudModelType = string;

// auth info interface
interface AuthInfo {
  token: string;
  username: string;
  email: string;
  user_id: number;
}

// auth state interface
interface AuthState {
  // user auth info
  token: string | null;
  username: string | null;
  email: string | null;
  user_id: number | null;

  // application settings
  appearance: string;
  language: string;
  isFirstLaunch: boolean;
  modelType: ModelType;
  cloud_model_type: CloudModelType;
  initState: InitState;

  // IDE preference
  preferredIDE: PreferredIDE;

  // shared token
  share_token?: string | null;

  // worker list data
  workerListData: { [key: string]: Agent[] };

  // auth related methods
  setAuth: (auth: AuthInfo) => void;
  logout: () => void;
  clerkLogin: (clerkToken: string, type: string) => Promise<void>;
  isTokenExpired: () => boolean;

  // set related methods
  setAppearance: (appearance: string) => void;
  setLanguage: (language: string) => void;
  setInitState: (initState: InitState) => void;
  setModelType: (modelType: ModelType) => void;
  setCloudModelType: (cloud_model_type: CloudModelType) => void;
  setIsFirstLaunch: (isFirstLaunch: boolean) => void;
  setPreferredIDE: (ide: PreferredIDE) => void;

  // worker related methods
  setWorkerList: (workerList: Agent[]) => void;
  checkAgentTool: (tool: string) => void;

  // cloud model syncing
  syncCloudModelWithProviders: () => Promise<void>;
}

// Default model is empty — will be populated from cloud config on first sync
const getRandomDefaultModel = (): CloudModelType => '';

// create store
const authStore = create<AuthState>()(
  persist(
    (set, get) => ({
      // initial state
      token: null,
      username: null,
      email: null,
      user_id: null,
      appearance: 'light',
      language: 'system',
      isFirstLaunch: true,
      modelType: 'cloud',
      cloud_model_type: getRandomDefaultModel(),
      preferredIDE: 'system',
      initState: 'permissions',
      share_token: null,
      workerListData: {},

      // auth related methods
      setAuth: ({ token, username, email, user_id }) =>
        set({ token, username, email, user_id }),

      logout: () =>
        set({
          token: null,
          username: null,
          email: null,
          user_id: null,
          initState: 'carousel',
        }),

      clerkLogin: async (clerkToken: string, type: string) => {
        const { proxyFetchPost } = await import('@/api/http');
        const data = await proxyFetchPost(
          '/api/login-by-clerk?token=' + encodeURIComponent(clerkToken),
          { token: clerkToken }
        );
        if (data && data.token) {
          set({
            token: data.token,
            email: data.email || null,
            username: data.username || null,
            user_id: data.user_id || null,
          });
        } else {
          throw new Error(data?.text || 'Clerk login failed');
        }
      },

      isTokenExpired: () => {
        const token = get().token;
        if (!token) return true;
        try {
          const payload = JSON.parse(atob(token.split('.')[1]));
          return payload.exp < Math.floor(Date.now() / 1000);
        } catch {
          return true;
        }
      },

      // set related methods
      setAppearance: (appearance) => set({ appearance }),

      setLanguage: (language) => set({ language }),

      setInitState: (initState) => {
        console.log('set({ initState })', initState);
        set({ initState });
      },

      setModelType: (modelType) => set({ modelType }),

      setCloudModelType: (cloud_model_type) => set({ cloud_model_type }),

      setIsFirstLaunch: (isFirstLaunch) => set({ isFirstLaunch }),

      setPreferredIDE: (preferredIDE) => set({ preferredIDE }),

      // worker related methods
      setWorkerList: (workerList) => {
        const { email } = get();
        set((state) => ({
          ...state,
          workerListData: {
            ...state.workerListData,
            [email as string]: workerList,
          },
        }));
      },

      checkAgentTool: (tool) => {
        const { email } = get();
        set((state) => {
          const currentEmail = email as string;
          const originalList = state.workerListData[currentEmail] ?? [];

          console.log('tool!!!', tool);

          const updatedList = originalList
            .map((worker) => {
              const filteredTools =
                worker.tools?.filter((t) => t !== tool) ?? [];
              console.log('filteredTools', filteredTools);
              return { ...worker, tools: filteredTools };
            })
            .filter((worker) => worker.tools.length > 0);

          console.log('updatedList', updatedList);

          return {
            ...state,
            workerListData: {
              ...state.workerListData,
              [currentEmail]: updatedList,
            },
          };
        });
      },

      syncCloudModelWithProviders: async () => {
        const { modelType, cloud_model_type, token } = get();
        if (modelType !== 'cloud' || !token) return;

        try {
          const { proxyFetchGet } = await import('@/api/http');
          const res = await proxyFetchGet('/api/cloud/available-providers');
          const providers =
            (Array.isArray(res) ? res : null) ??
            (Array.isArray((res as any)?.items) ? (res as any).items : null) ??
            (Array.isArray((res as any)?.data) ? (res as any).data : null) ??
            [];
          if (providers.length === 0) return;

          // Check if any provider has the current model_type configured
          const currentSupported = providers.some(
            (p: any) => p.model_type === cloud_model_type
          );
          if (currentSupported) return; // Current model is fine

          // Pick the first configured provider's model_type
          const first = providers.find((p: any) => p.model_type);
          if (first) {
            const newModel = first.model_type as CloudModelType;
            console.log(
              `[authStore] Auto-switching cloud model from '${cloud_model_type}' to '${newModel}' (provider '${first.provider_name}' is configured)`
            );
            set({ cloud_model_type: newModel });
            return;
          }
        } catch {
          // Silently ignore — this is a best-effort optimization
        }
      },
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({
        token: state.token,
        username: state.username,
        email: state.email,
        user_id: state.user_id,
        appearance: state.appearance,
        language: state.language,
        modelType: state.modelType,
        cloud_model_type: state.cloud_model_type,
        initState: state.initState,
        isFirstLaunch: state.isFirstLaunch,
        preferredIDE: state.preferredIDE,
        workerListData: state.workerListData,
      }),
    }
  )
);

// export Hook version for components
export const useAuthStore = authStore;

// export non-Hook version for non-components
export const getAuthStore = () => authStore.getState();

// constant definition
const EMPTY_LIST: Agent[] = [];

// worker list - use in React components
export const useWorkerList = (): Agent[] => {
  const { email, workerListData } = getAuthStore();
  const workerList = workerListData[email as string];
  return workerList ?? EMPTY_LIST;
};

// worker list - use outside React (e.g. in store actions)
export const getWorkerList = (): Agent[] => {
  const { email, workerListData } = getAuthStore();
  return workerListData[email as string] ?? EMPTY_LIST;
};
