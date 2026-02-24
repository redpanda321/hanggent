<div align="center"><a name="readme-top"></a>

[![][image-head]][hanggent-site]

[![][image-seperator]][hanggent-site]

### Hanggent: The Open Source Cowork Desktop to Unlock Your Exceptional Productivity

<!-- SHIELD GROUP -->

[![][download-shield]][hanggent-download]
[![][github-star]][hanggent-github]
[![][social-x-shield]][social-x-link]
[![][discord-image]][discord-url]<br>
[![][join-us-image]][join-us]

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
- [🧩 Use Cases](#-use-cases)
- [🛠️ Tech Stack](#-tech-stack)
  - [Backend](#backend)
  - [Frontend](#frontend)
- [🌟 Staying ahead](#staying-ahead)
- [🗺️ Roadmap](#-roadmap)
- [📖 Contributing](#-contributing)
  - [Main Contributors](#main-contributors)
  - [Distinguished Ambassador](#distinguished-ambassador)
- [Ecosystem](#ecosystem)
- [📄 Open Source License](#-open-source-license)
- [🌐 Community & contact](#-community--contact)

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
git clone https://github.com/hanggent-ai/hanggent.git
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

![Workforce](https://hanggent-ai.github.io/.github/assets/gif/feature_dynamic_workforce.gif)

<br/>

### 🧠 Comprehensive Model Support
Deploy Hanggent locally with your preferred models. 

![Model](https://hanggent-ai.github.io/.github/assets/gif/feature_local_model.gif)

<br/>

### 🔌 MCP Tools Integration (MCP)
Hanggent comes with massive built-in **Model Context Protocol (MCP)** tools (for web browsing, code execution, Notion, Google suite, Slack etc.), and also lets you **install your own tools**. Equip agents with exactly the right tools for your scenarios – even integrate internal APIs or custom functions – to enhance their capabilities.

![MCP](https://hanggent-ai.github.io/.github/assets/gif/feature_add_mcps.gif)

<br/>

### ✋ Human-in-the-Loop
If a task gets stuck or encounters uncertainty, Hanggent will automatically request human input. 

![Human-in-the-loop](https://hanggent-ai.github.io/.github/assets/gif/feature_human_in_the_loop.gif)

<br/>

### 👐 100% Open Source
Hanggent is completely open-sourced. You can download, inspect, and modify the code, ensuring transparency and fostering a community-driven ecosystem for multi-agent innovation.

![Opensource][image-opensource]

<br/>

### 🌐 Multi-language UI
Hanggent supports multilingual UI with language selection and system default detection. Supported languages include English, French, German, Korean, Japanese, Simplified Chinese, Russian, Hindi, and Spanish.

<br/>

## 🧩 Use Cases

### 1. Palm Springs Tennis Trip Itinerary with Slack Summary [Replay ▶️](https://www.hangent.com/download?share_token=IjE3NTM0MzUxNTEzMzctNzExMyI.aIeysw.MUeG6ZcBxI1GqvPDvn4dcv-CDWw__1753435151337-7113)

<details>
<summary><strong>Prompt:</strong> <kbd>We are two tennis fans and want to go see the tennis tournament ... </kbd></summary>
<br>
We are two tennis fans and want to go see the tennis tournament in Palm Springs 2026. I live in SF - please prepare a detailed itinerary with flights, hotels, things to do for 3 days - around the time semifinal/finals are happening. We like hiking, vegan food and spas. Our budget is $5K. The itinerary should be a detailed timeline of time, activity, cost, other details and if applicable a link to buy tickets/make reservations etc. for the item. Some preferences .Spa access would be nice but not necessary. When you finish this task, please generate a html report about this trip; write a summary of this plan and send text summary and report html link to slack #tennis-trip-sf channel.
</details>

<br>

### 2. Generate Q2 Report from CSV Bank Data [Replay ▶️](https://www.hangent.com/download?share_token=IjE3NTM1MjY4OTE4MDgtODczOSI.aIjJmQ.WTdoX9mATwrcBr_w53BmGEHPo8U__1753526891808-8739)

<details>
<summary><strong>Prompt:</strong> <kbd>Please help me prepare a Q2 financial statement based on my bank ... </kbd></summary>
<br>
Please help me prepare a Q2 financial statement based on my bank transfer record file bank_transacation.csv in my desktop to a html report with chart to investors how much we have spent.
</details>

<br>

### 3. UK Healthcare Market Research Report Automation [Replay ▶️](https://www.hangent.com/download?share_token=IjE3NTMzOTM1NTg3OTctODcwNyI.aIey-Q.Jh9QXzYrRYarY0kz_qsgoj3ewX0__1753393558797-8707)

<details>
<summary><strong>Prompt:</strong> <kbd>Analyze the UK healthcare industry to support the planning ... </kbd></summary>
<br>
Analyze the UK healthcare industry to support the planning of my next company. Provide a comprehensive market overview, including current trends, growth projections, and relevant regulations. Identify the top 5–10 major opportunities, gaps, or underserved segments within the market. Present all findings in a well-structured, professional HTML report. Then send a message to slack #hanggentr-product-test channel when this task is done to align the report content with my teammates.
</details>

<br>

### 4. German Electric Skateboard Market Feasibility [Replay ▶️](https://www.hangent.com/download?share_token=IjE3NTM2NTI4MjY3ODctNjk2Ig.aIjGiA.t-qIXxk_BZ4ENqa-yVIm0wMVyXU__1753652826787-696)

<details>
<summary><strong>Prompt:</strong> <kbd>We are a company that produces high-end electric skateboards ... </kbd></summary>
<br>
We are a company that produces high-end electric skateboards, and we are considering entering the German market. Please prepare a detailed market entry feasibility report for me. The report needs to cover the following aspects:
1. Market Size & Regulations: Research the market size, annual growth rate, key players, and market share for Personal Light Electric Vehicles (PLEVs) in Germany. Simultaneously, provide a detailed breakdown and summary of German laws and regulations concerning the use of electric skateboards on public roads, including certification requirements (such as ABE certification) and insurance policies.
2. Consumer Profile: Analyze the profile of potential German consumers, including their age, income level, primary usage scenarios (commuting, recreation), key purchasing decision drivers (price, performance, brand, design), and the channels they typically use to gather information (forums, social media, offline retail stores).
3. Channels & Distribution: Investigate Germany’s mainstream online electronics sales platforms (e.g., Amazon.de, MediaMarkt.de) and high-end sporting goods offline retail chains. List the top 5 potential online and offline distribution partners and find the contact information for their purchasing departments, if possible.
4. Costing & Pricing: Based on the product cost structure in my Product_Cost.csv file on my desktop, and taking into account German customs duties, Value Added Tax (VAT), logistics and warehousing costs, and potential marketing expenses, estimate a Manufacturer’s Suggested Retail Price (MSRP) and analyze its competitiveness in the market.
5. Comprehensive Report & Presentation: Summarize all research findings into an HTML report file. The content should include data charts, key findings, and a final market entry strategy recommendation (Recommended / Not Recommended / Recommended with Conditions).
</details>

<br>

### 5. SEO Audit for Workforce Multiagent Launch [Replay ▶️](https://www.hangent.com/download?share_token=IjE3NTM2OTk5NzExNDQtNTY5NiI.aIex0w.jc_NIPmfIf9e3zGt-oG9fbMi3K4__1753699971144-5696)

<details>
<summary><strong>Prompt:</strong> <kbd>To support the launch of our new Workforce Multiagent product ... </kbd></summary>
<br>
To support the launch of our new Workforce Multiagent product, please run a thorough SEO audit on our official website (https://www.hangent.com) and deliver a detailed optimization report with actionable recommendations.
</details>

<br>

### 6. Identify Duplicate Files in Downloads [Replay ▶️](https://www.hangent.com/download?share_token=IjE3NTM3NjAzODgxNzEtMjQ4Ig.aIhKLQ.epOG--0Nj0o4Bqjtdqm9OZdaqRQ__1753760388171-248)

<details>
<summary><strong>Prompt:</strong> <kbd>I have a folder named mydocs inside my Documents directory ... </kbd></summary>
<br>
I have a folder named mydocs inside my Documents directory. Please scan it and identify all files that are exact or near duplicates — including those with identical content, file size, or format (even if file names or extensions differ). List them clearly, grouped by similarity.
</details>

<br>

### 7. Add Signature to PDF [Replay ▶️](https://www.hangent.com/download?share_token=IjE3NTQwOTU0ODM0NTItNTY2MSI.aJCHrA.Mg5yPOFqj86H_GQvvRNditzepXc__1754095483452-5661)

<details>
<summary><strong>Prompt:</strong> <kbd>Please add this signature image to the Signature Areas in the PDF ... </kbd></summary>
<br>
Please add this signature image to the Signature Areas in the PDF. You could install the CLI tool ‘tesseract’ (needed for reliable location of ‘Signature Areas’ via OCR) to help finish this task.
</details>

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

## 🌟 Staying ahead

> \[!IMPORTANT]
>
> **Star Hanggent**, You will receive all release notifications from GitHub without any delay \~ ⭐️

![][image-star-us]

## 🗺️ Roadmap

| Topics                   | Issues   | Discord Channel |
| ------------------------ | -- |-- |
| **Context Engineering** | - Prompt caching<br> - System prompt optimize<br> - Toolkit docstring optimize<br> - Context compression | [**Join Discord →**](https://discord.gg/D2e3rBWD) |
| **Multi-modal Enhancement** | - More accurate image understanding when using browser<br> - Advanced video generation | [**Join Discord →**](https://discord.gg/kyapNCeJ) |
| **Multi-agent system** | - Workforce support fixed workflow<br> - Workforce support multi-round conversion | [**Join Discord →**](https://discord.gg/bFRmPuDB) |
| **Browser Toolkit** | - BrowseComp integration<br> - Benchmark improvement<br> - Forbid repeated page visiting<br> - Automatic cache button clicking | [**Join Discord →**](https://discord.gg/NF73ze5v) |
| **Document Toolkit** | - Support dynamic file editing | [**Join Discord →**](https://discord.gg/4yAWJxYr) |
| **Terminal Toolkit** | - Benchmark improvement<br> - Terminal-Bench integration | [**Join Discord →**](https://discord.gg/FjQfnsrV) |
| **Environment & RL** | - Environment design<br> - Data-generation<br> - RL framework integration (VERL, TRL, OpenRLHF) | [**Join Discord →**](https://discord.gg/MaVZXEn8) |


## [🤝 Contributing][contribution-link]

We believe in building trust and embracing all forms of open-source collaborations. Your creative contributions help drive the innovation of `Hanggent`. Explore our GitHub issues and projects to dive in and show us what you’ve got 🤝❤️ [Contribution Guideline][contribution-link]


## Contributors

<a href="https://github.com/hanggent-ai/hanggent/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=hanggent-ai/hanggent" />
</a>

Made with [contrib.rocks](https://contrib.rocks).

<br>


## **📄 Open Source License**

This repository is licensed under the [Apache License 2.0](LICENSE).
