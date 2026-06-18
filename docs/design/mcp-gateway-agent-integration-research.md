# HTTP 转 MCP 纳管与 Agent 展示设计

## 结论

Agent 部署页继续以 **计算巢 MCP 网关服务实例** 为主对象。

用户在 AI 网关控制台创建的 HTTP 转 MCP，可以纳管到某个计算巢服务实例。纳管后，它成为该实例 MCP 清单的一部分，能在服务实例详情和 Agent 部署页中和实例部署的 MCP 一起展示和选择。

纳管后仍允许用户在 AI 网关控制台手动修改、停用或删除 MCP。这里不能做强一致复制，AI 网关是 MCP Server 的真实状态源，计算巢只保存纳管关系和上次展示快照，并在展示和保存前做状态对账。

纳管不等于重新注册：

```text
实例部署 MCP：由计算巢模板创建和注册，生命周期由服务实例管理
HTTP 转 MCP 接入：AI 网关里已经存在，只把归属关系纳入服务实例 MCP 清单
Agent 可选 MCP：实例部署 MCP + 已接入 HTTP 转 MCP
```

---

## 命名

配置 MCP 弹窗中的第三个来源，视觉标签命名为：

```text
网关接入
```

不用“已创建 MCP”，因为这里不是泛化展示所有已创建 MCP，而是从当前服务实例关联的网关里接入已有 MCP。也不直接用“纳管 AI 网关 MCP”做页签名，因为它偏动作和底层产品名。

完整概念仍是“接入网关 MCP”，但左侧来源切换只展示“网关接入”，避免换行和认知负担。技术文档里可以继续说“纳管关系”，用户界面优先使用“接入 / 已接入 / 移出”。

推荐文案：

- 来源切换：`网关接入`
- 按钮：`接入当前实例`
- 状态：`已接入`
- 实例详情标签：`网关接入`

---

## 完整链路

### 1. 发现可纳管 MCP

从服务实例中读取并标准化 `gatewayId`，只查询当前实例关联网关下已部署的 HTTP 转 MCP。当前 FC/ACS 模板实际输出字段是 `HigressAI`，前端/后端需要兼容旧字段：

```text
gatewayId = Outputs.HigressAI || Outputs.GatewayId || Parameters.HigressAI
```

查询 APIG：

```text
ListMcpServers(
  gatewayId = 标准化后的 gatewayId,
  createFromTypes = ApiGatewayHttpToMCP,
  deployStatuses = Deployed
)
```

查询结果中已被当前实例接入的项展示为“已接入”，未接入的项展示为“可接入”。已经被其他实例接入的项可以展示来源，但默认不可选，避免同一个外部 MCP 被多个实例重复认领。

如果当前网关里还没有 HTTP 转 MCP，测试或后端创建链路按 AI 网关 API 执行：

```text
CreateService(...) -> serviceId
CreateMcpServer(
  gatewayId,
  name,
  type = RealMCP,
  createFromType = ApiGatewayHttpToMCP,
  protocol = HTTP,
  domainIds = [Parameters.HigressDomainId],
  match.path = { type: Prefix, value: /mcp-servers/<name> },
  backendConfig.services[0].serviceId = serviceId,
  mcpServerConfig.swaggerConfig = OpenAPI 3.0 JSON string
)
DeployMcpServer(mcpServerId)
```

实测约束：

- `match` 不能为空，否则 `CreateMcpServer` 返回 `Parameter match should not be empty`。
- `domainIds` 不能为空，否则 `DeployMcpServer` 返回 `Parameter domainIds should not be empty`。
- HTTP 转 MCP 的控制台接入点仍按 `/mcp-servers/<name>` 和 `/mcp-servers/<name>/sse` 形成；API 中的 `protocol=HTTP` 表示 HTTP 转 MCP 创建形态，不等于普通 API 暴露。
- `ListMcpServers` / `GetMcpServer` 当前不稳定返回 tools 明细，纳管参数不保存工具快照。
- DNS 后端创建成功不代表后端可达，真实产品需要在接入前提示或校验后端能被 AI 网关访问。

