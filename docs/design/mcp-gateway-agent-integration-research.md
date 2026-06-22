# HTTP-to-MCP 接入方案说明

本文件原来讨论“从 AI 网关纳管 MCP”的独立入口。该方案已废弃，最终以 `mcp-overall-knative-design.md` 为准。

当前结论：

| Item | Decision |
|------|----------|
| 配置入口 | 不新增 AI 网关接入 tab。 |
| 存储字段 | 不新增独立纳管参数。 |
| 前端调用 | 不调用 APIG 列表接口拉取可导入 MCP。 |
| 接入方式 | 用户在 AI 网关控制台创建 HTTP-to-MCP，复制 MCP URL 后填入计算巢自定义 MCP。 |
| Agent 部署 | 先用 `mcpServerId` 调 APIG `GetMcpServer` 拿实时接入信息，再只传 MCP endpoint 给 Agent。 |

详细接入、验收和排查步骤见 `http-to-mcp-custom-mcp-test.md`。

用户文档需要说明的流程：

```text
AI 网关控制台创建 HTTP-to-MCP
  -> 复制 MCP Server ID 或 SSE / Streamable HTTP 访问地址
  -> 计算巢配置 MCP
  -> 选择自定义 MCP
  -> 填入 mcpServerId 或访问地址
```
