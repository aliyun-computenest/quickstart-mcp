# 快速打造企业内部的MCP市场

随着企业数字化转型的深入，Model Context Protocol (MCP) 作为连接AI模型与企业数据的重要桥梁，正在成为企业AI应用的核心基础设施。阿里云计算巢为企业提供了完整的MCP市场解决方案，帮助企业快速构建内部私有化的MCP服务平台，实现AI能力的统一管理和分发。本文介绍如何基于计算巢构建企业内部MCP市场，包括系统架构设计、公开和私有MCP服务部署、权限管理以及企业级功能特性。

**核心组件：**

+ **MCP集群管理**：支持私有和公开MCP包的统一管理
+ **AI网关（Higress）**：提供统一的API入口和路由控制
+ **权限控制模块**：基于API Key的多租户权限管理
+ **基础设施管理**：包含动态伸缩、服务发现、健康检查等

**架构特点：**

### 部署架构
![](./img/deploy.png)

#### 企业内建MCP平台产品架构一-托管版
![img_5.png](img_5.png)

#### 企业内建MCP平台产品架构二-自建版
![img_6.png](img_6.png)


+ 私有MCP包通过OSS存储，支持本地化部署
+ AI网关提供统一的API访问入口和认证机制
+ 支持REST API转MCP协议的智能转换
+ 完整的监控和日志管理体系

### 1.2 多协议支持
**协议支持：**

+ **MCP原生协议**：SSE长连接，实时交互
+ **OpenAPI REST**：标准HTTP接口
+ **Streamable HTTP**：分块传输，支持大数据流处理

### 1.3 部署模式
**社区版能力：**

+ ✅ 快速部署MCP，支持私有化部署
+ ✅ 支持实例变配和MCP调试
+ ✅ 简单的MCP管控面板

**企业版增强：**

在社区版基础上，支持以下功能

+ ✅ 支持选择已有AI网关实例和自定义域名
+ ✅ 企业级权限管理和API Key分发
+ ✅ 完备的MCP管控面板



## 前提条件
<font style="color:rgb(51, 51, 51);">部署Dify社区版服务实例，需要对部分阿里云资源进行访问和创建操作。因此您的账号需要包含如下资源的权限。</font><font style="color:rgb(51, 51, 51);"> </font>**<font style="color:rgb(51, 51, 51);">说明</font>**<font style="color:rgb(51, 51, 51);">：当您的账号是RAM账号时，才需要添加此权限。</font>

| <font style="color:rgb(51, 51, 51);">权限策略名称</font> | <font style="color:rgb(51, 51, 51);">备注</font> |
| --- | --- |
| <font style="color:rgb(51, 51, 51);">AliyunECSFullAccess</font> | <font style="color:rgb(51, 51, 51);">管理云服务器服务（ECS）的权限</font> |
| <font style="color:rgb(51, 51, 51);">AliyunVPCFullAccess</font> | <font style="color:rgb(51, 51, 51);">管理专有网络（VPC）的权限</font> |
| <font style="color:rgb(51, 51, 51);">AliyunROSFullAccess</font> | <font style="color:rgb(51, 51, 51);">管理资源编排服务（ROS）的权限</font> |
| <font style="color:rgb(51, 51, 51);">AliyunComputeNestUserFullAccess</font> | <font style="color:rgb(51, 51, 51);">管理计算巢服务（ComputeNest）的用户侧权限</font> |


## 二、公开MCP服务部署
### 2.1 公开MCP服务类型
计算巢MCP市场支持多种类型的公开MCP服务：

**标准公开MCP工具：**

+ 浏览器自动化工具
+ 位置服务和地图工具
+ 搜索引擎工具
+ 开发者工具集
+ 文件处理工具
+ 数据分析工具

**自定义公开MCP服务：**

+ 支持从公共仓库安装的NPX包
+ 支持从公共仓库安装的UVX包
+ 已有的SSE MCP服务纳管