### 2. 纳管校验

用户点击“纳管”时，后端再次校验：

- `mcpServerId` 存在。
- `gatewayId` 等于当前服务实例标准化后的 `gatewayId`。
- `createFromType=ApiGatewayHttpToMCP`。
- `deployStatus=Deployed`。
- 当前实例下不存在同一个 `mcpServerId` 的纳管记录。

校验通过后，保存纳管关系。

### 3. Parameters 存储

纳管记录存到计算巢服务实例 Parameters 中的独立字段，不写入 `McpConfigJson`。

推荐新增隐藏参数：

```text
ManagedMcpConfigJson
```

原因：

- `McpConfigJson` 已被 FC/ACS 模板用于创建函数、工作负载和注册 MCP Server。
- 如果把纳管项塞进 `McpConfigJson`，模板会把它当成需要部署的 MCP，造成重复注册或运行时配置错误。
- `ManagedMcpConfigJson` 只作为实例 MCP 清单扩展，由计算巢前端/后端读取和展示，不被 ROS 资源引用。

模板和服务配置需要同时补齐：

```yaml
Parameters:
  ManagedMcpConfigJson:
    Type: Json
    Default: []
    Label:
      zh-cn: 网关接入 MCP
      en: Managed gateway MCP
    AssociationPropertyMetadata:
      Visible:
        Condition:
          Fn::Equals:
            - true
            - false
```

```yaml
OperationMetadata:
  ModifyParametersConfig:
    - TemplateName: FC企业版
      Operation:
        - Name: Manage-Gateway-MCP
          Description: 接入或移出网关MCP
          Type: Custom
          SupportPredefinedParameters: false
          EnableLogging: false
          Parameters:
            - ManagedMcpConfigJson
    - TemplateName: ACS企业版
      Operation:
        - Name: Manage-Gateway-MCP
          Description: 接入或移出网关MCP
          Type: Custom
          SupportPredefinedParameters: false
          EnableLogging: false
          Parameters:
            - ManagedMcpConfigJson
```

当前消费者侧 `UpdateServiceInstanceAttributes` 不能写 Parameters。接入、移出、清理失效项需要走服务实例变更入口，例如 `UpdateServiceInstanceSpec` + `operationName=Manage-Gateway-MCP`。如果当前服务版本还没有这个 Operation，前端不能展示“接入当前实例”，需要提示先升级服务版本或走 AI 网关控制台管理。

参数值使用数组：

```json
[
  {
    "mcpServerId": "mcp-xxx",
    "gatewayId": "gw-xxx",
    "name": "order-api",
    "displayName": "订单查询 API",
    "source": "gateway_managed",
    "createFromType": "ApiGatewayHttpToMCP",
    "mcpServerPath": "/mcp-servers/order-api",
    "managedAt": "2026-06-17T10:00:00Z",
    "lastSyncedAt": "2026-06-17T10:05:00Z",
    "lastObservedStatus": "Deployed",
    "status": "managed"
  }
]
```

字段说明：

| 字段 | 作用 |
|------|------|
| `mcpServerId` | 主关联键，用于回查 APIG MCP Server。 |
| `gatewayId` | 校验该 MCP 是否仍属于当前实例关联网关。 |
| `name` / `displayName` | 展示名称快照。 |
| `source` | 固定为 `gateway_managed`，表示来自网关接入。 |
| `createFromType` | 当前固定为 `ApiGatewayHttpToMCP`。 |
| `mcpServerPath` | 展示和 Agent 配置使用的路径快照。 |
| `managedAt` | 纳管时间。 |
| `lastSyncedAt` | 最近一次和 AI 网关对账时间。 |
| `lastObservedStatus` | 最近一次从 AI 网关读到的部署状态。 |
| `status` | 计算巢侧展示状态：`managed`、`unavailable`、`invalid`、`removed`。 |

### 4. 状态对账

用户后续可以在 AI 网关里手动改名、修改路径、更新工具、停用或删除 MCP，因此计算巢和 AI 网关可能出现不一致。处理原则：

