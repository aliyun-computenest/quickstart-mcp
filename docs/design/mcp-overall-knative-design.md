## MCP 整体方案 - Knative 版设计文档

### 1. Feature Background

ACS 版 MCP Runtime 改成 Knative Serving。这里的 Knative Service 指 `serving.knative.dev/v1 Service`，不是普通 Kubernetes `Service`；它负责 Revision、流量和自动伸缩，底层再生成实际工作负载。

MCP 配置模型不变。AI 网关里创建出来的 HTTP-to-MCP，本质上是一条可访问的 MCP URL，不在计算巢里新增“AI 网关接入”入口。用户在 AI 网关控制台创建 HTTP-to-MCP 后，复制 SSE 或 Streamable HTTP 地址，作为自定义 MCP 填入。

---

### 2. Requirements Overview

| # | Requirement | Decision |
|---|-------------|----------|
| 1 | ACS Runtime | 本地命令型 MCP 用 Knative Serving Service 承载；远端 URL 不创建 workload。 |
| 2 | 配置字段 | 只使用 `McpConfigJson`，不新增顶层参数。 |
| 3 | AI 网关 HTTP-to-MCP | 按自定义 MCP URL 使用，不做单独导入界面。 |
| 4 | 前端展示 | 继续展示公共 MCP 和自定义 MCP；不新增第三个 tab。 |
| 5 | Agent 部署 | 下发最终 MCP endpoint；AI 网关来源先用 `mcpServerId` 查 APIG 实时详情。 |

---

### 3. Database Design

无数据库变更，无新增参数。

`McpConfigJson` 继续保存公共 MCP 和自定义 MCP。AI 网关 HTTP-to-MCP 也按自定义 MCP 保存，不增加新类型。

| Field | Meaning |
|-------|---------|
| `serverCode` | 当前实例内 MCP 标识。 |
| `type` | MCP 连接方式，如 `sse` 或 `streamable-http`。 |
| `mcpServerId` | 可选。AI 网关 MCP Server ID，用于展示和 Agent 部署前调用 APIG `GetMcpServer`。 |
| `url` | 可选。普通自定义 MCP 访问地址，也可作为 APIG 查询失败时的兜底地址。 |
| `env` | 可选运行参数。 |

不再设计独立纳管字段、`api-mcp` 类型、`gatewayId`、路径快照、tools 快照等字段。名称、路径、tools 归 AI 网关控制台管理；计算巢只保存 `mcpServerId` 这个查询句柄，或保存普通自定义 URL。

---

### 4. API Design

无新增计算巢 API。

| Flow | Rule |
|------|------|
| 配置 MCP | 前端通过现有服务实例变配写回完整 `McpConfigJson`。 |
| 查询展示 | 前端读取服务实例详情里的 `McpConfigJson`，按现有公共 MCP / 自定义 MCP 逻辑展示。 |
| AI 网关 HTTP-to-MCP | 配置页不新增导入 tab；展示详情可用 `mcpServerId` 调 APIG `GetMcpServer`。 |
| Agent 部署 | 后端把用户选择的 MCP 转成 `transport + url` 下发给 Agent；AI 网关来源先调 `GetMcpServer` 解析实时 endpoint。 |

Agent 配置示例：

```json
{
  "mcpServers": [
    {
      "transport": "streamable-http",
      "url": "https://example.com/mcp-servers/order-api"
    },
    {
      "transport": "sse",
      "url": "https://example.com/mcp-servers/fetch/sse"
    }
  ]
}
```

---

### 5. Environment Variables

无变更。

公共 MCP 和自定义 MCP 如需参数，仍写在 `McpConfigJson.env`。

---

### 6. Interaction Design

配置 MCP 弹窗只保留两类来源：

```text
公共 MCP | 自定义 MCP
```

| Area | Rule |
|------|------|
| 公共 MCP | 复用现有展示和参数配置。 |
| 自定义 MCP | 支持填写名称、连接方式、URL、环境变量。 |
| AI 网关 HTTP-to-MCP | 不展示独立 tab；用户把 AI 网关复制出的 MCP URL 填到自定义 MCP。 |
| 服务实例详情 | 展示当前 `McpConfigJson` 对应的 MCP 清单。 |
| Agent 部署页 | 展示可选 MCP，保存时传 MCP endpoint。 |

用户文档补充四步：

| Step | Description |
|------|-------------|
| 1 | 在 AI 网关控制台创建 HTTP-to-MCP。 |
| 2 | 确认 MCP Server 已部署成功。 |
| 3 | 复制 SSE 或 Streamable HTTP 访问地址。 |
| 4 | 回到计算巢自定义 MCP，填入该地址。 |

详细接入和测试步骤见 `http-to-mcp-custom-mcp-test.md`。

---

### Core Flow Design

```text
AI 网关控制台创建 HTTP-to-MCP
  -> 复制 MCP Server ID 或 URL
  -> 计算巢自定义 MCP 填 mcpServerId 或 URL
  -> 写入 McpConfigJson
  -> ACS 不为远端 URL 创建 workload
  -> Agent 部署时调用 GetMcpServer 生成 transport + url
```

---

### Verification Points

| Scenario | Expected |
|----------|----------|
| 旧实例 `McpConfigJson` | 正常展示、正常变配。 |
| 配置 MCP 弹窗 | 不出现 AI 网关接入 tab。 |
| 模板参数 | 不出现独立纳管参数。 |
| AI 网关 HTTP-to-MCP | 作为自定义 MCP URL 使用。 |
| ACS Runtime | 命令型 MCP 独立创建 Knative Serving Service；远端 URL 不创建 pod。 |
| Agent 部署 | 只接收可连接 MCP endpoint，不接收 `mcpServerId`。 |