### 2.2 公开MCP服务部署流程
#### 2.2.1 快速部署步骤
1. **访问MCP市场**
    - 进入计算巢首点击"MCP市场"
    - 浏览可用的公开MCP工具

![](https://intranetproxy.alipay.com/skylark/lark/0/2025/png/63156287/1755671732619-62dd14ba-fe9c-4c9e-a38c-68018095db10.png)

2. **选择MCP工具**
    - 选择要部署的MCP工具，如"必应搜索中文"
    - 点击MCP工具进入详细文档界面![](https://intranetproxy.alipay.com/skylark/lark/0/2025/png/63156287/1755671757929-0af51a20-5bf6-4812-995e-58c6eb628a45.png)
    - 查看工具功能说明和使用示例
3. **部署配置**
    - 点击右上角的"部署"按钮
    - 选择创建新的服务实例或部署到已有实例![](https://intranetproxy.alipay.com/skylark/lark/0/2025/png/63156287/1755671829630-a898a2b0-bd60-423a-8c1a-bd902ba832c7.png)
    - 多个MCP工具可部署在同一服务实例内
4. **资源配置**
    - 根据业务情况选择包年包月或按量付费
    - 选择合适的ECS实例规格
    - 配置网络和安全组设置
5. **完成部署**
    - 点击"立即创建"开始部署
    - 等待服务实例创建完成
    - 获取MCP控制台和调试界面访问地址

## 三、私有MCP服务部署
注意：如果无可用的OSS Bucket建议先通过任意公开MCP包创建出计算巢服务实例，该服务实例会自动创建出符合规范的OSS仓库。
如需要使用已有的OSS Bucket，可参考以下步骤进行授权：
1. 访问[OSS控制台](https://oss.console.aliyun.com/bucket)
2. 找到Bucket授权策略。![img_8.png](img_8.png)
3. ![img_9.png](img_9.png)
### 3.1 支持的MCP格式
计算巢MCP市场支持标准的包管理格式：

**Python (UVX) 格式：**

+ 支持文件类型：`.whl`、`.tar.gz`
+ 基于[PEP 518标准](https://peps.python.org/pep-0518/)的pyproject.toml配置
+ 示例仓库：[https://github.com/aliyun-computenest/mcp-python-demo](https://github.com/aliyun-computenest/mcp-python-demo)

**JavaScript (NPX) 格式：**

+ 支持文件类型：`.tgz`
+ 基于标准的package.json配置
+ 示例仓库：[https://github.com/aliyun-computenest/mcp-js-demo](https://github.com/aliyun-computenest/mcp-js-demo)

### 3.2 Python MCP包创建流程
#### 3.2.1 项目配置
创建符合标准的`pyproject.toml`文件：

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "your-mcp-package"           # 包名（必需）
version = "1.0.0"                   # 版本号（必需）
description = "Your MCP Server description"
authors = [
    {name = "Your Name", email = "your.email@example.com"}
]
readme = "README.md"
requires-python = ">=3.8"          # Python版本要求
dependencies = []                   # 运行时依赖

# 脚本入口点配置（必需）
[project.scripts]
your-mcp-command = "your_package_name.server:main"

[project.urls]
Homepage = "https://github.com/your-username/your-mcp-package"

# 构建配置
[tool.hatch.build.targets.wheel]
packages = ["src/your_package_name"]
```

#### 3.2.2 部署步骤


### 部署参数说明

| <font style="color:rgb(51, 51, 51);">参数组</font>     | <font style="color:rgb(51, 51, 51);">参数项</font>         | <font style="color:rgb(51, 51, 51);">说明</font>                                            |
|-----------------------------------------------------|---------------------------------------------------------|-------------------------------------------------------------------------------------------|
| <font style="color:rgb(51, 51, 51);">MCP配置</font>   | <font style="color:rgb(51, 51, 51);">McpConfigJson</font>  | <font style="color:rgb(51, 51, 51);">需要使用的MCP工具</font>                                    |
|    | <font style="color:rgb(51, 51, 51);">MCP_KEY</font> | <font style="color:rgb(51, 51, 51);">MCP Server和大模型交互的秘钥</font>                           |
| <font style="color:rgb(51, 51, 51);">服务实例</font>    | <font style="color:rgb(51, 51, 51);">服务实例名称</font>      | <font style="color:rgb(51, 51, 51);">长度不超过64个字符，必须以英文字母开头，可包含数字、英文字母、短划线（-）和下划线（_）</font> |
|                                                     | <font style="color:rgb(51, 51, 51);">地域</font>          | <font style="color:rgb(51, 51, 51);">服务实例部署的地域</font>                                     |
|                                                     | <font style="color:rgb(51, 51, 51);">付费类型</font>        | <font style="color:rgb(51, 51, 51);">资源的计费类型：按量付费和包年包月</font>                             |
| <font style="color:rgb(51, 51, 51);">ECS实例配置</font> | <font style="color:rgb(51, 51, 51);">实例类型</font>        | <font style="color:rgb(51, 51, 51);">可用区下可以使用的实例规格</font>                                 |
|                                                     | <font style="color:rgb(51, 51, 51);">实例密码</font>        | <font style="color:rgb(51, 51, 51);">长度8-30，必须包含三项（大写字母、小写字母、数字、 ()`~!@#$%^&*-+=          |{}[]:;'<>,.?/ 中的特殊符号）</font> |
| <font style="color:rgb(51, 51, 51);">网络配置</font>    | <font style="color:rgb(51, 51, 51);">可用区</font>         | <font style="color:rgb(51, 51, 51);">ECS实例所在可用区</font>                                    |
|                                                     | <font style="color:rgb(51, 51, 51);">VPC ID</font>      | <font style="color:rgb(51, 51, 51);">资源所在VPC</font>                                       |
|                                                     | <font style="color:rgb(51, 51, 51);">交换机ID</font>       | <font style="color:rgb(51, 51, 51);">资源所在交换机</font>                                       |

1. **访问计算巢MCP市场**
    - 进入计算巢首页，点击"MCP市场"![](https://intranetproxy.alipay.com/skylark/lark/0/2025/png/63156287/1755671281379-bb1ec856-e135-4f51-a837-54b04804345e.png)
    - 选择"创建自定义MCP"
2. **基础信息配置**
    - 上传MCP图标（支持自定义图标）
    - 设置MCP名称和唯一ID
    - 注意：同一服务实例下ID不能重复
3. **包上传配置**
    - 选择安装方式为"UVX"
    - 选择合适的地域和OSS Bucket
    - 上传.whl或.tar.gz格式的软件包![](https://intranetproxy.alipay.com/skylark/lark/0/2025/png/63156287/1755671299420-f3ec69bc-d612-4671-b713-c59fe5ebf0e1.png)
4. **启动参数配置**
    - **默认参数**：系统自动生成启动命令（不可修改）

```bash
uvx /mcp-package/your-package-name.whl
```

    - **自定义参数**：可添加额外的启动参数

```bash
--timezone Asia/Shanghai --config /path/to/config
```

    - **环境变量**：设置运行时需要的环境变量，如API Key等![](https://intranetproxy.alipay.com/skylark/lark/0/2025/png/63156287/1755671372337-f6f5837f-cedf-47b6-9c28-fa459ebf8f0c.png)
5. **服务实例部署**
    - **选择创建新的服务实例** 或 **部署到已有实例**![](https://intranetproxy.alipay.com/skylark/lark/0/2025/png/63156287/1755671378733-99fbb08e-3ba9-45ad-981a-cb6e90376ada.png)
    - 等待部署完成，通过MCP管控平台查看服务状态![](https://intranetproxy.alipay.com/skylark/lark/0/2025/png/63156287/1755671400235-587248ba-ab5d-499e-8350-3290e7ab77a1.png)

### 3.3 JavaScript MCP包创建流程
#### 3.3.1 项目配置
确保`package.json`包含正确的配置：

```json
{
  "name": "your-mcp-package",
  "version": "1.0.0",
  "description": "Your MCP Server description",
  "main": "index.js",
  "bin": {
    "your-mcp-command": "./bin/server.js"
  },
  "dependencies": {
    "@modelcontextprotocol/sdk": "^0.4.0"
  }
}
```

#### 3.3.2 部署步骤
1. **包格式准备**
    - 使用`npm pack`生成.tgz包文件
2. **上传配置**
    - 选择安装方式为"NPX"
    - 上传.tgz格式的软件包![](https://intranetproxy.alipay.com/skylark/lark/0/2025/png/63156287/1755671413339-ab5bf527-9ae7-4a7f-835b-c6d5916be733.png)
3. **启动参数配置**
    - **默认参数**：

```bash
npx -y --package /mcp-package/your-package.tgz ${启动命令}
```

    - **自定义参数**：第一个参数必须是可执行文件映射（package.json中bin字段的值）
    1. 用户如果有自定义参数项，比如给package设置时区，则可传入类似--from cn-beijing的值进行设置。此处会通过空格解析传入的指令

```bash
your-mcp-command --config /path/to/config
```

4. **环境变量：**如果您使用的MCP Server的package需要设置环境变量，比如高德地图的API Key，则可在此处设置。设置完后点击下一步![](https://intranetproxy.alipay.com/skylark/lark/0/2025/png/63156287/1755671515100-e538bf5d-403a-4b54-b856-9c086de6d849.png)
5. **直接新建服务实例** Or **选择已有的服务实例**
    1. 如果想通过刚刚的配置**直接创建服务实例**，则选择界面左侧上方的“创建服务实例”按钮。
    2. 如果想将该MCP直接部署到“**已有的服务实例**”，则在下方选择某个服务实例，并点击开始部署

![](https://intranetproxy.alipay.com/skylark/lark/0/2025/png/63156287/1755671557989-cfa14fc4-63ec-45b9-b178-0bc1069b3b96.png)

6. 待服务实例部署完后，可点击MCP管控平台查看整体的MCP服务，或在下方可用的MCP服务处选择某一个来查看：![](https://intranetproxy.alipay.com/skylark/lark/0/2025/png/63156287/1755671572189-e452d26e-4565-47c4-b71d-dc1ff486eef0.png)



### 3.4 私有MCP包管理
#### 3.4.1 包存储机制
**OSS存储方案：**

+ 所有私有包统一上传到用户自有的OSS Bucket根目录

**安全控制：**

+ 通过ECS RAM Role实现安全的OSS访问
+ 支持包的加密存储
+ 实施访问日志和审计

#### 3.4.2 包部署流程
**自动化部署流程：**

1. **环境检查**：检查OSSUtil工具是否已安装配置
2. **包下载**：从OSS下载私有MCP包到本地
3. **服务启动**：根据配置启动MCP服务
4. **健康检查**：验证服务是否正常运行
5. **服务注册**：将服务注册到AI网关

## 四、企业内部API转MCP服务
### 4.1 API转MCP适配器
对于企业内部的API服务，可基于AI网关实现已有API转MCP。

参考文档：[https://higress.cn/en/blog/higress-gvr7dx_awbbpb_mpavtgoff5h3odvq/](https://higress.cn/en/blog/higress-gvr7dx_awbbpb_mpavtgoff5h3odvq/)

或参考AI网关的API：SwaggerToMCPConfig

**适用场景：**

+ 企业内部API服务
+ 满足OpenAPI规范的配置文件
+ 需要转换为MCP协议的现有服务

**转换能力：**

+ 支持将OpenAPI规范批量转化为MCP Server
+ 自动生成MCP协议适配层
+ 保持原有API的功能和性能

## 五、企业接入指南
前提：新建AI网关实例。

具体可参考：[https://help.aliyun.com/zh/api-gateway/ai-gateway/user-guide/create-a-gateway-instance?spm=a2c4g.11186623.help-menu-29462.d_2_0_0.4b7844eerOks7g&scm=20140722.H_2881527._.OR_help-T_cn~zh-V_1](https://help.aliyun.com/zh/api-gateway/ai-gateway/user-guide/create-a-gateway-instance?spm=a2c4g.11186623.help-menu-29462.d_2_0_0.4b7844eerOks7g&scm=20140722.H_2881527._.OR_help-T_cn~zh-V_1)

### 5.1 企业级MCP市场展示
在企业版计算巢服务实例中，展示了可用的MCP：![](https://intranetproxy.alipay.com/skylark/lark/0/2025/png/63156287/1755672011180-544f2a66-e7ee-4497-9b74-6c8283e7eee3.png)

此处需要调用AI网关的API：[ListHttpApiRoutes](https://api.aliyun.com/api/APIG/2024-03-27/ListHttpApiRoutes)和[**ListHttpApis**](https://api.aliyun.com/document/APIG/2024-03-27/ListHttpApis)**查询可用的MCP：包含API转MCP和私有公开包拉起的MCP。**

**调用逻辑如下：**

1. 首先通过[ListHttpApis](https://api.aliyun.com/document/APIG/2024-03-27/ListHttpApis)获取ApiId。
    1. 入参：

```json
  "gatewayId": "gw-d1qbbium1hko66pmepf0",（从服务实例Parameters里取）
  "gatewayType": "AI",（固定）
  "keyword": "mcp",（固定）
```

    2. 出参中获取到type为MCP的唯一的MCP相关的httpApiId
2. 接着通过[ListHttpApiRoutes](https://api.aliyun.com/document/APIG/2024-03-27/ListHttpApiRoutes)查询当前网关MCP信息：
    1. 传入第一步查询出来的httpApiId和本身的gatewayId
    2. 获取到所有可用的MCP
    3. 对于计算巢部署的MCP，在**Description**字段中存储了该MCP的图标，名称和描述。参考以下字段：

```json
{
  "Name": "MCP-Name",
  "Description": "该服务器使大型语言模型能够检索和处理网页内容，将HTML转换为markdown格式，以便于更轻松地使用。",
  "Path": "oss://packages/nodejs/web-scraper-mcp-1.0.0.tgz或whl",
  "Icon": "https://resources.modelscope.cn/studio-cover-pre/studio-cover_761f7bfe-fc5c-4753-b955-dcdd3288941b.png",
}
```

3. 将以上结果作为卡片展示即可。

### 5.2 企业级权限管理架构
**权限控制模块包含以下核心组件：**

+ **消费者管理（Consumer Management）**：管理不同业务团队的身份标识
+ **API Key认证**：基于API Key的身份验证机制
+ **授权策略引擎**：控制消费者对MCP服务的访问权限
+ **路由级权限控制**：在AI网关层面实现精细化的路由访问控制

**权限模型：**

```plain
企业平台
├── 业务团队A (Consumer A)
│   ├── API Key: bmw-team-a-001
│   └── 权限: MCP1, MCP2, MCP3
├── 业务团队B (Consumer B)
│   ├── API Key: bmw-team-b-002
│   └── 权限: MCP4, MCP5, MCP6
└── 业务团队C (Consumer C)
    ├── API Key: bmw-team-c-003
    └── 权限: MCP1, MCP4, MCP5
```

### 5.2 消费者与API Key管理
#### 5.2.1 消费者创建流程
平台管理员通过调用`[CreateConsumer](https://api.aliyun.com/api/APIG/2024-03-27/CreateConsumer?RegionId=cn-hangzhou)` API为业务团队创建消费者身份：

**API调用示例：**

```json
{
  "apiKeyIdentityConfig": {
    "apikeySource": {
      "source": "QueryString",
      "value": "apikey"
    },
    "type": "Apikey",
    "credentials": [
      {
        "generateMode": "Custom",
        "apikey": "bmw-team-a-001"
      }
    ]
  },
  "name": "会计团队",
  "enable": true,
  "gatewayType": "AI"
}
```

**响应示例：**

```json
{
  "code": "Ok",
  "data": {
    "consumerId": "cs-d2437ium1hkoc92qbpo0"
  },
  "requestId": "3CA6571A-937B-3164-8DE7-11716FA43466"
}
```

#### 5.2.2 API Key管理最佳实践
**API Key命名规范建议：**

```plain
{企业标识}-{团队标识}-{序号}
例如：bmw-finance-001, bmw-frontend-002
```

**安全策略：**

+ API Key应存储在安全的配置管理系统中
+ 避免在代码中硬编码API Key
+ 定期轮换API Key提升安全性
+ 实施IP白名单限制

### 5.3 MCP服务授权机制
#### 5.3.1 启用MCP服务认证
为每个MCP服务启用认证机制，调用`[CreateAndAttachPolicy](https://api.aliyun.com/api/APIG/2024-03-27/CreateAndAttachPolicy?RegionId=cn-hangzhou)` API：

```json
{
  "attachResourceType": "GatewayRoute",
  "gatewayId": "gw-d1qbbium1hko66pmepf0",
  "environmentId": "env-d1qbc7em1hkluu4lgagg",
  "config": "{\"authenticationType\":\"Apikey\",\"enable\":true}",
  "className": "Authentication",
  "attachResourceIds": [
    "hr-d1sqdqem1hkrte7kn3t0"
  ]
}
```

#### 5.3.2 消费者授权
通过`[CreateConsumerAuthorizationRules](https://api.aliyun.com/api/APIG/2024-03-27/CreateConsumerAuthorizationRules?RegionId=cn-hangzhou)` API为消费者授权访问特定MCP服务：

```json
{
  "authorizationRules": [
    {
      "consumerId": "cs-d242jsum1hkktoltohs0",
      "resourceIdentifier": {
        "resourceId": "hr-d1sqdqem1hkrte7kn3t0",
        "environmentId": "env-d1qbc7em1hkluu4lgagg"
      },
      "resourceType": "MCP",
      "expireMode": "LongTerm"
    }
  ]
}
```

### 5.4 权限申请工作流
**在企业内部可参考一下流程实现API Key的自动化：**

1. **业务团队提交申请**：选择需要访问的MCP服务列表
2. **平台方审核**：验证申请的合理性和安全风险
3. **自动化授权**：系统自动创建消费者并执行授权操作
4. **权限生效**：业务团队获得API Key并开始使用

## 六、MCP服务使用与集成
### 6.1 AI助手集成
#### 6.1.1 Cherry Studio集成示例
**配置步骤：**

1. **获取MCP配置信息**
    - 访问计算巢实例界面
    - 选择要使用的MCP工具进入详情页面![](https://intranetproxy.alipay.com/skylark/lark/0/2025/png/63156287/1755672855209-32c96532-4b19-4168-a0db-4b0e774f5d20.png)
    - 复制MCP服务器配置信息![](https://intranetproxy.alipay.com/skylark/lark/0/2025/png/63156287/1755672883451-03bb2b06-80f3-45dd-be12-ab35884cfc78.png)
2. **配置Cherry Studio**
    - 打开Cherry Studio助手
    - 新建MCP服务器配置
    - 粘贴从控制台复制的配置信息![](https://intranetproxy.alipay.com/skylark/lark/0/2025/png/63156287/1755672904468-68d5a7d3-12b8-4866-b4ae-77b17f919439.png)
    - 如果鉴权参数未自动识别，需要手动复制API Key
3. **启用和使用**
    - 点击右上角的"启用"和"保存"
    - 进入对话界面，选择要使用的MCP工具
    - 开始与AI助手进行对话，调用MCP工具功能

#### 6.1.2 其他AI助手集成
**通用集成方式：**

+ 支持所有兼容MCP协议的AI助手
+ 提供标准的MCP服务器配置格式
+ 支持SSE、HTTP等多种连接方式

## 七、运维监控
### 7.1 服务监控
#### 7.1.1 健康检查
**监控指标：**

+ 实例健康状态监控

访问服务实例监控面板可查看ECS监控指标![](https://intranetproxy.alipay.com/skylark/lark/0/2025/png/63156287/1755673758130-57ed40c3-37a3-465d-a983-e4d1bb69f310.png)

+ MCP服务可用性检测。

MCP调用日志，网关日志可在AI网关控制台查看![](https://intranetproxy.alipay.com/skylark/lark/0/2025/png/63156287/1755673812680-87dbbc39-34d1-421c-93ec-a2a02d5c6974.png)

+ 性能指标收集和告警![](https://intranetproxy.alipay.com/skylark/lark/0/2025/png/63156287/1755770219457-0157a65a-755e-4c6d-968e-32be6a6295e5.png)
+ 资源使用情况统计![](https://intranetproxy.alipay.com/skylark/lark/0/2025/png/63156287/1755769959025-4f44d7df-2b24-4cfc-b663-42c00ae3f0c9.png)



## 九、Q&A
Q: OSS文件上传失败。

A：需要选择的OSS关闭”阻止公共访问“，且对当前RAM账号开启授权了。可参考以下两张参考图：![](https://intranetproxy.alipay.com/skylark/lark/0/2025/png/63156287/1755676058218-97206989-cdf7-4cd4-9a97-f765034b40a9.png)

![](https://intranetproxy.alipay.com/skylark/lark/0/2025/png/63156287/1755676129819-e8ecfe64-4c05-4d1e-8519-88c28f106db4.png)




## 调试和实际使用示例

1. 点击MCP Server实例，进入控制台界面，点击"MCP 调试控制台"![img_1.png](img_1.png)
2. 进入后是一个swagger版本的调试控制台，如图所示。![img_2.png](img_2.png)
3. 点击需要测试的工具，比如图里的"fetch"，进入到具体的MCP调试界面。按照图示进行测试即可![img_3.png](img_3.png)

## 修改要使用的MCP工具
如果想要修改要使用的MCP工具请参考下列操作
1. 在计算巢控制台，点击"我的实例"，选择之前部署的MCP Server实例，点击右上方的"修改配置"。![img.png](update/img.png)
2. 点击修改MCP工具，并点击"下一步"![img_1.png](update/img_1.png)
3. 选择想要新增的MCP工具，比如我这新增了Fetch工具。（注意：之前选择的工具在此处会被重新渲染）![img_2.png](update/img_2.png)
4. 当然这里如果涉及到环境变量，则一定要按照文档进行设置。
5. 点击确定，发起工具修改请求。![img_3.png](update/img_3.png)
6. 等待实例状态变更完。![img_4.png](update/img_4.png)
7. 将输出中新增的MCP工具加入到AI对话客户端中。![img_5.png](update/img_5.png)


## Cherry Studio使用示例
1. 来到计算巢实例界面，![img_7.png](img-deploy/img_7.png),点击MCP 控制台
2. 选择要使用的工具点进进去，![img.png](img.png)
2. 打开您的Cherry Studio助手，按照下图示例，新建MCP服务器。![img.png](cherry-studio/img.png)
3. "名称"和描述可以随便填。
4. 类型根据自己需要选择。以下以sse为例
6. 在请求头添加上鉴权参数：![img_2.png](cherry-studio/img_2.png)。注意此处需要将":"改为"="填入，比如Authorization=Bearer 123
7. 点击右上角的启用按钮和保存按钮。![img_3.png](cherry-studio/img_3.png)
8. 来到对话界面，选择要使用的MCP工具。![img_4.png](cherry-studio/img_4.png)
9. 选择合适的模型，与AI对话，比如"我现在在杭州云谷，请给我推荐开车半小时以内的餐馆",即可让AI调用模型帮你找到合适的餐馆。


## Dify 使用示例
1. 来到计算巢实例界面，![img_7.png](img-deploy/img_7.png),点击MCP 控制台
2. 打开您的Dify，按照下图示例，安装"SSE发现和调用MCP工具"![img.png](dify/img.png)
3. 如果后续使用出现问题，可将此工具版本降低到0.0.10。![img_1.png](dify/img_1.png)
4. 点击"授权"按钮对SSE工具进行配置。此处可直接粘贴步骤一中的MCP Server访问地址![img_2.png](dify/img_2.png)
5. 创建个Agent，并进入。![img_3.png](dify/img_3.png)
6. 按照下图示例，开启MCP工具调用，填写合适的提示词，选择合适的模型，比如QWEN-max。![img_4.png](dify/img_4.png)
7. 对话，即可调用MCP工具。![img_5.png](dify/img_5.png)

## 百炼使用示例
1. 来到计算巢实例界面，![img_7.png](img-deploy/img_7.png),点击MCP 控制台
2. 打开您的[百炼控制台](https://bailian.console.aliyun.com/?tab=mcp#/mcp-market)，进入到MCP界面![img_1.png](bailian/img_1.png)
3. 选择SSE的安装方式，填写合适的服务名称和描述![img.png](bailian/img_6.png)
4. 选择要使用的MCP工具，将其配置粘贴到"MCP服务配置"中，示例如下。![img_2.png](bailian/img_2.png)
```json
{"mcpServers":{"amap-maps":{"type":"sse","url":"http://47.xxx:8080/amap-maps/sse","headers":{"Authorization":"Bearer rBrrSh7ZhA"}}}}
```
5. 注意，此处如果在计算巢选择安装了多个工具，需要在控制台每个工具配置一次MCP服务。
6. 在百炼"应用"界面，点击"应用管理"，点击"新增应用"![img_3.png](bailian/img_3.png)，选择"智能体应用"，并点击创建
7. 按照图示顺序添加要使用的MCP工具。![img_4.png](bailian/img_4.png)
8. 选择合适的模型，即可在对话中使用MCP功能。![img_5.png](bailian/img_5.png)![img.png](bailian/img.png)

## Open WebUI使用示例

1. 来到计算巢实例界面，![img_7.png](img-deploy/img_7.png),点击MCP 控制台
2. 打开您的Open WebUI客户端，如Open WebUI，并将地址和API秘钥粘贴进去。![img_8.png](img-deploy/img_8.png)
3. 新建个对话，并开启MCP工具![img_9.png](img-deploy/img_9.png)
4. 验证一下AI使用您的MCP工具！ ![img_10.png](img-deploy/img_10.png)

## Cline使用示例
1. 来到计算巢实例界面，![img_7.png](img-deploy/img_7.png),点击MCP 控制台
2. 进入控制台，将配置复制好。![img_5.png](cline/img_5.png)
3. 打开Cline，按照图示位置打开MCP的配置，将第二部的配置信息粘贴。![img_6.png](cline/img_6.png)
4. 调用MCP工具。![img_7.png](cline/img_7.png)

## 问题排查

如果发现实例一直未部署成功，90%的概率是环境变量配置错误，可参考以下步骤排查：
1. 通过会话管理登录到ECS实例。![img_6.png](error/img.png)
2. 输入以下指令确认环境变量是否正确。
```shell
cat /root/config.json
```
4. 对配置进行修改。重启docker compose应用
```shell
sudo systemctl restart quickstart-mcp
```

## 企业用户推荐的ECS实例配置
1. 推荐的ECS实例类型：请选择cpu核数和内存大于ecs.u1-c1m2.xlarge已上的类型
2. 公网带宽：请选择大于8MPS的带宽。（某些MCP工具涉及到联网调用）
3. 对于4核8G的U实例类型，单次部署请选择10个以内的MCP工具

请访问MCP官方了解如何使用：[使用文档](https://github.com/open-webui/mcpo)