- AI 网关是真实状态源。
- `ManagedMcpConfigJson` 是纳管关系和快照，不是 MCP Server 的最终状态。
- 服务实例详情页和 Agent 部署页打开时，先读取服务实例 Parameters，再用标准化后的 `gatewayId` 调 `ListMcpServers`，按 `mcpServerId` 合并。
- 页面展示使用合并后的实时结果；只有纳管、取消纳管、同步快照、清理失效项时才回写 Parameters，避免每次打开页面都触发服务实例参数写入。
- Agent 保存前再次对选中的 `mcpServerId` 做校验，校验不通过则阻断保存。

对账结果：

| AI 网关状态 | 计算巢处理 |
|------------|------------|
| `mcpServerId` 存在、`gatewayId` 一致、状态为 Deployed | 展示为可用；名称、路径、工具以 AI 网关最新值为准。 |
| 名称、路径或工具发生变化 | 继续可用；展示最新值，可在用户保存或点击刷新后更新快照。 |
| MCP 存在但不是 Deployed | 展示为不可用，Agent 不可选择，引导用户去 AI 网关恢复。 |
| MCP 已删除或查不到 | 展示为已失效，保留纳管记录，提供“移出实例 / 清理失效项”。 |
| `gatewayId` 不一致或类型不再是 HTTP 转 MCP | 展示为来源异常，Agent 不可选择，需要重新纳管。 |

如果用户在 AI 网关删除后又创建了同名 MCP，它会拥有新的 `mcpServerId`，计算巢不按名称自动绑定。旧记录展示为已失效，新 MCP 需要用户重新纳管，避免同名误认领。

### 5. 服务实例展示

服务实例详情展示统一的“实例 MCP 清单”，由两部分合并：

```text
实例 MCP 清单
├── 实例部署 MCP
│   ├── GitHub
│   └── Fetch
└── 网关接入 MCP
    ├── 订单查询 API
    └── CRM 客户 API
```

展示规则：

- 卡片标题使用 MCP 展示名。
- 元信息用 `网关接入 · 已接入`。
- 如果 APIG 中查不到该 MCP，展示 `网关接入 · 已失效`，并禁止 Agent 选择。
- 详情页提供“刷新状态”“移出实例”“清理失效项”一类管理动作，动作只影响纳管关系，不删除 AI 网关 MCP Server。
- 不在实例详情里强调 HTTP 转 MCP，除非用户进入详情查看来源。

### 6. Agent 展示与输出

Agent 部署页只做使用选择，不做纳管管理。

页面仍然先选择 MCP 网关服务实例，再展示该实例网关内全部可用 MCP。这里不区分 MCP 来源，也不展示“HTTP 转 MCP / 实例部署 / 已接入”等类型标签。只要已经进入实例 MCP 清单，Agent 都可以选择。

Agent 页刷新和保存时也要做状态对账。默认只展示可用 MCP；如果历史选择里的 MCP 已失效，保留一条通用“不可用”状态，方便用户移除选择，但不暴露来源类型。

```text
选择 MCP 网关实例
    |
    v
展示服务实例可用 MCP
    ├── Fetch
    ├── LeetCode
    ├── 订单查询 API
    └── CRM 客户 API
```

Agent 输出配置：

```json
{
  "serviceInstanceId": "si-xxx",
  "gatewayId": "gw-xxx",
  "mcpServers": [
    {
      "mcpServerId": "mcp-xxx",
      "name": "order-api",
      "tools": []
    }
  ]
}
```

---

## UI 文案

配置 MCP 弹窗来源切换：

```text
公共 MCP | 自定义 MCP | 网关接入
```

这里用“网关接入”做短标签，避免左侧来源切换换行。完整解释放在该页签的说明文案中：只查询当前网关下已部署的 HTTP 转 MCP，接入后写入 `ManagedMcpConfigJson`，不会重新注册 MCP Server。

操作按钮：

```text
接入当前实例
```

分组名称：

```text
可用 MCP
```

提示文案：

