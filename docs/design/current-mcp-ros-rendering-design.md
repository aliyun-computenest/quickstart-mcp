## MCP 市场当前界面与 ROS 模板渲染设计文档

### 1. Feature Background

当前 MCP 市场页面承担两个职责：一是让用户在市场中发现、筛选、选择公共或自定义 MCP；二是把用户选择转换成计算巢服务实例部署或变更所需的 ROS 参数。页面本身不是完全独立的前端表单，核心部署区域由 ROS 模板参数和计算巢控制台的模板渲染能力共同决定。

当前 ECS 单机版模板的主契约是 `McpConfigJson`。MCP 市场侧负责产出用户选择的 MCP 列表、运行命令、参数、环境变量、图标和包信息；ROS 模板侧负责把这些信息转换成实例上的运行配置，并在服务实例创建或变更时完成 ECS、网络、OSS、认证和控制台地址输出。

本设计文档描述当前界面如何与 ROS 模板协同渲染，以及 UI 在创建服务实例、修改已部署 MCP、访问控制台地址时应遵守的参数边界。目标是先把现状讲清楚，为后续 UI 重构和网关化调整提供稳定依据。

---

### 2. Requirements Overview

| # | Requirement | Description |
|:---:|------------|-------------|
| 1 | MCP 选择契约 | MCP 市场选择结果统一序列化到 `McpConfigJson`，作为创建和修改 MCP 工具的唯一主参数。 |
| 2 | ROS 参数渲染 | 下单页根据 ROS 参数定义、可见性条件、参数分组和预置套餐渲染部署表单。 |
| 3 | 自定义 MCP 支持 | 自定义 MCP 与公共 MCP 使用同一配置数组，但自定义项需要携带命令、地址、环境变量、包路径等用户配置。 |
| 4 | 修改已部署 MCP | 服务实例变更操作只暴露 `McpConfigJson`，用于替换当前实例的 MCP 工具列表。 |
| 5 | 资源套餐选择 | 预置套餐影响付费类型、ECS 规格、公网带宽和购买时长，并作为成本估算的输入。 |
| 6 | 网络与访问控制 | VPC、安全组、公网访问和认证开关共同决定实例是否生成公网访问地址、内网访问地址和 API Key。 |
| 7 | 部署后输出 | 部署完成后输出 MCP 总览控制台、调试控制台、API Key 和 ECS 初始密码，其中敏感项按隐藏输出处理。 |
| 8 | 内网代理访问 | 当关闭公网访问时，内网控制台地址需要依赖计算巢 Web Proxy 能力让用户可达。 |

---

### 3. Database Design

无变更。

当前设计不引入新的业务数据库。MCP 选择状态在创建或变更服务实例时作为 ROS 参数传入；服务实例的运行结果、输出地址和敏感输出由计算巢与 ROS 资源栈管理。

---

### 4. API Design

无新增业务 API。

当前界面复用计算巢服务实例创建和服务实例变更能力，前端与模板之间的核心数据契约是 ROS 参数载荷。`McpConfigJson` 的逻辑结构如下：

```json
[
  {
    "serverCode": "github",
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-github"],
    "env": {
      "GITHUB_PERSONAL_ACCESS_TOKEN": "credential-or-user-value"
    },
    "type": "stdio",
    "url": "",
    "packageOssPath": "",
    "icon": "https://example.com/icon.png"
  }
]
```

Behavior:

| Operation | Input | Semantics |
|-----------|-------|-----------|
| 创建服务实例 | 完整 ROS 参数集 | 按模板创建 ECS、OSS、网络、安全组和 MCP 运行环境。 |
| 修改 MCP 工具 | `McpConfigJson` | 覆盖当前实例的 MCP 工具列表，不做增量合并。 |
| 预置套餐选择 | 套餐内参数 | 回填付费类型、ECS 规格、公网带宽和购买时长。 |

字段说明：

