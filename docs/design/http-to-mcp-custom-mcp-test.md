# HTTP-to-MCP 自定义 MCP 接入与测试

这份文档说明怎么把 AI 网关创建的 HTTP-to-MCP 服务接入 quickstart-mcp。结论是：不新增计算巢入口，不新增参数；把 AI 网关生成的 MCP 访问地址当作自定义 MCP 写入 `McpConfigJson`，再按普通 MCP 做部署、展示、Agent 下发和验收。

## 范围

这里测试的是 AI 网关 HTTP API 转 MCP 后，接入计算巢 MCP 实例的链路。

| 项目 | 处理方式 |
|------|----------|
| 配置入口 | 复用自定义 MCP，不新增“AI 网关接入”页签。 |
| 存储字段 | 只写 `McpConfigJson`，不新增 `ManagedMcpConfigJson`。 |
| 前端查询 | 不调用 APIG `ListMcpServers` 或 `GetMcpServer` 拉列表。 |
| 运行时 | ACS 按 `McpConfigJson` 创建 Knative Service。 |
| Agent 部署 | 传 MCP endpoint，不传 `gatewayId` 或 `mcpServerId`。 |

## 配置契约

HTTP-to-MCP 作为自定义远程 MCP 保存。远程 MCP 不带 `command` 和 `args`。

```json
[
  {
    "serverCode": "order-api",
    "type": "streamable-http",
    "url": "https://example.com/mcp-servers/order-api",
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
| `serverCode` | 是 | 实例内唯一标识，也用于生成 `/mcp-servers/{serverCode}`。 |
| `type` | 是 | 取值为 `sse` 或 `streamable-http`。 |
| `url` | 是 | AI 网关控制台复制出的 MCP 访问地址。 |
| `env` | 否 | 额外运行参数。没有参数时传 `{}`。 |

不要把 `gatewayId`、`mcpServerId`、`name`、`displayName`、`mcpServerPath`、图标、tools 快照写进该条目。名称、tools、路径归 AI 网关控制台管理；计算巢只保存可连接的 MCP 地址。

## 前端展示

前端继续读取服务实例详情里的 `Parameters.McpConfigJson`。展示时按条目字段判断类型。

| 条目形态 | 展示方式 |
|----------|----------|
| 有 `command` | 按公共 MCP 或包类型自定义 MCP 展示。 |
| 无 `command`，有 `url` | 按远程自定义 MCP 展示。 |
| `type=sse` | 展示连接方式为 SSE。 |
| `type=streamable-http` | 展示连接方式为 Streamable HTTP。 |

修改 MCP 时，前端仍通过现有服务实例变配写回完整 `McpConfigJson`。不要做增量 patch，也不要额外调用 APIG 查询可导入列表。

## 运行时行为

ACS 每个 MCP 条目创建一个 Knative Service，并统一向外暴露 Streamable HTTP。

| `McpConfigJson` 条目 | ACS 启动方式 | 对外路径 |
|----------------------|--------------|----------|
| `command=npx` 或 `command=uvx` | `supergateway --stdio ... --outputTransport streamableHttp` | `/mcp-servers/{serverCode}` |
| 无 `command`，`type=sse` | `supergateway --sse <url> --outputTransport streamableHttp` | `/mcp-servers/{serverCode}` |
| 无 `command`，`type=streamable-http` | `supergateway --streamableHttp <url> --outputTransport streamableHttp` | `/mcp-servers/{serverCode}` |

Agent 部署时使用最终可连接的 endpoint。对于 ACS 实例内的 MCP，endpoint 是：

```text
{McpRuntimeEndpoint}/mcp-servers/{serverCode}
```

Agent 配置只需要传 transport 和 url：

```json
{
  "mcpServers": {
    "order-api": {
      "transport": "streamable-http",
      "url": "http://alb-example.cn-hangzhou.alb.aliyuncsslb.com/mcp-servers/order-api"
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
| 远程 MCP | 有 `url`，无 `command`。 |
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
| Knative Service | 每个 MCP 一个 `mcp-{serverCode}`。 |
| Backend Service | 每个 MCP 一个 `mcp-{serverCode}-backend`，有 endpoints。 |
| Pod | `2/2 Running`，无 `ImagePullBackOff` 或 `CrashLoopBackOff`。 |
| 旧组件 | 没有 `mcp-api` workload，没有 `mcpo`。 |
| 启动参数 | SSE 上游使用 `--sse`，Streamable HTTP 上游使用 `--streamableHttp`。 |

### 4. 验证 MCP 协议

对 ACS 输出 endpoint 发起 Streamable HTTP 初始化请求。

```bash
MCP_URL="http://alb-example.cn-hangzhou.alb.aliyuncsslb.com/mcp-servers/order-api"

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
| url | 使用最终 MCP endpoint。 |
| 内部 ID | 不传 `gatewayId`、`mcpServerId`。 |
| 调用结果 | Agent 能完成一次 tools 调用。 |

## 排查

| 现象 | 优先检查 |
|------|----------|
| APIG 部署失败，提示 `domainIds should not be empty` | HTTP-to-MCP 没绑定网关域名。先补域名，不改 ACS。 |
| 本地访问超时 | 查云防火墙 EIP 保护、控制面 SLB ACL、ALB 安全组。 |
| ALB 返回 `503` | 查 Knative Route、Kourier、backend service endpoints。 |
| `initialize` 成功但 `tools/list` 为空 | 查 AI 网关 HTTP-to-MCP 的 tools 映射。 |
| 返回 `401` 或 `403` | 查 AI 网关鉴权、请求头、API Key。 |
| Pod 启动后退出 | 查 `supergateway` 上游参数和 URL 是否匹配 `type`。 |

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
| ACS 变配 | 新增远程 HTTP-to-MCP 后仍 `Deployed`。 |
| SSE 上游 | `initialize` 和 `tools/list` 通过。 |
| Streamable HTTP 上游 | `initialize` 和 `tools/list` 通过。 |
| Agent 部署 | 只传 MCP endpoint，并能调用 tools。 |
