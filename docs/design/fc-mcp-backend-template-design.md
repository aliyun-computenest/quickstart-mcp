# MCP 后端模板核心改动

## 结论

后端模板只负责部署和注册 MCP 协议入口，不再提供 API/OpenAPI 直连入口，也不在模板里承载 API 转 MCP。

这样模板保持简单：

- FC：函数直接运行 MCP transport，不引入 Caddy、Supervisor、mcpo。
- ACS：每个 MCP 独立运行，不额外部署 `mcp-api`。
- AI 网关：只注册 MCP 直接代理服务。

如果用户要把已有 HTTP API 转成 MCP，应引导到 AI 网关控制台操作。

---

## 模板输入改动

不新增运行时字段。

模板继续使用 MCP 市场返回的基础字段，例如 `serverCode`、`command`、`args`、`env`、`url`、`pkgType` 等。`serverCode` 属于现有市场配置字段，可以继续用于命名和路径生成，但不再把它作为新增字段设计。

默认行为固定为 SSE MCP 直接代理，后端路径沿用当前 `/sse`、`/message`。

---

## FC 模板改动

FC 模板保持单进程 MCP runtime，不做 API 分流。

```text
FC HTTP Trigger -> supergateway :8080
                      └─ stdio MCP package
```

需要调整的点：

- 不引入 Caddy。
- 不引入 Supervisor。
- 不启动 mcpo。
- 不输出 API/OpenAPI 直连地址。
- 注册函数仍把 FC 函数注册为 AI 网关 MCP 直接代理。

FC3 同一个函数只能有一个 HTTP Trigger，模板继续只生成一个 Trigger。

---

## ACS 模板改动

ACS 模板也只保留 MCP 协议入口。

```text
ALB Ingress
  └─ /mcp-servers/{serverCode} -> Service: mcp-{serverCode} -> Deployment: mcp-{serverCode} -> supergateway
```

需要调整的点：

- 不部署 `mcp-api` Deployment。
- 不部署 `mcp-api` Service。
- Ingress 不生成 `/{serverCode}` API 路径。
- 每个 MCP 仍然独立 Deployment + Service，避免多个 MCP pod 被同一个 Service 混合负载。

---

## AI 网关注入

模板自动注册的 MCP Server 只走 MCP 直接代理。

固定注册语义：按现有 SSE MCP 直接代理注册到 AI 网关，后端路径沿用 `/sse`。

不在模板里暴露协议转换开关。是否开启协议转换，交给 AI 网关控制台或后续专门能力处理。

---

## API 转 MCP 调研结论

AI 网关支持 HTTP 转 MCP，但不建议放到当前模板界面里做。

官方能力包括：

- 创建 MCP 服务时可以选择“HTTP 转 MCP”。
- HTTP 转 MCP 后端服务需要选择 HTTP 服务。
- 工具可以通过 Swagger/OpenAPI 文件导入生成。
- 也可以用自定义 YAML 手动配置工具。
- 可选配置后端服务认证，例如 Basic、Bearer、API Key。

这套流程需要 Swagger 上传或粘贴、工具生成预览、工具描述确认、认证配置等交互。当前模板页面主要是 ROS 参数渲染，不适合承载这个完整流程。

因此当前策略：

- 模板不提供 API 转 MCP。
- 模板只注册计算巢实例自身部署的 MCP。
- 用户在 AI 网关控制台创建的 HTTP 转 MCP，按自定义 MCP URL 填入计算巢。
- 不新增“网关接入”页签，不新增独立纳管参数，也不在前端调用 APIG 列表接口。
- Agent 部署页只使用最终可连接的 MCP endpoint，不传 AI 网关内部 ID。

推荐引导文案：

> 如需使用已在 AI 网关中创建的 HTTP 转 MCP，请先在 AI 网关控制台复制 SSE 或 Streamable HTTP 访问地址，再到计算巢“配置 MCP”的“自定义 MCP”中填入该地址。

---

## 已验证信息

| 验证点 | 结果 |
|--------|------|
| FC 同函数多 HTTP Trigger | 不支持；模板必须保持单 Trigger。 |
| APIG MCP 直接代理 | 已验证可创建并部署。 |
| APIG 协议转换 | 已验证网关侧行为可用，但当前模板不开放开关。 |
| ACS YAML 解析 | `acs.yaml` 可解析。 |

---

## 当前边界

- 本模板不提供 API/OpenAPI 直连能力。
- 本模板不提供 API 转 MCP 创建向导。
- 本模板不接管已纳管 HTTP 转 MCP 的外部生命周期；AI 网关被手动修改后，通过计算巢前端/后端对账更新展示，不由 ROS 自动修复。
- AI 网关里删除后同名重建的 MCP 视为新资源，需要重新纳管。
- ACS 直部署需要真实 ACR 镜像；模板里的 `{{ computenest::acrimage::quickstart-mcp-acs }}` 由 ComputeNest 发布链路替换。
- 私有 MCP package 的 OSS 下载逻辑还需要补 init container 或启动前下载步骤。
- ACS AI 网关注 Job 默认关闭；开启前需要 RRSA/OIDC 和具备 APIG 权限的 RAM 角色。