> 选择实例后展示该实例网关内全部可用 MCP。Agent 使用时不区分 MCP 来源和创建方式。

---

## 前端改造点

### 1. 配置 MCP 弹窗

弹窗左侧只负责“来源切换 + MCP 列表”，右侧负责“当前选中项详情”。不要把“接入网关 MCP”做成长标签页，视觉上使用紧凑来源切换：

```text
选择来源
[ 公共 MCP ][ 自定义 MCP ][ 网关接入 ]
搜索框
来源内 MCP 列表
```

前端状态：

| 状态 | 说明 |
|------|------|
| `sourceType=public` | 读取公共 MCP 市场数据，保存到 `McpConfigJson`。 |
| `sourceType=custom` | 读取用户自定义 MCP 配置，保存到 `McpConfigJson`。 |
| `sourceType=gateway` | 读取当前服务实例关联网关内已有 HTTP 转 MCP，保存到 `ManagedMcpConfigJson`。 |
| `selectedMcpId` | 当前右侧详情展示的 MCP。 |
| `selectedMcpIds` | 当前准备加入实例的 MCP 集合。 |

`sourceType=gateway` 时，前端调用后端包装接口获取候选列表。后端包装接口负责：

```text
serviceInstanceId
  -> 查询服务实例 Outputs.HigressAI，兼容 Outputs.GatewayId / Parameters.HigressAI
  -> 查询服务实例 Parameters.ManagedMcpConfigJson
  -> ListMcpServers(gatewayId, createFromTypes=ApiGatewayHttpToMCP)
  -> 按 mcpServerId 合并已接入状态
```

列表状态：

| 状态 | 前端展示 | 操作 |
|------|----------|------|
| 未接入 | `可接入` | 展示“接入当前实例”。 |
| 已接入且 Deployed | `已接入` | 可从实例移出。 |
| 已接入但非 Deployed | `不可用` | 禁止选择，引导去 AI 网关恢复。 |
| 已接入但查不到 | `已失效` | 只允许移出或清理。 |

右侧详情：

- 公共 MCP：展示服务定义和运行参数，只允许编辑运行参数。
- 自定义 MCP：允许编辑名称、安装方式、连接地址、环境变量等自定义配置。
- 网关接入：只读展示 AI 网关返回的名称、路径、工具、部署状态；只提供接入/移出，不允许在这里编辑 MCP Server 本体。

接入动作：

1. 前端传 `serviceInstanceId + mcpServerId`。
2. 后端重新读取服务实例，标准化 `gatewayId`，并调用 APIG 校验该 MCP 是当前网关下 `ApiGatewayHttpToMCP + Deployed`。
3. 后端读取当前 `ManagedMcpConfigJson`，按 `mcpServerId` 去重合并。
4. 后端通过服务实例参数变更写回 `ManagedMcpConfigJson`。
5. 写回后重新读取服务实例和 APIG，返回合并后的列表。

移出动作只删除 `ManagedMcpConfigJson` 中对应 `mcpServerId`，不调用 `DeleteMcpServer`，也不修改 `McpConfigJson`。

### 2. 服务实例详情

服务实例详情页读取两个来源后合并展示：

```text
McpConfigJson              -> 实例部署 MCP
ManagedMcpConfigJson + APIG -> 网关接入 MCP
```

前端打开详情页时要触发一次对账：

1. 读取服务实例中的网关 ID：优先 `Outputs.HigressAI`，兼容 `Outputs.GatewayId` 和 `Parameters.HigressAI`。
2. 读取 Parameters 中的 `McpConfigJson` 和 `ManagedMcpConfigJson`。
3. 用标准化后的 `gatewayId` 查询 AI 网关 MCP Server 列表。
4. 按 `mcpServerId` 更新网关接入项的可用、不可用、已失效状态。
5. 对实例部署 MCP，用 `${serviceInstanceName}-${serverCode}` 小写后和 APIG 返回的 `name` 匹配。匹配且 `deployStatus=Deployed` 才算可用；匹配不到时在详情页展示不可用，Agent 不可选择。
6. 页面上只展示“实例 MCP 清单”；卡片上可以展示 `网关接入 · 已接入` 这类管理来源，但不影响 Agent 使用。

