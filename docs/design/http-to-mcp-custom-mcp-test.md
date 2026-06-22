# HTTP-to-MCP 自定义 MCP 接入与测试

这份文档说明怎么把 AI 网关创建的 HTTP-to-MCP 服务接入 quickstart-mcp。结论是：不新增计算巢入口，不新增参数；把 AI 网关生成的 MCP 访问地址当作自定义 MCP 写入 `McpConfigJson`，前端展示和 Agent 下发直接使用该地址。

## 范围

这里测试的是 AI 网关 HTTP API 转 MCP 后，接入计算巢 MCP 实例的链路。

| 项目 | 处理方式 |
|------|----------|
| 配置入口 | 复用自定义 MCP，不新增“AI 网关接入”页签。 |
| 存储字段 | 只写 `McpConfigJson`，不新增 `ManagedMcpConfigJson`。 |
| 前端查询 | 普通自定义 URL 不查 APIG；带 `mcpServerId` 的 AI 网关来源可调用 APIG `GetMcpServer` 拿实时详情。 |
| 运行时 | ACS 只为本地命令型 MCP 创建 Knative Service；远端 URL 不创建 ACS workload。 |
| Agent 部署 | 传最终 MCP endpoint；`mcpServerId` 只用于部署前查询 APIG，不下发给 Agent。 |

## 配置契约

HTTP-to-MCP 作为自定义远程 MCP 保存。远程 MCP 不带 `command` 和 `args`。

```json
[
  {
    "serverCode": "order-api",
    "type": "streamable-http",
    "mcpServerId": "mcp-xxxx",
    "env": {}
  },
  {
    "serverCode": "crm-api",
    "type": "sse",
    "url": "https://example.com/mcp-servers/crm-api/sse",
    "env": {}
  }
]
```

| 字段 | 必填 | 说明 |
|------|------|------|
| `serverCode` | 是 | 实例内唯一标识。命令型 MCP 会用它生成 `/mcp-servers/{serverCode}`；远端 URL 只用于展示和 Agent 选择。 |
| `type` | 是 | 取值为 `sse` 或 `streamable-http`。 |
| `mcpServerId` | 否 | AI 网关 MCP Server ID。通过 AI 网关来源添加时保存；纯手填 URL 不需要。 |
| `url` | 否 | 纯手填远端 MCP 的访问地址，也可作为 APIG 查询失败时的兜底地址。 |
| `env` | 否 | 额外运行参数。没有参数时传 `{}`。 |

不要把 `gatewayId`、`name`、`displayName`、`mcpServerPath`、图标、tools 快照写进该条目。名称、tools、路径归 AI 网关控制台管理；需要展示或部署时用 `mcpServerId` 调 APIG 获取实时结果。

## 前端展示

前端继续读取服务实例详情里的 `Parameters.McpConfigJson`。展示时按条目字段判断类型。

| 条目形态 | 展示方式 |
|----------|----------|
| 有 `command` | 按公共 MCP 或包类型自定义 MCP 展示。 |
| 无 `command`，有 `mcpServerId` | 按 AI 网关来源的远程自定义 MCP 展示；详情来自 APIG `GetMcpServer`。 |
| 无 `command`，有 `url` | 按普通远程自定义 MCP 展示。 |
| `type=sse` | 展示连接方式为 SSE。 |
| `type=streamable-http` | 展示连接方式为 Streamable HTTP。 |

修改 MCP 时，前端仍通过现有服务实例变配写回完整 `McpConfigJson`。不要做增量 patch，也不要额外调用 APIG 查询可导入列表。

## 运行时行为

ACS 只给本地命令型 MCP 创建 Knative Service，并统一向外暴露 Streamable HTTP。远端自定义 MCP 已经有可连接的 SSE 或 Streamable HTTP 地址，不再由 ACS runtime 包一层。

