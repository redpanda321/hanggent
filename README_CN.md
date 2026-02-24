<div align="center"><a name="readme-top"></a>

[![][image-head]][hanggent-site]

[![][image-seperator]][hanggent-site]

### Hanggent：全球首个多智能体工作流，释放卓越生产力

<!-- SHIELD GROUP -->

[![][download-shield]][hanggent-download]
[![][github-star]][hanggent-github]
[![][social-x-shield]][social-x-link]
[![][discord-image]][discord-url]<br>
[![][join-us-image]][join-us]

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

[![image-public-beta]][hanggent-download]

<div align="right">
<a href="https://www.hangent.com/download">Get started at Hangent.com →</a>
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
git clone https://github.com/hanggent-ai/hanggent.git
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

![Workforce](https://hanggent-ai.github.io/.github/assets/gif/feature_dynamic_workforce.gif)

<br/>

### 🧠 全面模型支持  
使用您偏好的模型本地部署 Hanggent。  

![Model](https://hanggent-ai.github.io/.github/assets/gif/feature_local_model.gif)

<br/>

### 🔌 MCP 工具集成  
Hanggent 内置大量 **模型上下文协议（MCP）** 工具（用于网页浏览、代码执行、Notion、Google 套件、Slack 等），并允许您 **安装自己的工具**。为智能体配备适合您场景的工具——甚至集成内部 API 或自定义功能——以增强其能力。

![MCP](https://hanggent-ai.github.io/.github/assets/gif/feature_add_mcps.gif)

<br/>

### ✋ 人工介入  
如果任务卡住或遇到不确定性，Hanggent 会自动请求人工输入。  

![Human-in-the-loop](https://hanggent-ai.github.io/.github/assets/gif/feature_human_in_the_loop.gif)

<br/>

### 👐 100% 开源  
Hanggent 完全开源。您可以下载、检查和修改代码，确保透明度并促进多智能体创新的社区驱动生态系统。

![Opensource][image-opensource]

<br/>

## 🧩 使用案例

### 1. 棕榈泉网球旅行行程与 Slack 摘要 [回放 ▶️](https://www.hangent.com/download?share_token=IjE3NTM0MzUxNTEzMzctNzExMyI.aIeysw.MUeG6ZcBxI1GqvPDvn4dcv-CDWw__1753435151337-7113)

<details>
<summary><strong>提示：</strong> <kbd>我们是两个网球爱好者，想去观看 2026 年棕榈泉的网球比赛... </kbd></summary>
<br>
我们是两个网球爱好者，想去观看 2026 年棕榈泉的网球比赛。我住在旧金山——请准备一个详细的行程，包括航班、酒店、为期 3 天的活动安排——围绕半决赛/决赛的时间。我们喜欢徒步、素食和 Spa。预算为 5,000 美元。行程应是一个详细的时间表，包括时间、活动、费用、其他细节，以及购买门票/预订的链接（如适用）。完成后，请生成一份关于此次旅行的 HTML 报告；编写此计划的摘要，并将文本摘要和报告 HTML 链接发送到 Slack #tennis-trip-sf 频道。
</details>

<br>

### 2. 从 CSV 银行数据生成 Q2 报告 [回放 ▶️](https://www.hangent.com/download?share_token=IjE3NTM1MjY4OTE4MDgtODczOSI.aIjJmQ.WTdoX9mATwrcBr_w53BmGEHPo8U__1753526891808-8739)

<details>
<summary><strong>提示：</strong> <kbd>请根据我桌面上的银行转账记录文件 bank_transacation.csv... </kbd></summary>
<br>
请根据我桌面上的银行转账记录文件 bank_transacation.csv，帮我准备一份 Q2 财务报表，生成带图表的 HTML 报告，向投资者展示我们的支出情况。
</details>

<br>

### 3. 英国医疗市场调研报告自动化 [回放 ▶️](https://www.hangent.com/download?share_token=IjE3NTMzOTM1NTg3OTctODcwNyI.aIey-Q.Jh9QXzYrRYarY0kz_qsgoj3ewX0__1753393558797-8707)

<details>
<summary><strong>提示：</strong> <kbd>分析英国医疗保健行业以支持我下一家公司的规划... </kbd></summary>
<br>
分析英国医疗保健行业以支持我下一家公司的规划。提供全面的市场概览，包括当前趋势、增长预测和相关法规。识别市场中5-10个主要机会、缺口或服务不足的细分领域。将所有发现整理成结构清晰、专业的HTML报告。完成后，向Slack的#hanggentr-product-test频道发送消息，以便与团队成员对齐报告内容。。
</details>

<br>

### 4. 德国电动滑板市场可行性 [回放 ▶️](https://www.hangent.com/download?share_token=IjE3NTM2NTI4MjY3ODctNjk2Ig.aIjGiA.t-qIXxk_BZ4ENqa-yVIm0wMVyXU__1753652826787-696)

<details>
<summary><strong>提示：</strong> <kbd>我们是一家生产高端电动滑板的公司... </kbd></summary>
<br>
我们是一家生产高端电动滑板的公司，正在考虑进入德国市场。请为我准备一份详细的市场进入可行性报告。报告需涵盖以下方面：1. 市场规模与法规；2. 消费者画像；3. 渠道与分销；4. 成本与定价；5. 综合报告与演示。
</details>

<br>

### 5. 多智能体产品发布的 SEO 审计 [回放 ▶️](https://www.hangent.com/download?share_token=IjE3NTM2OTk5NzExNDQtNTY5NiI.aIex0w.jc_NIPmfIf9e3zGt-oG9fbMi3K4__1753699971144-5696)

<details>
<summary><strong>提示：</strong> <kbd>为了支持我们新的多智能体产品发布... </kbd></summary>
<br>
为了支持我们新的多智能体产品发布，请对我们的官方网站 (https://www.hangent.com) 进行全面的 SEO 审计，并提供带有可操作建议的详细优化报告。
</details>

<br>

### 6. 识别下载文件夹中的重复文件 [回放 ▶️](https://www.hangent.com/download?share_token=IjE3NTM3NjAzODgxNzEtMjQ4Ig.aIhKLQ.epOG--0Nj0o4Bqjtdqm9OZdaqRQ__1753760388171-248)

<details>
<summary><strong>提示：</strong> <kbd>我的 Documents 目录中有一个名为 mydocs 的文件夹... </kbd></summary>
<br>
我的 Documents 目录中有一个名为 mydocs 的文件夹。请扫描并识别所有完全或近似重复的文件——包括内容相同、文件大小或格式相同的文件（即使文件名或扩展名不同）。清晰列出它们，按相似性分组。
</details>

<br>

### 7. 添加签名到 PDF [回放 ▶️](https://www.hangent.com/download?share_token=IjE3NTQwOTU0ODM0NTItNTY2MSI.aJCHrA.Mg5yPOFqj86H_GQvvRNditzepXc__1754095483452-5661)

<details>
<summary><strong>提示:</strong> <kbd>请将此签名图片添加到 PDF 中的签名区域 ... </kbd></summary>
<br>
请将此签名图片添加到 PDF 中的签名区域。你可以安装命令行工具 “tesseract”（该工具通过 OCR 技术可可靠定位“签名区域”），以帮助完成此任务。
</details>

<br>

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
