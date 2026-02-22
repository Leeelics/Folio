# Claude Code 插件指导说明书

> 以 Folio 项目为案例，涵盖插件管理、核心插件详解、多终端协作开发实战。

---

## 目录

1. [插件管理基础](#1-插件管理基础)
2. [ecc 插件详解](#2-ecc-插件详解)
3. [claude-mem 插件详解](#3-claude-mem-插件详解)
4. [多终端协作开发实战](#4-多终端协作开发实战)
5. [推荐日常工作流](#5-推荐日常工作流)
6. [多终端协作开发完整指南](#6-多终端协作开发完整指南)

---

## 1. 插件管理基础

### 1.1 插件体系结构

Claude Code 的扩展能力分为三层：

| 层级 | 说明 | 示例 |
|------|------|------|
| **Plugins** | 第三方扩展包，可包含 agents、skills、MCP servers | `ecc`, `claude-mem` |
| **Skills** | 可通过 `/plugin:skill-name` 调用的专项能力 | `/ecc:tdd`, `/claude-mem:mem-search` |
| **MCP Servers** | Model Context Protocol 服务，提供工具级别的能力 | `claude-mem` 的 `search`、`save_memory` 工具 |

一个插件可以同时提供 agents、skills 和 MCP servers。例如 `ecc` 提供 9 个 agents 和 6 个 skills，而 `claude-mem` 通过 MCP server 提供 4 个工具 + 3 个 skills。

> 注意：插件的 skills 需要使用完整前缀调用，格式为 `/plugin-name:skill-name`。例如 `/ecc:tdd`，不能简写为 `/tdd`。

### 1.2 配置文件位置

```
~/.claude/settings.json          # 用户级配置（插件启用、marketplace 源）
<project>/.claude/settings.json  # 项目级配置（可覆盖用户级）
<project>/CLAUDE.md              # 项目指令文件（插件使用约定等）
```

当前 Folio 项目的用户级配置：

```json
{
  "enabledPlugins": {
    "ecc@ecc": true,
    "document-skills@anthropic-agent-skills": true,
    "claude-mem@thedotmack": true
  },
  "extraKnownMarketplaces": {
    "ecc": {
      "source": {
        "source": "github",
        "repo": "Leeelics/everything-claude-code"
      }
    }
  }
}
```

### 1.3 安装插件

**方式一：通过 Marketplace（推荐）**

```bash
# 在 Claude Code 交互界面中
/install-plugin
# 按提示选择 marketplace 和插件名
```

对于官方 marketplace 中的插件（如 `document-skills`、`claude-mem`），直接搜索安装即可。

**方式二：添加自定义 Marketplace 源**

部分插件不在官方 marketplace 中（如 `ecc`），需要先添加源：

在 `~/.claude/settings.json` 中添加：

```json
{
  "extraKnownMarketplaces": {
    "ecc": {
      "source": {
        "source": "github",
        "repo": "Leeelics/everything-claude-code"
      }
    }
  }
}
```

然后在 `enabledPlugins` 中启用：

```json
{
  "enabledPlugins": {
    "ecc@ecc": true
  }
}
```

### 1.4 查看已安装插件

```bash
# 在 Claude Code 中查看当前加载的插件
/plugins
```

也可以直接查看配置文件：

```bash
cat ~/.claude/settings.json | jq '.enabledPlugins'
```

### 1.5 升级插件

插件从 GitHub 仓库拉取，升级方式：

1. 清除本地缓存，让 Claude Code 重新拉取最新版本
2. 重启 Claude Code 会话

```bash
# 清除插件缓存（路径可能因系统而异）
rm -rf ~/.claude/plugins/cache/
# 重新启动 Claude Code
```

### 1.6 删除插件

在 `~/.claude/settings.json` 中将对应插件设为 `false` 或删除该行：

```json
{
  "enabledPlugins": {
    "ecc@ecc": false
  }
}
```

重启 Claude Code 生效。

---

## 2. ecc 插件详解

### 2.1 概览

- **来源**: Fork 自 [affaan-m/everything-claude-code](https://github.com/affaan-m/everything-claude-code)，重命名为 `ecc` 以缩短 CLI 命令前缀
- **Fork 仓库**: [Leeelics/everything-claude-code](https://github.com/Leeelics/everything-claude-code)
- **定位**: Claude Code 的"瑞士军刀"，提供代码审查、架构设计、TDD、E2E 测试、安全审计、文档生成等全方位开发辅助
- **安装方式**: 自定义 marketplace 源（见 1.3）
- **为什么 fork**: 原插件名 `everything-claude-code`（24 字符）导致 CLI 自动补全菜单中 skill 名称被截断。Fork 后仅修改 `plugin.json` 的 name 字段为 `ecc`，合并上游更新冲突概率极低

### 2.2 可用 Agents（9 个）

Agents 是通过 Task 工具自动调度的专项子代理，Claude Code 会根据上下文自动选择合适的 agent，用户无需手动调用。

| Agent | 用途 | 触发场景 |
|-------|------|----------|
| `code-reviewer` | 代码质量、安全性、可维护性审查 | 代码修改后自动触发 |
| `security-reviewer` | 安全漏洞检测（OWASP Top 10） | 涉及用户输入、认证、API 时触发 |
| `architect` | 系统设计、可扩展性、技术决策 | 规划新功能、重构时触发 |
| `refactor-cleaner` | 死代码清理、重复代码合并 | 重构任务时触发 |
| `doc-updater` | 文档和 codemap 更新 | 文档维护任务 |
| `e2e-runner` | Playwright E2E 测试 | 前端测试任务 |
| `tdd-guide` | 测试驱动开发引导 | 新功能开发、bug 修复 |
| `planner` | 复杂功能规划 | 功能实现、架构变更 |
| `build-error-resolver` | 构建和类型错误修复 | 构建失败时触发 |

> Agents 和 Skills 的区别：Agents 由 Claude Code 自动调度，你不需要手动调用；Skills 需要你主动输入 `/plugin:skill` 来触发。

### 2.3 可用 Skills（6 个，用户可调用）

Skills 通过 `/ecc:skill-name` 格式在对话中调用。

| 完整命令 | 简称 | 说明 |
|----------|------|------|
| `/ecc:tdd` | TDD | 测试驱动开发，先写测试再写实现 |
| `/ecc:setup-pm` | Setup PM | 配置项目管理偏好 |
| `/ecc:test-coverage` | Test Coverage | 测试覆盖率分析 |
| `/ecc:refactor-clean` | Refactor Clean | 死代码清理和重构 |
| `/ecc:update-codemaps` | Update Codemaps | 更新代码地图 |
| `/ecc:update-docs` | Update Docs | 更新项目文档 |

> 注意：命令前缀 `ecc:` 不能省略。输入 `/` 后会出现自动补全列表。

### 2.4 常见误解

**"为什么没有 `/commit`、`/plan`、`/e2e`、`/security-review` 这些命令？"**

这些功能确实存在，但不是以 skill 形式提供的：

| 你想做的事 | 实际方式 |
|-----------|---------|
| 规划功能 | 直接告诉 Claude "帮我规划..."，`planner` agent 会自动介入 |
| 代码审查 | 写完代码后 `code-reviewer` agent 自动触发 |
| 安全审查 | 涉及敏感代码时 `security-reviewer` agent 自动触发 |
| E2E 测试 | 使用 `/python-streamlit-e2e` skill（这是独立 skill，不属于此插件） |
| Git 提交 | 直接告诉 Claude "帮我提交"，它会用内置 git 能力完成 |

简单来说：**大部分能力是 agent 自动触发的，不需要你记命令。**

---

## 3. claude-mem 插件详解

### 3.1 架构原理

claude-mem 是一个跨会话持久化记忆系统，通过 MCP（Model Context Protocol）提供服务。

```
┌─────────────────────────────────────────┐
│           Claude Code 会话               │
│                                         │
│  save_memory() ──→ ┌──────────────┐     │
│                    │   SQLite DB   │     │
│  search()    ──→   │  (结构化存储)  │     │
│                    └──────┬───────┘     │
│  timeline()  ──→         │              │
│                    ┌──────▼───────┐     │
│  get_observations()│  ChromaDB    │     │
│              ──→   │ (向量嵌入)    │     │
│                    └──────────────┘     │
└─────────────────────────────────────────┘
```

- **SQLite**: 存储观察记录的结构化数据（标题、内容、时间戳、项目标签）
- **ChromaDB**: 存储文本的向量嵌入，支持语义相似度搜索

### 3.2 三层查询协议

这是 claude-mem 的核心设计，目的是最小化 token 消耗：

```
第 1 层: search(query)           → 返回索引和 ID（~50-100 tokens/条）
第 2 层: timeline(anchor=ID)     → 获取某条记录前后的上下文
第 3 层: get_observations([IDs]) → 获取指定 ID 的完整内容
```

**为什么分三层？**

直接获取所有记录的完整内容会消耗大量 token。三层协议让你先浏览索引，找到感兴趣的记录，再按需获取详情。官方说法是"10x token savings"。

**使用示例：**

```
# 第 1 层：搜索
search(query="budget API implementation", project="folio")
→ 返回: [{id: 42, title: "Budget API endpoints added"}, ...]

# 第 2 层：查看上下文
timeline(anchor=42)
→ 返回: ID 42 前后的相关记录摘要

# 第 3 层：获取详情
get_observations(ids=[42, 43])
→ 返回: 完整的观察记录内容
```

### 3.3 save_memory 用法

保存记忆供未来会话检索：

```
save_memory(
  text="完成了 Budget API 的 CRUD 端点实现，包括 create/read/update/close 四个操作。
        关键设计决策：budget close 时自动计算 remaining = allocated - spent。",
  title="Budget API CRUD 完成",
  project="folio"
)
```

**参数说明：**

| 参数 | 必填 | 说明 |
|------|------|------|
| `text` | 是 | 要记忆的内容，越详细越好 |
| `title` | 否 | 简短标题，不填则自动生成 |
| `project` | 否 | 项目标签，用于过滤。默认 `"claude-mem"` |

**最佳实践：**
- 每次会话结束前保存关键进展
- `text` 中包含：做了什么、为什么这样做、关键决策
- 始终指定 `project` 参数，方便后续按项目过滤
- 标题简洁明了，便于在搜索索引中快速识别

### 3.4 数据存储位置

claude-mem 的数据存储在本地：

```
~/.claude-mem/          # 默认数据目录
├── memories.db         # SQLite 数据库
└── chroma/             # ChromaDB 向量存储
```

数据完全本地化，不会上传到任何远程服务器。

### 3.5 与 `/memory` 自带命令的对比

| 特性 | `/memory`（内置） | `claude-mem`（插件） |
|------|-------------------|---------------------|
| 存储方式 | 写入 `CLAUDE.md` 文件 | SQLite + ChromaDB |
| 搜索能力 | 无（全文读取） | 语义搜索 + 时间线浏览 |
| 跨会话 | ✅ 通过文件持久化 | ✅ 通过数据库持久化 |
| 跨项目 | ❌ 绑定项目目录 | ✅ 通过 `project` 参数区分 |
| Token 效率 | 每次加载全部内容 | 三层协议按需加载 |
| 适用场景 | 项目级固定指令和约定 | 动态开发进展、决策记录、调试经验 |

**推荐用法：**
- `CLAUDE.md` / `/memory`：存放不常变化的项目约定（技术栈、目录结构、开发规范）
- `claude-mem`：存放动态的开发进展（完成了什么、遇到了什么问题、做了什么决策）

两者互补，不是替代关系。

---

## 4. 多终端协作开发实战

### 4.1 场景设定

以 Folio 项目开发 **Phase 3：投资组合盈亏分析** 为例，演示三个 Claude Code 终端如何协作。

**项目结构回顾：**

```
app/                    # 后端 (Backend 实例负责)
├── models/core.py      # 核心模型
├── api/core_routes.py  # API 端点
├── services/           # 业务逻辑
└── database.py

streamlit_app/          # 前端 (Frontend 实例负责)
├── api_client.py
└── pages/

tests/                  # 测试 (Testing 实例负责)
```

### 4.2 CLAUDE.md 的作用

`CLAUDE.md` 是所有终端的共享上下文，每个 Claude Code 实例启动时都会读取它。

关键内容：
- 技术栈和项目结构 → 所有实例共享同一认知
- 多实例分工规则 → 防止不同终端修改同一文件
- 插件使用约定 → 统一开发流程

### 4.3 三终端分工方案

```
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│  终端 1           │  │  终端 2           │  │  终端 3           │
│  Backend         │  │  Frontend        │  │  Testing         │
│                  │  │                  │  │                  │
│  修改范围:        │  │  修改范围:        │  │  修改范围:        │
│  app/            │  │  streamlit_app/  │  │  tests/          │
│                  │  │                  │  │                  │
│  流程:           │  │  流程:           │  │  流程:           │
│  "帮我规划..."    │  │  /mem-search     │  │  /mem-search     │
│  /ecc:tdd        │  │  开发页面         │  │  "审查代码"       ││  save_memory     │  │  /ecc:tdd        │  │  "安全审计"       │
└──────┬───────────┘  └──────┬───────────┘  └──────┬───────────┘
       │                     │                     │
       └──────────── claude-mem ───────────────────┘
                  (共享记忆数据库)
```

> `/ecc:tdd` 是插件 skill 的完整调用格式。输入 `/` 后会出现自动补全列表。

### 4.4 完整工作流演示

#### 阶段一：Backend 终端 — 实现 API

**开场白：**

```
你是 Folio 项目的 Backend 开发实例。
只修改 app/ 目录下的文件。
当前任务：实现 Phase 3 投资组合盈亏分析 API。
请先规划实现方案。
```

**工作流程：**

```
1. 告诉 Claude "帮我规划 Phase 3 盈亏分析 API"
   → planner agent 自动介入
   → 分析 models/core.py 中的 Holding 模型
   → 规划新增 API 端点：GET /api/v1/core/portfolio/pnl
   → 用户审批计划

2. /ecc:tdd
   → 先写测试：test_portfolio_pnl.py
   → 再实现：services/portfolio.py + api/core_routes.py
   → 确保测试通过

3. 保存进展到 claude-mem：
   save_memory(
     text="Phase 3 盈亏分析 API 完成。
           新增端点: GET /api/v1/core/portfolio/pnl
           请求参数: account_id (可选), period (7d/30d/all)
           返回: {holdings: [{symbol, qty, avg_cost, current_price, pnl, pnl_pct}], total_pnl}
           实现文件: app/services/portfolio.py, app/api/core_routes.py
           测试文件: tests/test_portfolio_pnl.py (8 tests passing)",
     title="Phase 3 盈亏分析 API 完成",
     project="folio"
   )
```

#### 阶段二：Frontend 终端 — 开发页面

**开场白：**

```
你是 Folio 项目的 Frontend 开发实例。
只修改 streamlit_app/ 目录下的文件。
当前任务：为 Phase 3 盈亏分析功能开发前端页面。
请先用 /claude-mem:mem-search 搜索后端 API 的最新进展。
```

**工作流程：**

```
1. 搜索后端进展：
   /claude-mem:mem-search
   → 搜索 "Phase 3 盈亏分析 API"
   → 了解 API 端点、参数、返回格式

2. 开发页面：
   → 在 api_client.py 中添加 get_portfolio_pnl() 方法
   → 创建 streamlit_app/pages/5_📊_投资组合.py
   → 调用 API 展示盈亏数据

3. /python-streamlit-e2e
   → 生成端到端测试
   → 验证页面功能正常

4. 保存进展：
   save_memory(
     text="Phase 3 前端页面完成。
           新增页面: pages/5_📊_投资组合.py
           功能: 持仓盈亏表格、总盈亏汇总、筛选条件
           api_client 新增: get_portfolio_pnl(account_id, period)
           E2E 测试: 3 个测试用例通过",
     title="Phase 3 前端页面完成",
     project="folio"
   )
```

#### 阶段三：Testing 终端 — 审查与安全

**开场白：**

```
你是 Folio 项目的 Testing 开发实例。
只修改 tests/ 目录下的文件。
当前任务：对 Phase 3 盈亏分析功能进行代码审查和安全审计。
请先用 /claude-mem:mem-search 搜索已完成的工作。
```

**工作流程：**

```
1. 搜索全部进展：
   /claude-mem:mem-search
   → 搜索 "Phase 3"
   → 获取 Backend 和 Frontend 的完成情况

2. 告诉 Claude "审查 portfolio.py 的代码质量"
   → code-reviewer agent 自动介入
   → 审查 app/services/portfolio.py
   → 审查 streamlit_app/pages/5_📊_投资组合.py

3. 告诉 Claude "对盈亏分析功能做安全审计"
   → security-reviewer agent 自动介入
   → 检查 API 端点的输入验证
   → 检查 SQL 注入风险
   → 检查数据泄露风险

4. 补充测试：
   → 添加边界条件测试
   → 添加异常场景测试

5. 保存审查结果：
   save_memory(
     text="Phase 3 代码审查和安全审计完成。
           发现问题: 无严重安全漏洞
           建议: portfolio.py 中的价格计算建议添加 Decimal 精度处理
           补充测试: 3 个边界条件测试已添加",
     title="Phase 3 审查完成",
     project="folio"
   )
```

### 4.5 避免冲突的规则

1. **文件所有权明确**：每个终端只修改自己负责的目录
2. **共享模型独占**：`app/models/core.py` 只由 Backend 实例修改
3. **通过 claude-mem 通信**：不要直接修改其他终端的文件，通过记忆传递信息
4. **先搜索再开发**：开始工作前先 `search()` 查看其他终端的最新进展
5. **及时保存进展**：每个阶段完成后立即 `save_memory()`
6. **CLAUDE.md 保持稳定**：运行时不要频繁修改 `CLAUDE.md`，它是共享的静态上下文

---

## 5. 推荐日常工作流

### 5.1 完整开发流程

```
开始会话
  │
  ├─→ 搜索记忆: /claude-mem:mem-search
  │   了解项目当前状态
  │
  ├─→ 规划: 告诉 Claude "帮我规划..."
  │   planner agent 自动介入，明确实现方案
  │
  ├─→ 编码: /ecc:tdd
  │   先写测试，再写实现
  │
  ├─→ 审查: code-reviewer agent 自动触发
  │   写完代码后自动检查质量
  │
  ├─→ 安全: security-reviewer agent 自动触发
  │   涉及敏感代码时自动检查
  │
  ├─→ 测试: /python-streamlit-e2e (如涉及前端)
  │   端到端验证
  │
  ├─→ 提交: 告诉 Claude "帮我提交"
  │   使用内置 git 能力完成
  │
  └─→ 保存进展: save_memory(text="...", project="folio")
      记录本次会话的关键成果
```

### 5.2 插件命令速查表

**用户主动调用的 Skills：**

| 命令 | 来源 | 用途 | 使用时机 |
|------|------|------|----------|
| `/ecc:tdd` | ecc | 测试驱动开发 | 编码阶段 |
| `/ecc:test-coverage` | ecc | 测试覆盖率分析 | 测试完成后 |
| `/ecc:refactor-clean` | ecc | 死代码清理 | 重构时 |
| `/ecc:update-codemaps` | ecc | 更新代码地图 | 结构变更后 |
| `/ecc:update-docs` | ecc | 更新文档 | 功能完成后 |
| `/ecc:setup-pm` | ecc | 配置项目管理 | 首次使用时 |
| `/claude-mem:mem-search` | claude-mem | 搜索跨会话记忆 | 会话开始时 |
| `/claude-mem:make-plan` | claude-mem | 带记忆的规划 | 复杂功能规划 |
| `/claude-mem:do` | claude-mem | 执行计划 | 计划审批后 |
| `/python-streamlit-e2e` | 独立 skill | Streamlit E2E 测试 | 前端完成后 |

**自动触发的 Agents（无需手动调用）：**

| Agent | 来源 | 触发条件 |
|-------|------|----------|
| `code-reviewer` | ecc | 代码修改后 |
| `security-reviewer` | ecc | 涉及敏感代码时 |
| `architect` | ecc | 架构决策时 |
| `planner` | ecc | 功能规划时 |
| `build-error-resolver` | ecc | 构建失败时 |

**MCP 工具（Claude 自动使用，也可在对话中提及）：**

| 工具 | 来源 | 用途 |
|------|------|------|
| `save_memory()` | claude-mem | 保存记忆 |
| `search()` | claude-mem | 搜索记忆 |
| `timeline()` | claude-mem | 查看时间线上下文 |
| `get_observations()` | claude-mem | 获取记录详情 |

### 5.3 Folio 项目专用约定

来自项目 `CLAUDE.md` 的标准流程：

```
新功能开始前  → 告诉 Claude "帮我规划..."（planner agent 自动介入）
后端开发      → /ecc:tdd → code-reviewer 自动审查
前端完成后    → /python-streamlit-e2e
提交前        → security-reviewer 自动审查（或主动要求 "做安全审计"）
会话结束      → save_memory(project="folio")
```

---

## 6. 多终端协作开发完整指南

> 基于 Folio 项目 Phase 3 和 UX 优化的实战经验。
> 读者可以是人类开发者，也可以是被指派到某个终端的 AI agent。

### 6.1 什么是多终端协作

在一个项目中同时打开多个 Claude Code 终端，每个终端负责不同的职责（如后端、前端、测试），通过共享上下文和信号机制协调工作，实现并行开发。

**适用场景：**
- 功能开发涉及多个独立目录（backend / frontend / tests）
- 任务可以拆分为互不干扰的子任务
- 希望缩短总开发时间

**不适用场景：**
- 改动集中在同一个文件或少数几个文件
- 任务之间强依赖，无法并行
- 简单的 bug 修复或小功能，单终端足够

### 6.2 前置条件

**工具：**

| 工具 | 用途 | 必需 |
|------|------|------|
| Claude Code CLI | 每个终端运行一个实例 | 是 |
| claude-mem 插件 | 终端间通信（信号传递） | 是 |
| CLAUDE.md | 共享上下文（所有终端自动读取） | 是 |
| Git | 代码合并和版本控制 | 是 |

**启动方式：**

每个终端用无确认模式启动，避免人工逐个审批：

```bash
claude --dangerously-skip-permissions
```

> 此模式下 Claude 会自动执行所有操作，包括文件修改和命令执行。确保你信任 CLAUDE.md 中的指令。

**确认 claude-mem 可用：**

```
save_memory(text="test", project="my-project")
search(query="test", project="my-project")
```

两个命令都正常返回即可。

### 6.3 核心机制

#### 6.3.1 文件所有权

每个终端只修改自己负责的目录，这是避免 git 冲突的根本手段。

```
终端 A (Backend):   只改 app/
终端 B (Frontend):  只改 streamlit_app/
终端 C (Testing):   只改 tests/
```

规则：
- 共享模型文件（如 `app/models/core.py`）由一个终端独占修改
- 如果必须跨目录修改，在 CLAUDE.md 中明确标注由谁负责
- 只读不写是安全的——任何终端都可以读取任何文件

#### 6.3.2 信号协议（claude-mem）

终端之间不能直接对话，需要通过 claude-mem 传递完成信号。

**发送信号：**

```
save_memory(
  text="SIGNAL:BACKEND_DONE - 后端任务完成: API端点已实现，测试通过",
  project="my-project"
)
```

**接收信号（轮询）：**

```
search(query="SIGNAL:BACKEND_DONE", project="my-project")
# 如果未找到，sleep 30 秒后重试
# 最多重试 20 次（约 10 分钟超时）
```

**信号命名规范：**

```
SIGNAL:<终端名>_DONE    # 终端完成全部任务
SIGNAL:<终端名>_READY   # 终端准备就绪（可选）
SIGNAL:<终端名>_BLOCKED # 终端遇到阻塞（可选）
```

信号内容应包含：完成了什么、修改了哪些文件、关键决策。这样下游终端不需要重新分析代码就能了解上游做了什么。

#### 6.3.3 共享上下文（CLAUDE.md）

CLAUDE.md 是所有终端的"共同大脑"，每个 Claude Code 实例启动时自动读取。

**应该写入 CLAUDE.md 的内容：**
- 项目结构和技术栈
- 各终端的分工和文件所有权
- 接口契约（API 请求/响应格式）
- 信号协议定义
- 每个终端的开场白

**不应该写入的内容：**
- 运行时动态状态（用 claude-mem 代替）
- 过于详细的实现细节（让终端自行决策）

**关键原则：CLAUDE.md 在多终端运行期间不要修改。** 它是静态的共享上下文，运行时修改可能导致终端之间认知不一致。

#### 6.3.4 接口契约

当前端依赖后端 API 时，在 CLAUDE.md 中预先定义接口契约，让前端可以先行开发：

```markdown
| 方法 | 路径 | 响应 |
|------|------|------|
| GET | /api/v1/portfolio | `{total_value, holdings: [{symbol, name, quantity, ...}]}` |
```

前端终端根据契约编写 API 调用代码，后端终端根据契约实现端点。两边独立开发，最终对接。

### 6.4 协作模式

#### 模式 A：完全并行

所有终端独立工作，互不依赖。

```
Terminal A ──────────────────→ Done
Terminal B ──────────────────→ Done
Terminal C ──────────────────→ Done
```

适用于：各终端修改完全独立的功能模块。

#### 模式 B：流水线

上游完成后下游才能开始。

```
Terminal A ──→ SIGNAL:A_DONE ──→ Terminal B ──→ SIGNAL:B_DONE ──→ Terminal C
```

适用于：强依赖关系，如后端 API → 前端页面 → 集成测试。

#### 模式 C：混合（推荐）

部分任务并行，部分任务有依赖。

```
Terminal A: ████████████████ → SIGNAL:A_DONE
Terminal B: ████ (独立任务) → 等待A → ████████ (依赖任务) → SIGNAL:B_DONE
Terminal C: ████ (独立任务) → 等待A → ████ → 等待B → ████ → SIGNAL:C_DONE
```

这是最常用的模式。每个终端先做不依赖上游的任务，然后轮询等待信号，收到后继续做依赖任务。

#### 模式选择指南

| 场景 | 推荐模式 | 终端数 |
|------|----------|--------|
| 大功能开发（新增 API + 页面 + 测试） | 混合 | 3 |
| UX 优化（前后端各改几处） | 并行 + QA | 2-3 |
| 纯后端重构 | 单终端 | 1 |
| 多个独立 bug 修复 | 完全并行 | 按 bug 数 |

### 6.5 实操步骤

**Step 1：分析任务，决定是否需要多终端**

问自己：
- 改动涉及几个独立目录？→ 2+ 个目录考虑多终端
- 任务之间有多少并行空间？→ 并行空间大才值得
- 总工作量多大？→ 小任务单终端更高效

**Step 2：在 CLAUDE.md 中定义分工**

写清楚每个终端的角色名称、修改范围（目录级别）、任务列表（按执行顺序）、依赖关系：

```markdown
## 多终端分工

### Terminal A: Backend
- 范围: app/
- 任务: A1(sync升级) → A2(portfolio端点) → A3(pnl端点)

### Terminal B: Frontend
- 范围: streamlit_app/
- 任务: B1(交易录入页面) → 等待A → B2(api_client) → B3(投资组合页面)

### Terminal C: Testing
- 范围: tests/
- 任务: C1(单元测试) → 等待A → C2(集成测试) → 等待B → C3(E2E测试)
```

**Step 3：定义信号协议**

```markdown
## 信号协议

| 信号 | 发送方 | 含义 |
|------|--------|------|
| SIGNAL:BACKEND_DONE | Terminal A | API 端点全部完成 |
| SIGNAL:FRONTEND_DONE | Terminal B | 页面全部完成 |
| SIGNAL:TESTING_DONE | Terminal C | 测试全部通过 |
```

**Step 4：定义接口契约（如有跨终端依赖）**

```markdown
## 接口契约

| 方法 | 路径 | 响应格式 |
|------|------|----------|
| GET | /api/v1/portfolio | `{total_value, holdings: [...]}` |
```

**Step 5：编写开场白**（见 6.6 节详细规范）

**Step 6：启动终端**

打开 N 个终端窗口，每个执行 `claude --dangerously-skip-permissions`，然后粘贴对应的开场白。

**Step 7：等待完成**

所有终端自主运行。你可以：
- 观察各终端的输出
- 在 claude-mem 中搜索信号确认进度
- 最后一个终端（通常是 QA）完成后，检查最终结果

### 6.6 开场白编写规范

开场白是粘贴到终端的第一条消息，相当于给 AI agent 的"任务书"。写得好坏直接决定终端能否自主完成工作。

#### 结构模板

```
读取 CLAUDE.md，我是 <角色名> 终端。按照 <分工章节名> 执行任务 <任务编号>，全程自主完成，不要停下来问我。

工作流程：
1. <第一步：检查前序状态>
2. <第二步：执行任务>
3. <第三步：发送完成信号>
4. <第四步：git 提交>

注意：全程不要停下来问我确认，遇到问题自行决策。
```

#### 关键要素

| 要素 | 说明 | 示例 |
|------|------|------|
| 角色声明 | 告诉 AI 它是哪个终端 | "我是 Backend 终端" |
| 读取指令 | 指向 CLAUDE.md 获取完整上下文 | "读取 CLAUDE.md" |
| 任务范围 | 明确要做哪些任务 | "执行任务 A1→A2→A3" |
| 自主决策 | 避免 AI 停下来等确认 | "全程不要停下来问我确认" |
| 前序检查 | 搜索 claude-mem 了解当前状态 | `search(query="Phase 3", project="...")` |
| 等待信号 | 如有依赖，说明轮询方式 | "轮询 SIGNAL:BACKEND_DONE，sleep 30s，最多 20 次" |
| 完成信号 | 任务完成后发送信号 | `save_memory(text="SIGNAL:...", project="...")` |
| 收尾动作 | 代码审查、git 提交等 | "git add 并提交所有改动" |

#### 好的开场白 vs 差的开场白

差的开场白：

```
帮我实现投资组合功能的后端部分。
```

问题：没有角色声明、没有任务边界、没有信号协议、AI 会频繁停下来问你。

好的开场白：

```
读取 CLAUDE.md，我是 Backend 终端。执行 Phase 3 任务 A1→A2→A3。

工作流程：
1. search(query="Phase 3 backend", project="folio") 检查前序进展
2. A1: 修改 app/api/core_routes.py 中 sync_holdings_value，用 AkShare 替换随机模拟
3. A2: 在 app/api/investment_routes.py 新增 GET /investments/portfolio
4. A3: 在 app/api/investment_routes.py 新增 GET /investments/pnl-analysis
5. 每个任务完成后运行 uv run pytest -v 确认测试通过
6. 全部完成后: save_memory(text="SIGNAL:BACKEND_DONE - ...", project="folio")
7. git add 并提交

全程不要停下来问我确认，遇到问题自行决策。
```

#### 轻量任务的开场白

不是所有多终端任务都需要复杂的开场白。对于小型优化：

```
读取 CLAUDE.md，我是 Frontend 终端。修改 streamlit_app/pages/2_账户管理.py：
1. 删除按钮用 st.expander 折叠 + 二次确认
2. 持仓输入精度改为 4 位小数
完成后 save_memory(text="UX优化 Frontend完成", project="folio")，然后 git 提交。
不要停下来问我。
```

### 6.7 真实案例

#### Case 1：Phase 3 大功能开发（3 终端，混合模式）

背景：为 Folio 添加投资组合分析功能，涉及新 API 端点、新前端页面、新测试。

分工：

```
Backend (app/)        → A1 sync升级 → A2 portfolio端点 → A3 pnl端点
Frontend (streamlit/) → B1 交易录入(独立) → 等待A → B2 api_client → B3 投资组合页面 → B4 首页链接
Testing (tests/)      → C1 单元测试(独立) → 等待A → C2 集成测试 → 等待B → C3 E2E测试
```

时间线：

```
00:00  三个终端同时启动
       Backend 开始 A1, Frontend 开始 B1, Testing 开始 C1
00:18  Backend 完成，发送 SIGNAL:BACKEND_DONE
00:20  Frontend 收到信号，开始 B2
       Testing 收到信号，开始 C2
00:22  Frontend 完成，发送 SIGNAL:FRONTEND_DONE
00:25  Testing 收到信号，开始 C3
00:28  Testing 完成，发送 SIGNAL:TESTING_DONE
```

关键配置（CLAUDE.md 中）：
- 接口契约让 Frontend 和 Testing 可以在 Backend 完成前就开始独立任务
- 信号协议让下游终端自动感知上游完成
- 文件所有权避免了 git 冲突

#### Case 2：UX 优化（3 终端，并行 + QA）

背景：修复 3 个体验问题：删除按钮安全性、输入精度、同步性能。

分工：

```
Backend (app/)        → 优化 sync 并发（asyncio.gather 替换串行循环）
Frontend (streamlit/) → 删除按钮折叠 + 精度4位 + 同步状态提示
QA                    → 等待两者完成 → 验收测试
```

特点：
- Backend 和 Frontend 完全并行，互不依赖
- QA 终端轮询两个信号，都收到后才开始验收
- 任务更轻量，每个终端只改 1 个文件

QA 终端的轮询逻辑：

```
先轮询: search(query="UX优化 Backend完成", project="folio")
     和 search(query="UX优化 Frontend完成", project="folio")
如果未找到，sleep 30 秒后重试，最多 20 次。

两个信号都收到后:
1. git pull
2. uv run pytest -v
3. 代码检查（确认改动符合预期）
4. 安全审查
```

### 6.8 经验教训

#### 测试终端容易成为瓶颈

在 Phase 3 中我们发现：Backend 和 Frontend 各自很快完成，但 Testing 终端需要等待两者都完成才能做集成测试和 E2E 测试，导致它成为整个流水线的瓶颈。

应对策略：
- 让 Testing 终端先做不依赖上游的单元测试（mock 数据）
- 考虑让 Backend 和 Frontend 各自负责自己的单元测试，Testing 只做集成和 E2E
- 对于小型任务，QA 可以合并到其中一个终端，不必单独开

#### 信号轮询的超时设计

轮询参数推荐：
- 间隔：30 秒，最大重试：20 次（总超时约 10 分钟）

如果上游任务预计耗时较长：
- 间隔：60 秒，最大重试：30 次（总超时约 30 分钟）

超时后终端应该停止等待并报告状态，而不是无限循环。

#### Git 冲突处理

如果严格遵守文件所有权，理论上不会有冲突。但实际中可能出现：
- 两个终端都修改了 CLAUDE.md（不应该在运行时修改）
- 自动格式化工具修改了不属于自己的文件

预防措施：
- CLAUDE.md 在启动前写好，运行时不改
- 在开场白中明确"只修改 xxx 目录"
- 每个终端提交前先 `git pull --rebase`

#### 什么时候不要用多终端

- 改动少于 3 个文件 → 单终端
- 所有改动在同一个目录 → 单终端
- 任务之间强耦合，无法拆分 → 单终端
- 你需要频繁介入决策 → 单终端（多终端的核心是自主运行）

#### "不要停下来问我"很重要

如果不加这句，AI 会在每个决策点停下来等你确认，多终端的并行优势就没了。但这也意味着你需要：
- 在 CLAUDE.md 中把任务描述得足够清楚
- 接受 AI 可能做出不完美的决策
- 事后通过 QA 终端或人工审查来兜底

#### 信号内容要有信息量

差的信号：
```
save_memory(text="SIGNAL:BACKEND_DONE", project="folio")
```

好的信号：
```
save_memory(
  text="SIGNAL:BACKEND_DONE - Phase 3 Backend 完成: A1 sync升级用AkShare替换随机模拟,
        A2 GET /investments/portfolio 端点, A3 GET /investments/pnl-analysis 端点.
        全部45测试通过.",
  project="folio"
)
```

好的信号让下游终端不需要重新分析代码就能了解上游做了什么，减少重复工作。

### 6.9 快速检查清单

启动多终端前，确认以下事项：

- [ ] CLAUDE.md 中已定义各终端的角色、范围、任务列表
- [ ] 文件所有权无重叠（每个文件只有一个终端可以修改）
- [ ] 信号协议已定义（信号名、发送方、含义）
- [ ] 接口契约已定义（如有跨终端 API 依赖）
- [ ] 每个终端的开场白已写好
- [ ] claude-mem 插件可用
- [ ] Git 工作区干净（`git status` 无未提交改动）
- [ ] 所有终端使用 `--dangerously-skip-permissions` 启动

---

*本文档基于 Claude Code 及其插件生态编写，插件版本和功能可能随更新变化。*