| Field | Type | Required | Description |
|-------|------|:--------:|-------------|
| `serverCode` | string | Yes | MCP 唯一标识，也是运行配置中的 key。 |
| `command` | string | Conditional | stdio 类 MCP 的启动命令，如 `npx` 或 `uvx`。 |
| `args` | string[] | Conditional | stdio 类 MCP 的启动参数。 |
| `env` | object | No | MCP 运行所需环境变量。 |
| `type` | string | Yes | MCP 类型或连接方式，用于区分 stdio、SSE、HTTP 等运行形态。 |
| `url` | string | Conditional | 远程 MCP 的连接地址。 |
| `packageOssPath` | string | Conditional | 自定义私有包在 OSS 中的路径。 |
| `icon` | string | No | 市场和控制台展示图标。 |

---

### 5. Environment Variables

无新增平台环境变量。

MCP 运行变量由用户在 MCP 配置中填写，并存放在 `McpConfigJson.env` 内。模板会把每个 MCP 的环境变量写入实例侧运行配置，平台本身不新增统一环境变量。

| Variable | Purpose | Example |
|----------|---------|---------|
| MCP-specific env | 单个 MCP Server 运行所需凭据或配置 | `GITHUB_PERSONAL_ACCESS_TOKEN` |

---

### Core Flow Design

#### Flow: 创建服务实例

```
用户进入 MCP 市场
        │
        ▼
选择公共 MCP 或创建自定义 MCP
        │
        ▼
市场侧生成 McpConfigJson
        │
        ▼
进入计算巢服务实例创建页
        │
        ├── 选择预置套餐 → 回填付费、规格、带宽和时长
        │
        └── 自定义配置 → 用户逐项填写 ROS 参数
                │
                ▼
ROS 创建资源栈
        │
        ▼
ECS 启动脚本写入 MCP 运行配置并启动服务
        │
        ▼
输出 MCP 总览控制台、调试控制台和 API Key
```

#### Flow: 修改已部署 MCP

```
用户从服务实例操作进入 Modify-MCP-Servers
        │
        ▼
界面只展示 MCP 工具配置参数
        │
        ▼
用户调整 MCP 列表和运行参数
        │
        ▼
提交新的 McpConfigJson
        │
        ▼
实例侧按新配置覆盖当前 MCP 列表
```

#### Flow: 公网与内网访问

```
用户选择公网访问开关
        │
        ├── 开启公网访问
        │       └── ECS 分配公网带宽，输出公网控制台和调试地址
        │
        └── 关闭公网访问
                └── ECS 不分配公网带宽，输出内网地址并通过 Web Proxy 访问
```

---

### 6. Interaction Design

#### 6.1 Page Structure Changes

当前页面结构应理解为“市场页 + 计算巢模板页”的组合，而不是单一前端页面：

```
MCP 市场
├── 搜索与分类
├── 公共 MCP 列表
├── 自定义 MCP 创建入口
├── MCP 运行参数配置
└── 部署入口
    ├── 创建新服务实例
    └── 修改已有服务实例 MCP 工具

计算巢服务实例创建页
├── Mcp 配置
│   ├── McpConfigJson
│   └── 是否开启认证
├── OSS 存储配置
├── 付费类型配置
├── 资源配置
└── 可用区配置
```

#### 6.2 MCP 配置区

**Elements:**

- **MCP 选择器**: 由 `ALIYUN::MCP::Server::Server` 参数渲染，展示 MCP 列表、标签和已选数量。
- **公共 MCP 卡片**: 用户只能配置运行参数和凭据，不修改平台维护的服务定义。
- **自定义 MCP 表单**: 用户填写名称、ID、安装方式、命令或 URL、环境变量、包路径和图标。
- **认证开关**: 控制是否生成 API Key，以及实例初始化时是否开启鉴权。

**Validation rules:**

| Field | Rule |
|-------|------|
| `serverCode` | 同一服务实例内必须唯一。 |
| `command` / `args` | stdio 类 MCP 必填，参数保持数组结构。 |
| `url` | SSE 或 HTTP 类 MCP 必填，需为可访问地址。 |
| `env` | key 不能为空；涉及凭据时应避免明文暴露在非敏感展示区域。 |
| `packageOssPath` | 私有包类 MCP 必填，且依赖 OSS 访问权限。 |