详情页动作：

| 动作 | 行为 |
|------|------|
| 刷新状态 | 重新查询 AI 网关并更新页面状态。 |
| 移出实例 | 只从 `ManagedMcpConfigJson` 删除对应记录，不删除 AI 网关 MCP Server。 |
| 清理失效项 | 批量删除 `status=invalid` 的纳管记录。 |

### 3. Agent 部署 AssociationProperty

Agent 部署页需要新增一个计算巢侧 AssociationProperty，职责是“先选服务实例，再选该实例可用 MCP”。它不是复用 `ALIYUN::MCP::Server::Server`，因为这里的选择范围来自已部署服务实例。

建议语义：

```yaml
AssociationProperty: ALIYUN::ComputeNest::MCP::GatewayMcpServers
AssociationPropertyMetadata:
  ServiceId: ${McpGatewayServiceId}
  RegionId: ${RegionId}
  InstanceStatus:
    - Deployed
  RequireOutput:
    - HigressAI
  OutputGatewayIdAliases:
    - HigressAI
    - GatewayId
  ParameterGatewayIdAliases:
    - HigressAI
  IncludeManagedMcp: true
```

前端渲染规则：

1. 左侧只展示 `ServiceId` 匹配的计算巢 MCP 网关服务实例。
2. 用户选择服务实例后，读取并标准化该实例 `gatewayId`。
3. 用 `gatewayId` 查询该网关下 `deployStatus=Deployed` 的 MCP Server。
4. 合并 `ManagedMcpConfigJson` 的失效状态，默认只让用户选择可用 MCP。
5. 对 `McpConfigJson` 中的实例部署 MCP，用 `${serviceInstanceName}-${serverCode}` 小写后匹配 APIG `name`，避免展示已经写入参数但实际没有部署成功的 MCP。
6. Agent 页不展示“公共 / 自定义 / 网关接入 / HTTP 转 MCP”等来源标签，只展示 MCP 名称、路径和可用状态。工具摘要只有在后端能拿到 tools 明细时展示，当前 APIG List/Get 不返回 tools。
7. 点击保存前重新校验选中的 `mcpServerId` 是否仍存在且 Deployed。

输出值：

```json
{
  "serviceInstanceId": "si-xxx",
  "gatewayId": "gw-xxx",
  "mcpServers": [
    {
      "mcpServerId": "mcp-xxx",
      "name": "order-api",
      "displayName": "订单查询 API",
      "path": "/mcp-servers/order-api",
      "tools": []
    }
  ]
}
```

### 4. 前端边界

- 配置弹窗负责接入和移出，Agent 部署页只负责使用选择。
- 前端不直接调用 `CreateMcpServer` 创建 HTTP 转 MCP。
- 前端不把网关接入项写入 `McpConfigJson`。
- 前端不按名称自动恢复已失效项，必须基于新的 `mcpServerId` 重新接入。

---

## 边界

- 纳管项不进入 FC/ACS 注册逻辑。
- 网关接入项只更新 `ManagedMcpConfigJson` 纳管关系，不触发 FC/ACS 资源变更或 MCP 重新注册。
- 网关接入项不重复调用 `CreateMcpServer`。
- 取消纳管只删除计算巢侧纳管关系，不删除 AI 网关中的 MCP Server。
- 删除服务实例时，默认不删除纳管的 HTTP 转 MCP；除非后续明确提供“同时删除外部 MCP”能力。
- 如果 AI 网关中的 MCP Server 被删除或变为非 Deployed，计算巢侧展示为“已失效”，Agent 部署时不可选择。
- 同名重建不自动恢复纳管关系，必须按新的 `mcpServerId` 重新纳管。

---

## 参考

- APIG `ListMcpServers`: https://help.aliyun.com/zh/api-gateway/ai-gateway/developer-reference/api-apig-2024-03-27-listmcpservers-ai-gateway