| `McpConfigJson` 条目 | ACS 启动方式 | 对外路径 |
|----------------------|--------------|----------|
| `command=npx` 或 `command=uvx` | `supergateway --stdio ... --outputTransport streamableHttp` | `/mcp-servers/{serverCode}` |
| 无 `command`，有 `mcpServerId` 或 `url` | 不创建 ACS workload | Agent 部署时解析最终 URL |

Agent 部署时使用最终可连接的 endpoint：

| MCP 形态 | Agent endpoint |
|----------|----------------|
| 命令型 MCP | `{McpRuntimeEndpoint}/mcp-servers/{serverCode}` |
| AI 网关来源 MCP | 调 APIG `GetMcpServer(mcpServerId)` 后生成 URL。 |
| 普通远端 URL MCP | `McpConfigJson.url`。 |

AI 网关来源 MCP 的部署解析规则：

| Step | Rule |
|------|------|
| 1 | 用 `mcpServerId` 调 APIG `GetMcpServer`。 |
| 2 | 只接受 `deployStatus=Deployed` 的 MCP Server。 |
| 3 | 从 `domainInfos` 选一个可访问域名，协议用返回的 `HTTP` 或 `HTTPS`。 |
| 4 | `type=streamable-http` 时 URL 为 `{scheme}://{domain}{mcpServerPath}`。 |
| 5 | `type=sse` 时 URL 为 `{scheme}://{domain}{mcpServerPath}/sse`。 |
| 6 | 如果 APIG 查询失败且条目里有 `url`，可降级使用该 `url`；否则阻止部署并提示用户刷新 MCP。 |

Agent 配置只需要传 transport 和 url：

```json
{
  "mcpServers": {
    "order-api": {
      "transport": "streamable-http",
      "url": "https://example.com/mcp-servers/order-api"
    }
  }
}
```

## 测试步骤

按下面顺序验收。前一层不通过时，不要跳到后一层排查。

### 1. 验证 AI 网关 HTTP-to-MCP

在 AI 网关控制台创建 HTTP-to-MCP，并确认 MCP Server 已部署。

可选 CLI 检查：

```bash
aliyun apig list-mcp-servers \
  --region cn-hangzhou \
  --gateway-id "$GATEWAY_ID" \
  --create-from-types ApiGatewayHttpToMCP \
  --deploy-statuses Deployed
```

验收标准：

| 检查项 | 期望 |
|--------|------|
| MCP Server 状态 | `Deployed`。 |
| 地址 | 能复制 SSE 或 Streamable HTTP URL。 |
| tools | AI 网关控制台能看到预期 tools。 |

### 2. 写入计算巢自定义 MCP

在计算巢配置 MCP 页面选择自定义 MCP。填写 `serverCode`、连接方式和 URL。

写回后的 `McpConfigJson` 必须满足：

| 检查项 | 期望 |
|--------|------|
| 远程 MCP | 有 `mcpServerId` 或 `url`，无 `command`。 |
| 连接方式 | `type` 是 `sse` 或 `streamable-http`。 |
| 旧条目 | 公共 MCP 和包类型自定义 MCP 不变。 |
| 独立字段 | 没有 `ManagedMcpConfigJson`。 |

### 3. 验证 ACS 实例

创建新实例或执行 `Modify-MCP-Servers` 变配。实例进入 `Deployed` 后检查集群。

```bash
kubectl -n mcp-runtime get ksvc,route,pod,svc,ingress
```

验收标准：

| 检查项 | 期望 |
|--------|------|
| Knative Service | 只为有 `command` 的 MCP 创建 `mcp-{serverCode}`。 |
| Backend Service | 只为有 `command` 的 MCP 创建 `mcp-{serverCode}-backend`，有 endpoints。 |
| Pod | 命令型 MCP `2/2 Running`，无 `ImagePullBackOff` 或 `CrashLoopBackOff`。 |
| 远端 URL | 不出现对应 `mcp-{serverCode}` pod。 |
| 旧组件 | 没有 `mcp-api` workload，没有 `mcpo`。 |
| 启动参数 | 不出现远端 URL 的 `--sse` 或 `--streamableHttp` 二次包装。 |

