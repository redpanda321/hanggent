<div align="center"><a name="readme-top"></a>


### Hanggent: O Desktop Cowork Open Source para Desbloquear sua Produtividade Excepcional

<!-- SHIELD GROUP --> 


</div>

<hr/>
<div align="center">

[English](./README.md) · **Português** · [简体中文](./README_CN.md) · [日本語](./README_JA.md) · [Site Oficial][hanggent-site] · [Documentação][docs-site] · [Feedback][github-issue-link]

</div>
<br/>

**Hanggent** é a aplicação desktop cowork open source que capacita você a construir, gerenciar e implantar uma força de trabalho de IA personalizada, capaz de transformar seus fluxos de trabalho mais complexos em tarefas automatizadas.

Nosso sistema introduz uma **Força de Trabalho Multiagente** que **aumenta a produtividade** por meio de execução paralela, personalização e proteção de privacidade.

### ⭐ 100% Open Source - 🥇 Implantação Local - 🏆 Integração MCP

- ✅ **Zero Configuração** - Nenhuma configuração técnica necessária
- ✅ **Coordenação Multiagente** - Gerencie fluxos de trabalho complexos com múltiplos agentes
- ✅ **Recursos Corporativos** - SSO / Controle de acesso
- ✅ **Implantação Local**
- ✅ **Open Source**
- ✅ **Suporte a Modelos Personalizados**
- ✅ **Integração MCP**

<br/>

[![][image-join-us]][join-us]

<details>
<summary><kbd>Sumário</kbd></summary>

#### TOC

- [🚀 Primeiros Passos](#-primeiros-passos)
  - [🏠 Implantação Local (Recomendado)](#-implantação-local-recomendado)
  - [⚡ Início Rápido (Conectado à Nuvem)](#-início-rápido-conectado-à-nuvem)
  - [🏢 Empresarial](#-empresarial)
  - [☁️ Versão em Nuvem](#️-versão-em-nuvem)
- [✨ Principais Recursos](#-principais-recursos)
  - [🏭 Força de Trabalho](#-força-de-trabalho)
  - [🧠 Suporte Abrangente a Modelos](#-suporte-abrangente-a-modelos)
  - [🔌 Integração de Ferramentas MCP (MCP)](#-integração-de-ferramentas-mcp-mcp)
  - [✋ Humano no Circuito](#-humano-no-circuito)
  - [👐 100% Código Aberto](#-100-código-aberto)

- [🛠️ Stack Tecnológica](#-stack-tecnológica)
  - [Backend](#backend)
  - [Frontend](#frontend)
- [🌟 Mantendo-se à Frente](#-mantendo-se-à-frente)
- 
####

<br/>

</details>

## **🚀 Primeiros Passos**

> **🔓 Construído em Público** — Hanggent é **100% open source** desde o primeiro dia. Cada funcionalidade, cada commit e cada decisão são transparentes. Acreditamos que as melhores ferramentas de IA devem ser construídas abertamente com a comunidade, e não a portas fechadas.

### 🏠 Implantação Local (Recomendado)

A forma recomendada de executar o Hanggent — totalmente independente, com controle completo sobre seus dados, sem necessidade de conta em nuvem.

👉 **[Guia Completo de Implantação Local](./server/README_EN.md)**

Esta configuração inclui:
- Servidor backend local com API completa
- Integração de modelos locais (vLLM, Ollama, LM Studio, etc.)
- Isolamento completo de serviços em nuvem
- Zero dependências externas

### ⚡ Início Rápido (Conectado à Nuvem)

Para uma visualização rápida usando nosso backend em nuvem — comece em segundos:

#### Pré-requisitos

- Node.js (versão 18–22) e npm

#### Passos

```bash
git clone https://github.com/hanggent
cd hanggent
npm install
npm run dev
```

> Nota: Este modo se conecta aos serviços em nuvem do Hanggent e requer registro de conta. Para uma experiência totalmente independente, utilize a [Implantação Local](#-implantação-local-recomendado) em vez disso.

### 🏢 Empresarial

Para organizações que requerem máxima segurança, personalização e controle:

- **Recursos Exclusivos** (como SSO e desenvolvimento personalizado)
- **Implantação Empresarial Escalável**
- **SLAs Negociados** e serviços de implementação

📧 Para mais detalhes, entre em contato conosco em [redpanda321@gmail.com](mailto:redpanda321@gmail.com).

### ☁️ Versão em Nuvem

Para equipes que preferem infraestrutura gerenciada, também oferecemos uma plataforma em nuvem. A maneira mais rápida de experimentar as capacidades de IA multi-agente do Hanggent sem complexidade de configuração. Nós hospedaremos os modelos, APIs e armazenamento em nuvem, garantindo que o Hanggent funcione perfeitamente.

- **Acesso Instantâneo** - Comece a construir fluxos de trabalho multi-agente em minutos.
- **Infraestrutura Gerenciada** - Nós cuidamos da escalabilidade, atualizações e manutenção.
- **Suporte Premium** - Assine e obtenha assistência prioritária de nossa equipe de engenharia.

<br/>

[![image-public-beta]][hanggent-download]

<div align="right">
<a href="https://www.hangent.com/download">Comece em Hangent.com →</a>
</div>

## **✨ Principais recursos**
Desbloqueie todo o potencial de produtividade excepcional com os poderosos recursos do Hanggent—construídos para integração perfeita, execução de tarefas mais inteligente e automação ilimitada.

### 🏭 Força de Trabalho 
Emprega uma equipe de agentes de IA especializados que colaboram para resolver tarefas complexas. O Hanggent divide dinamicamente as tarefas e ativa múltiplos agentes para trabalhar **em paralelo.**

O Hanggent pré-definiu os seguintes agentes trabalhadores:

- **Agente Desenvolvedor:** Escreve e executa código, executa comandos de terminal.
- **Agente de Busca:** Pesquisa na web e extrai conteúdo.
- **Agente de Documento:** Cria e gerencia documentos.
- **Agente Multi-Modal:** Processa imagens e áudio.



<br/>

### 🧠 Suporte Abrangente a Modelos
Implante o Hanggent localmente com seus modelos preferidos.


<br/>

### 🔌 Integração de Ferramentas MCP (MCP)
O Hanggent vem com ferramentas massivas integradas do **Protocolo de Contexto de Modelo (MCP)** (para navegação web, execução de código, Notion, Google suite, Slack etc.), e também permite que você **instale suas próprias ferramentas**. Equipe os agentes com exatamente as ferramentas certas para seus cenários – até mesmo integre APIs internas ou funções personalizadas – para aprimorar suas capacidades.


<br/>

### ✋ Humano no Circuito
Se uma tarefa ficar travada ou encontrar incerteza, o Hanggent solicitará automaticamente entrada humana.


<br/>

### 👐 100% Código Aberto
O Hanggent é completamente de código aberto. Você pode baixar, inspecionar e modificar o código, garantindo transparência e promovendo um ecossistema impulsionado pela comunidade para inovação multi-agente.

![Código Aberto][image-opensource]


<br>

## 🛠️ Stack Tecnológica

### Backend
- **Framework:** FastAPI
- **Gerenciador de Pacotes:** uv
- **Servidor Assíncrono:** Uvicorn
- **Autenticação:** OAuth 2.0, Passlib
- **Framework Multiagente:** CAMEL
    
### Frontend

- **Framework:** React
- **Framework de App Desktop:** Electron
- **Linguagem:** TypeScript
- **UI:** Tailwind CSS, Radix UI, Lucide React, Framer Motion
- **Gerenciamento de Estado:** Zustand
- **Editor de Fluxo:** React Flow
