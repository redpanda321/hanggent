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

import { Provider } from '@/types';

export const INIT_PROVODERS: Provider[] = [
  {
    id: 'openai',
    name: 'OpenAI',
    apiKey: '',
    apiHost: 'https://api.openai.com/v1',
    description: 'OpenAI model configuration.',
    is_valid: false,
    model_type: '',
  },
  {
    id: 'anthropic',
    name: 'Anthropic',
    apiKey: '',
    apiHost: 'https://api.anthropic.com/v1/',
    description: 'Anthropic Claude API configuration',
    is_valid: false,
    model_type: '',
  },
  {
    id: 'openrouter',
    name: 'OpenRouter',
    apiKey: '',
    apiHost: 'https://openrouter.ai/api/v1',
    description: 'OpenRouter model configuration.',
    is_valid: false,
    model_type: '',
  },
  {
    id: 'tongyi-qianwen',
    name: 'Qwen',
    apiKey: '',
    apiHost: 'https://dashscope-intl.aliyuncs.com/compatible-mode/v1',
    description:
      'Qwen model configuration. Intl: dashscope-intl.aliyuncs.com; China: dashscope.aliyuncs.com.',
    is_valid: false,
    model_type: '',
  },
  {
    id: 'deepseek',
    name: 'Deepseek',
    apiKey: '',
    apiHost: 'https://api.deepseek.com',
    description: 'DeepSeek model configuration.',
    is_valid: false,
    model_type: '',
  },
  {
    id: 'minimax',
    name: 'Minimax',
    apiKey: '',
    apiHost: 'https://api.minimax.io/v1',
    description: 'Minimax model configuration.',
    is_valid: false,
    model_type: '',
  },
  {
    id: 'Z.ai',
    name: 'Z.ai',
    apiKey: '',
    apiHost: 'https://api.z.ai/api/coding/paas/v4/',
    description: 'Z.ai model configuration.',
    is_valid: false,
    model_type: '',
  },
  {
    id: 'kimi',
    name: 'KIMI (Moonshot)',
    apiKey: '',
    apiHost: 'https://api.moonshot.ai/v1',
    description: 'KIMI / Moonshot AI model configuration.',
    is_valid: false,
    model_type: '',
  },
  {
    id: 'glm',
    name: 'GLM (BigModel)',
    apiKey: '',
    apiHost: 'https://open.bigmodel.cn/api/paas/v4/',
    description: 'GLM / BigModel OpenAI-compatible API configuration.',
    is_valid: false,
    model_type: '',
  },
  {
    id: 'aws-bedrock',
    name: 'AWS Bedrock',
    apiKey: '',
    apiHost: '',
    description: 'AWS Bedrock model configuration.',
    hostPlaceHolder: 'e.g. https://bedrock-runtime.{{region}}.amazonaws.com',
    is_valid: false,
    model_type: '',
  },
  {
    id: 'azure',
    name: 'Azure',
    apiKey: '',
    apiHost: '',
    description: 'Azure OpenAI model configuration.',
    hostPlaceHolder: 'e.g.https://{{your-resource-name}}.openai.azure.com',
    externalConfig: [
      {
        key: 'api_version',
        name: 'API Version',
        value: '',
      },
      {
        key: 'azure_deployment_name',
        name: 'Deployment Name',
        value: '',
      },
    ],
    is_valid: false,
    model_type: '',
  },
  {
    id: 'openai-compatible-model',
    name: 'OpenAI Compatible',
    apiKey: '',
    apiHost: '',
    description: 'OpenAI-compatible API endpoint configuration.',
    hostPlaceHolder: 'e.g. https://api.x.ai/v1',
    is_valid: false,
    model_type: '',
  },
  {
    id: 'xai',
    name: 'xAI',
    apiKey: '',
    apiHost: 'https://api.x.ai/v1',
    description: 'xAI Grok model configuration.',
    is_valid: false,
    model_type: '',
  },
];