### 4. 验证 MCP 协议

命令型 MCP 对 ACS 输出 endpoint 发起 Streamable HTTP 初始化请求。远端 URL MCP 直接请求最终 URL；AI 网关来源 MCP 先用 `GetMcpServer` 解析最终 URL。AI 网关 HTTP-to-MCP 的 Streamable HTTP 地址是 `/mcp-servers/{name}`，SSE 地址是 `/mcp-servers/{name}/sse`。

```bash
MCP_URL="https://example.com/mcp-servers/order-api"

curl -i -sS -X POST "$MCP_URL" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2025-03-26",
      "capabilities": {},
      "clientInfo": {
        "name": "quickstart-mcp-test",
        "version": "0.1.0"
      }
    }
  }'
```

继续调用 `tools/list`。如果初始化响应返回 `Mcp-Session-Id`，后续请求带上这个 header。

```bash
curl -i -sS -X POST "$MCP_URL" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "Mcp-Session-Id: $MCP_SESSION_ID" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/list",
    "params": {}
  }'
```

验收标准：

| 检查项 | 期望 |
|--------|------|
| `GET /mcp-servers/{serverCode}` | 可返回 `405`，说明已到 MCP 服务。 |
| `initialize` | HTTP `200`，返回 MCP server info。 |
| `tools/list` | HTTP `200`，返回 AI 网关 HTTP-to-MCP 暴露的 tools。 |

### 5. 验证 Agent 部署

在 Agent 部署页选择该 MCP。提交前检查 payload。

验收标准：

| 检查项 | 期望 |
|--------|------|
| transport | `streamable-http`。 |
| url | 命令型 MCP 用 ACS ALB endpoint；AI 网关来源 MCP 用 `GetMcpServer` 实时生成 endpoint；普通远端 URL MCP 用 `McpConfigJson.url`。 |
| 内部 ID | 不传 `gatewayId`、`mcpServerId` 给 Agent。 |
| 调用结果 | Agent 能完成一次 tools 调用。 |

## 排查

| 现象 | 优先检查 |
|------|----------|
| APIG 部署失败，提示 `domainIds should not be empty` | HTTP-to-MCP 没绑定网关域名。先补域名，不改 ACS。 |
| 本地访问超时 | 查云防火墙 EIP 保护、控制面 SLB ACL、ALB 安全组。 |
| ALB 返回 `503` | 查 Knative Route、Kourier、backend service endpoints。 |
| `initialize` 成功但 `tools/list` 为空 | 查 AI 网关 HTTP-to-MCP 的 tools 映射。 |
| 返回 `401` 或 `403` | 查 AI 网关鉴权、请求头、API Key。 |
| 远端 URL 写入后出现新 pod | ACS 模板过滤失效；远端 URL 不应创建 workload。 |

## 回归清单

每次改这条链路至少跑下面检查：

```bash
python3 -m pytest tests/test_acs_template.py -q
python3 -m py_compile mcp/fc-mcp.py mcp/higress_enterprise.py
node --check mcp/dual-entrypoint.js
git diff --check
```

完整验收必须包括：

| 场景 | 必须通过 |
|------|----------|
| ACS 新建实例 | `Deployed`。 |
| ACS 变配 | 新增远程 HTTP-to-MCP 后仍 `Deployed`，且不新增远端 URL pod。 |
| SSE 地址 | 直接请求 AI 网关 SSE endpoint 能建立会话。 |
| Streamable HTTP 地址 | 直接请求 AI 网关 Streamable HTTP endpoint 的 `initialize` 和 `tools/list` 通过。 |
| Agent 部署 | 只传 MCP endpoint，并能调用 tools。 |
