# Demo服务实例部署文档

## 概述

MCP（Model Context Protocol，模型上下文协议） ，2024年11月底，由 Anthropic 推出的一种开放标准，旨在统一大型语言模型（LLM）与外部数据源和工具之间的通信协议。MCP 的主要目的在于解决当前 AI 模型因数据孤岛限制而无法充分发挥潜力的难题，MCP 使得 AI 应用能够安全地访问和操作本地及远程数据，为 AI 应用提供了连接万物的接口。
本文向您介绍如何开通计算巢上的`MCP Server社区版`服务，以及部署流程和使用说明。
## 前提条件
<font style="color:rgb(51, 51, 51);">部署Dify社区版服务实例，需要对部分阿里云资源进行访问和创建操作。因此您的账号需要包含如下资源的权限。</font><font style="color:rgb(51, 51, 51);"> </font>**<font style="color:rgb(51, 51, 51);">说明</font>**<font style="color:rgb(51, 51, 51);">：当您的账号是RAM账号时，才需要添加此权限。</font>

| <font style="color:rgb(51, 51, 51);">权限策略名称</font> | <font style="color:rgb(51, 51, 51);">备注</font> |
| --- | --- |
| <font style="color:rgb(51, 51, 51);">AliyunECSFullAccess</font> | <font style="color:rgb(51, 51, 51);">管理云服务器服务（ECS）的权限</font> |
| <font style="color:rgb(51, 51, 51);">AliyunVPCFullAccess</font> | <font style="color:rgb(51, 51, 51);">管理专有网络（VPC）的权限</font> |
| <font style="color:rgb(51, 51, 51);">AliyunROSFullAccess</font> | <font style="color:rgb(51, 51, 51);">管理资源编排服务（ROS）的权限</font> |
| <font style="color:rgb(51, 51, 51);">AliyunComputeNestUserFullAccess</font> | <font style="color:rgb(51, 51, 51);">管理计算巢服务（ComputeNest）的用户侧权限</font> |


MCP Server社区版在计算巢上的费用主要涉及：

- 所选vCPU与内存规格
- 系统盘类型及容量
- 公网带宽

为了提高MCP工具调用的性能，我们推荐至少选择2核，4G以上的CPU。
且默认帮您配置的网络带宽为10Mbps,按流量计费。

计费方式包括：

- 按量付费（小时）
- 包年包月


预估费用在创建实例时可实时看到。
如需更多规格、其他服务（如集群高可用性要求、企业级支持服务等），请联系我们 [mailto:xx@xx.com](mailto:xx@xx.com)。


## 部署架构
![](./img/deploy.png)

## 部署流程


### 部署参数说明

### 部署步骤

1. 单击[部署链接]("https://computenest.console.aliyun.com/service/instance/create/cn-hangzhou?type=user&ServiceName=MCP Server社区版")，进入服务实例部署界面，根据界面提示，填写参数完成部署。
2. 选择你想使用的MCP工具。注意，可以多选哦！
3. 如果选择的MCP工具需要设置，请务必按照说明配置上正确的参数。
4. 如果无设置按钮，则可以跳过参数配置步骤。
5. 系统默认帮你生成了一个API KEY，用于保护你即将部署的MCP工具，你可以对此进行修改。
6. 配置你的ECS实例规格，建议选择2核4G的规格以上。
7. 配置你的ECS登录密码
8. 等待部署成功，该过程一般耗时3分钟。该时长根据您选择的工具的多少有所波动。
9. 访问刚部署成功的实例界面，可查看到您部署的专属MCP工具的地址和API秘钥。
10. 打开您的AI助手客户端，如Open WebUI，并将地址和API秘钥粘贴进去。
11. 验证一下AI使用您的MCP工具



### 使用Demo
加下来以高德地图MCP为例，我们开一个完整的使用Demo


请访问MCP官方了解如何使用：[使用文档](https://github.com/open-webui/mcpo)



