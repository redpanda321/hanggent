<div align="center"><a name="readme-top"></a>



### Hanggent: The Open Source Cowork Desktop to Unlock Your Exceptional Productivity

<!-- SHIELD GROUP -->


</div>

<hr/>
<div align="center">

**English** · [Português](./README_PT-BR.md) · [简体中文](./README_CN.md) · [日本語](./README_JA.md) · [Official Site][hanggent-site] · [Documents][docs-site] · [Feedback][github-issue-link]

</div>
<br/>

**Hanggent** is the open source cowork desktop application, empowering you to build, manage, and deploy a custom AI workforce that can turn your most complex workflows into automated tasks. 

Our system introduces a **Multi-Agent Workforce** that **boosts productivity** through parallel execution, customization, and privacy protection.

### ⭐ 100% Open Source - 🥇 Local Deployment - 🏆 MCP Integration

- ✅ **Zero Setup** - No technical configuration required
- ✅ **Multi-Agent Coordination** - Handle complex multi-agent workflows
- ✅ **Enterprise Feature** - SSO/Access control
- ✅ **Local Deployment**
- ✅ **Open Source**
- ✅ **Custom Model Support**
- ✅ **MCP Integration**

<br/>

[![][image-join-us]][join-us]

<details>
<summary><kbd>Table of contents</kbd></summary>

#### TOC

- [🚀 Getting Started](#-getting-started)
  - [🏠 Local Deployment (Recommended)](#-local-deployment-recommended)
  - [⚡ Quick Start (Cloud-Connected)](#-quick-start-cloud-connected)
  - [🏢 Enterprise](#-enterprise)
  - [☁️ Cloud Version](#️-cloud-version)
- [✨ Key features](#-key-features)
  - [🏭 Workforce](#-workforce)
  - [🧠 Comprehensive Model Support](#-comprehensive-model-support)
  - [🔌 MCP Tools Integration (MCP)](#-mcp-tools-integration-mcp)
  - [✋ Human-in-the-Loop](#-human-in-the-loop)
  - [👐 100% Open Source](#-100-open-source)

- [🛠️ Tech Stack](#-tech-stack)
  - [Backend](#backend)
  - [Frontend](#frontend)

####

<br/>

</details>

## **🚀 Getting Started**

> **🔓 Build in Public** — Hanggent is **100% open source** from day one. Every feature, every commit, every decision is transparent. We believe the best AI tools should be built openly with the community, not behind closed doors.

### 🏠 Local Deployment (Recommended)

The recommended way to run Hanggent — fully standalone with complete control over your data, no cloud account required.

👉 **[Full Local Deployment Guide](./server/README_EN.md)**

This setup includes:
- Local backend server with full API
- Local model integration (vLLM, Ollama, LM Studio, etc.)
- Complete isolation from cloud services
- Zero external dependencies

### ⚡ Quick Start (Cloud-Connected)

For a quick preview using our cloud backend — get started in seconds:

#### Prerequisites

- Node.js (version 18-22) and npm

#### Steps

```bash
git clone https://github.com/redpanda321/hanggent.git
cd hanggent
npm install
npm run dev
```

> Note: This mode connects to Hanggent cloud services and requires account registration. For a fully standalone experience, use [Local Deployment](#-local-deployment-recommended) instead.

### 🏢 Enterprise

For organizations requiring maximum security, customization, and control:

- **Exclusive Features** (like SSO & custom development)
- **Scalable Enterprise Deployment**
- **Negotiated SLAs** & implementation services

📧 For further details, please contact us at [redpanda321@gmail.com](mailto:redpanda321@gmail.com).

### ☁️ Cloud Version

For teams who prefer managed infrastructure, we also offer a cloud platform. The fastest way to experience Hanggent's multi-agent AI capabilities without setup complexity. We'll host the models, APIs, and cloud storage, ensuring Hanggent runs flawlessly.

- **Instant Access** - Start building multi-agent workflows in minutes.
- **Managed Infrastructure** - We handle scaling, updates, and maintenance.
- **Premium Support** - Subscribe and get priority assistance from our engineering team.

<br/>

[![image-public-beta]][hanggent-download]

<div align="right">
<a href="https://www.hangent.com/download">Get started at Hangent.com →</a>
</div>

## **✨ Key features**
Unlock the full potential of exceptional productivity with Hanggent’s powerful features—built for seamless integration, smarter task execution, and boundless automation.

### 🏭 Workforce 
Employs a team of specialized AI agents that collaborate to solve complex tasks. Hanggent dynamically breaks down tasks and activates multiple agents to work **in parallel.**

Hanggent pre-defined the following agent workers:

- **Developer Agent:** Writes and executes code, runs terminal commands.
- **Browser Agent:** Searches the web and extracts content.
- **Document Agent:** Creates and manages documents.
- **Multi-Modal Agent:** Processes images and audio.

<br/>

### 🧠 Comprehensive Model Support
Deploy Hanggent locally with your preferred models. 



<br/>

### 🔌 MCP Tools Integration (MCP)
Hanggent comes with massive built-in **Model Context Protocol (MCP)** tools (for web browsing, code execution, Notion, Google suite, Slack etc.), and also lets you **install your own tools**. Equip agents with exactly the right tools for your scenarios – even integrate internal APIs or custom functions – to enhance their capabilities.



<br/>

### ✋ Human-in-the-Loop
If a task gets stuck or encounters uncertainty, Hanggent will automatically request human input. 


<br/>

### 👐 100% Open Source
Hanggent is completely open-sourced. You can download, inspect, and modify the code, ensuring transparency and fostering a community-driven ecosystem for multi-agent innovation.

![Opensource][image-opensource]

<br/>

### 🌐 Multi-language UI
Hanggent supports multilingual UI with language selection and system default detection. Supported languages include English, French, German, Korean, Japanese, Simplified Chinese, Russian, Hindi, and Spanish.

<br/>


<br>

## 🛠️ Tech Stack

### Backend
- **Framework:** FastAPI
- **Package Manager:** uv
- **Async Server:** Uvicorn
- **Authentication:** OAuth 2.0,  Passlib.
- **Multi-agent framework:** CAMEL
    
### Frontend

- **Framework:** React
- **Desktop App Framework:** Electron
- **Language:** TypeScript
- **UI:** Tailwind CSS, Radix UI, Lucide React, Framer Motion
- **State Management:** Zustand
- **Flow Editor:** React Flow