**Mockup:** see `mcp-market-redesign.html`

#### 6.3 资源与套餐配置区

**Elements:**

- **预置套餐**: 回填付费类型、ECS 规格、公网带宽和购买时长。
- **付费类型**: 按量付费时隐藏购买周期和购买时长；包年包月时展示对应字段。
- **ECS 规格**: 与付费类型、可用区联动，作为成本和实例能力的核心参数。
- **公网带宽**: 在开启公网访问时生效。

**Validation rules:**

| Field | Rule |
|-------|------|
| `PayType` | 只能为按量付费或包年包月。 |
| `PayPeriodUnit` / `PayPeriod` | 仅包年包月时需要填写。 |
| `EcsInstanceType` | 必须是当前可用区和付费类型下可售规格。 |
| `InternetMaxBandwidthOut` | 开启公网访问时必须在模板允许范围内。 |

#### 6.4 网络与存储配置区

**Elements:**

- **VPC 选择**: 支持新建 VPC 或使用已有 VPC。
- **交换机选择**: 使用已有 VPC 时按 VPC 和可用区筛选交换机。
- **安全组选择**: 使用已有 VPC 时支持新建或选择已有安全组。
- **OSS 选择**: 支持新建 OSS Bucket 或选择已有 Bucket，用于存储企业内部 MCP Package。
- **公网访问开关**: 在已有 VPC 且已有安全组场景下展示。

**Validation rules:**

| Field | Rule |
|-------|------|
| `VpcCidrBlock` | 新建 VPC 时必填，必须为合法私网 CIDR。 |
| `VSwitchCidrBlock` | 新建 VPC 时必填，必须属于 VPC CIDR。 |
| `VpcId` | 使用已有 VPC 时必填。 |
| `VSwitchId` | 使用已有 VPC 时必填，并受 `VpcId` 和 `ZoneId` 约束。 |
| `SecurityGroupId` | 使用已有安全组时必填。 |
| `BucketName` | 使用已有 OSS Bucket 时必填。 |

#### 6.5 部署后结果区

**Elements:**

- **MCP Server 总览控制台**: 公网访问开启时展示公网地址，关闭时展示内网地址并通过 Web Proxy 访问。
- **MCP Server 调试控制台**: 公网访问开启时展示公网调试地址，关闭时展示内网调试地址并通过 Web Proxy 访问。
- **API Key**: 仅开启认证时展示，按敏感输出处理。
- **ECS 初始密码**: 按敏感输出处理，仅用于必要的实例运维。

**Validation rules:**

| Field | Rule |
|-------|------|
| 控制台地址 | 根据公网访问开关只展示对应地址，避免同时暴露公网和内网入口。 |
| API Key | 仅认证开启时生成和展示。 |
| 内网地址 | 需要配置 Web Proxy，否则用户无法从 Console 直接访问。 |

---

### Verification Points

| Scenario | Expected Behavior |
|----------|-------------------|
| 用户未选择任何 MCP | 页面应阻止创建或给出明确提示，避免生成空运行配置。 |
| 公共 MCP 需要凭据但未填写 | 页面应阻止提交，并定位到缺失的环境变量。 |
| 自定义 MCP ID 与已有项重复 | 页面应阻止保存，提示同一实例内 ID 必须唯一。 |
| 关闭公网访问 | 不分配公网带宽，只展示内网控制台和内网调试地址。 |
| 开启认证 | 部署后输出 API Key，实例侧调用调试接口需要携带鉴权信息。 |
| 使用已有 OSS Bucket | 页面应提示需要确保实例角色具备访问 Bucket 的权限。 |
| 修改 MCP 工具 | 提交的新 `McpConfigJson` 覆盖当前列表，确认页应让用户看到移除和新增项。 |
| 元数据引用不存在参数 | 参数分组中存在但模板未定义的字段不应渲染成异常表单项；正式发布前应清理。 |
| 预置套餐名称不完整 | 套餐名称应完整展示，避免影响用户理解套餐适用范围。 |
