<div align="center"><a name="readme-top"></a>



### Hanggent：全球首个多智能体工作流，释放卓越生产力

<!-- SHIELD GROUP -->


</div>

<hr/>
<div align="center">

[English](./README.md) · [Português](./README_PT-BR.md) · **简体中文** · [日本語](./README_JA.md) · [官方网站][hanggent-site] · [文档][docs-site] · [反馈][github-issue-link]

</div>
<br/>

**Hanggent** 是开源的 **多智能体工作流** 桌面应用程序，帮助您构建、管理和部署定制化的 AI 工作团队，将最复杂的工作流程转化为自动化任务。

我们的系统引入了 **多智能体工作流**，通过并行执行、定制化和隐私保护 **提升生产力**。

### ⭐ 100% 开源 - 🥇 本地部署 - 🏆 MCP 集成

- ✅ **零配置** - 无需技术设置  
- ✅ **多智能体协作** - 处理复杂的多智能体工作流  
- ✅ **企业级功能** - SSO/访问控制  
- ✅ **本地部署**  
- ✅ **开源**  
- ✅ **支持自定义模型**  
- ✅ **MCP 集成**  

<br/>

[![][image-join-us]][join-us]

<details>
<summary><kbd>目录</kbd></summary>

#### 目录

- [🚀 快速开始](#-快速开始)
  - [☁️ 云版本](#️-云版本)
  - [🏠 自托管（社区版）](#-自托管社区版)
  - [🏢 企业版](#-企业版)
- [✨ 核心功能](#-核心功能)
  - [🏭 工作流](#-工作流)
  - [🧠 全面模型支持](#-全面模型支持)
  - [🔌 MCP 工具集成](#-mcp-工具集成)
  - [✋ 人工介入](#-人工介入)
  - [👐 100% 开源](#-100-开源)
- [🧩 使用案例](#-使用案例)
- [🛠️ 技术栈](#️-技术栈)
  - [后端](#后端)
  - [前端](#前端)


####

<br/>

</details>

## **🚀 快速开始**

有三种方式开始使用 Hanggent：

### ☁️ 云版本

最快体验 Hanggent 多智能体 AI 能力的方式是通过我们的云平台，适合希望无需复杂设置即可立即使用的团队和个人。我们将托管模型、API 和云存储，确保 Hanggent 流畅运行。

- **即时访问** - 几分钟内开始构建多智能体工作流。  
- **托管基础设施** - 我们负责扩展、更新和维护。  
- **优先支持** - 订阅后获得工程团队的优先协助。  

<br/>

[![image-public-beta]][hanggent]

<div align="right">
<a href="https://www.hangent.com">Get started at Hangent.com →</a>
</div>

### 🏠 自托管（社区版）

适合偏好本地控制、数据隐私或定制的用户，此选项适用于需要以下功能的组织：

- **数据隐私** - 敏感数据保留在您的基础设施内。  
- **定制化** - 修改和扩展平台以满足需求。  
- **成本控制** - 避免大规模部署的持续云费用。  

#### 1. 前提条件

- Node.js (版本 18-22) 和 npm  

#### 2. 快速开始

```bash
git clone https://github.com/redpanda321/hanggent
cd hanggent
npm install
npm run dev
```

#### 3. 本地开发(使用完全和云端服务分离的版本)
[server/README_CN.md](./server/README_CN.md)

### 🏢 企业版

适合需要最高安全性、定制化和控制的组织：

- **商业许可证** - [查看许可证 →](LICENSE)  
- **独家功能**（如 SSO 和定制开发）  
- **可扩展的企业部署**  
- **协商的 SLA** 和实施服务  

📧 更多详情，请联系 [redpanda321@gmail.com](mailto:redpanda321@gmail.com)。

## **✨ 核心功能**
通过 Hanggent 的强大功能释放卓越生产力的全部潜力——专为无缝集成、智能任务执行和无边界自动化而设计。

### 🏭 工作流  
部署一支专业 AI 智能体团队，协作解决复杂任务。Hanggent 动态分解任务并激活多个智能体 **并行工作**。

Hanggent 预定义了以下智能体工作者：

- **开发智能体**：编写和执行代码，运行终端命令。  
- **搜索智能体**：搜索网络并提取内容。  
- **文档智能体**：创建和管理文档。  
- **多模态智能体**：处理图像和音频。  

<br/>

### 🧠 全面模型支持  
使用您偏好的模型本地部署 Hanggent。  

<br/>

### 🔌 MCP 工具集成  
Hanggent 内置大量 **模型上下文协议（MCP）** 工具（用于网页浏览、代码执行、Notion、Google 套件、Slack 等），并允许您 **安装自己的工具**。为智能体配备适合您场景的工具——甚至集成内部 API 或自定义功能——以增强其能力。

<br/>

### ✋ 人工介入  
如果任务卡住或遇到不确定性，Hanggent 会自动请求人工输入。  

<br/>

### 👐 100% 开源  
Hanggent 完全开源。您可以下载、检查和修改代码，确保透明度并促进多智能体创新的社区驱动生态系统。

![Opensource][image-opensource]


## 🛠️ 技术栈

### 后端
- **框架：** FastAPI  
- **包管理器：** uv  
- **异步服务器：** Uvicorn  
- **认证：** OAuth 2.0, Passlib  
- **多智能体框架：** CAMEL  

### 前端
- **框架：** React  
- **桌面应用框架：** Electron  
- **语言：** TypeScript  
- **UI：** Tailwind CSS, Radix UI, Lucide React, Framer Motion  
- **状态管理：** Zustand  
- **流程编辑器：** React Flow  
