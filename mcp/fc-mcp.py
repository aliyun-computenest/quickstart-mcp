#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
APIG MCP服务注册脚本
用于将FC3函数批量注册到APIG并创建MCP路由
"""

import json
import logging
import base64
import time

from typing import List, Dict, Optional

from alibabacloud_apig20240327.client import Client as APIG20240327Client
from alibabacloud_credentials.client import Client as CredentialClient
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_apig20240327 import models as apig20240327_models
from alibabacloud_tea_util import models as util_models

# 配置日志
logger = logging.getLogger()
logger.setLevel(logging.INFO)


class APIMCPManager:
    def __init__(self, region: str = 'cn-hangzhou'):
        """初始化APIG MCP管理器"""
        self.client = self._create_client(region)
        self.runtime = util_models.RuntimeOptions()
        self.headers = {}

    def _create_client(self, region: str) -> APIG20240327Client:
        """创建APIG客户端"""
        credential = CredentialClient()
        config = open_api_models.Config(credential=credential)
        config.endpoint = f'apig.{region}.aliyuncs.com'
        return APIG20240327Client(config)

    def get_http_api_id(self, gateway_id: str) -> Optional[str]:
        """获取MCP类型的HttpApiId"""
        try:
            request = apig20240327_models.ListHttpApisRequest(
                gateway_id=gateway_id,
                gateway_type='AI',
                types='MCP'
            )

            response = self.client.list_http_apis_with_options(
                request, self.headers, self.runtime
            )

            if response.body.code == 'Ok' and response.body.data.items:
                first_item = response.body.data.items[0]
                if first_item.versioned_http_apis:
                    http_api_id = first_item.versioned_http_apis[0].http_api_id
                    logger.info(f"✓ 找到HttpApiId: {http_api_id}")
                    return http_api_id

            logger.error("❌ 未找到MCP类型的HttpApi")
            return None

        except Exception as error:
            logger.error(f"❌ 获取HttpApiId失败: {error}")
            return None

    def create_services(self, gateway_id: str, fc3_names: List[str],
                        resource_group_id: str = None) -> Dict[str, str]:
        """批量创建APIG服务，返回函数名到服务ID的映射"""
        service_mapping = {}  # 函数名 -> 服务ID的映射

        for fc3_name in fc3_names:
            try:
                logger.info(f"正在为函数 {fc3_name} 创建APIG服务...")

                service_configs = [
                    apig20240327_models.CreateServiceRequestServiceConfigs(
                        name=fc3_name,
                        qualifier="LATEST"
                    )
                ]

                request = apig20240327_models.CreateServiceRequest(
                    gateway_id=gateway_id,
                    source_type='FC3',
                    service_configs=service_configs
                )

                if resource_group_id:
                    request.resource_group_id = resource_group_id

                response = self.client.create_service_with_options(
                    request, self.headers, self.runtime
                )

                logger.info(f"APIG服务创建响应: {response.body}")

                if response.body.code == 'Ok':
                    created_service_ids = response.body.data.service_ids
                    if created_service_ids:
                        service_id = created_service_ids[0]  # 取第一个服务ID
                        service_mapping[fc3_name] = service_id
                        logger.info(f"✓ 创建APIG服务成功: {fc3_name} -> {service_id}")
                else:
                    logger.error(f"❌ 创建APIG服务失败: {fc3_name}, 错误: {getattr(response.body, 'message', '未知错误')}")

            except Exception as error:
                error_str = str(error)

                # 检查是否是服务已存在的错误
                if "Conflict.ServiceExisted" in error_str or "409" in error_str:
                    logger.warning(f"⚠️ 服务已存在，跳过创建: {fc3_name}")
                    logger.info(f"服务已存在详情: {error_str}")

                    # 尝试从错误信息中提取已存在的服务ID
                    try:
                        # 错误信息格式: "已存在名为mcp-dd26-fetch/svc-d397u4em1hks7ua617c0的服务"
                        if "/" in error_str:
                            # 提取服务ID部分
                            parts = error_str.split("/")
                            for part in parts:
                                if part.startswith("svc-"):
                                    # 找到服务ID，提取干净的ID
                                    service_id = part.split("的服务")[0].split(" ")[0]
                                    service_mapping[fc3_name] = service_id
                                    logger.info(f"✓ 使用已存在的服务: {fc3_name} -> {service_id}")
                                    break
                    except Exception as extract_error:
                        logger.warning(f"无法从错误信息中提取服务ID: {extract_error}")

                    continue  # 跳过这个服务，继续处理下一个
                else:
                    # 其他类型的错误，记录但不中断流程
                    logger.error(f"❌ 创建APIG服务异常: {fc3_name}, 错误: {error}")
                    import traceback
                    logger.error(f"详细错误: {traceback.format_exc()}")

        logger.info(f"APIG服务处理完成，共获得 {len(service_mapping)} 个服务映射: {service_mapping}")
        return service_mapping

    def create_mcp_servers(self, gateway_id: str, domain_ids: List[str],
                           service_mapping: Dict[str, str]) -> Dict[str, str]:
        """批量创建MCP服务器，返回需要部署的函数名到MCP服务器ID的映射"""
        mcp_server_mapping = {}  # 函数名 -> MCP服务器ID的映射（只包含需要部署的）

        for fc3_name, service_id in service_mapping.items():
            try:
                logger.info(f"创建MCP服务器: {fc3_name} -> {service_id}")

                # 1. 创建路径匹配配置
                http_route_match_path = apig20240327_models.HttpRouteMatchPath(
                    type='Prefix',
                    value=f'/mcp-servers/{fc3_name}'
                )
                logger.info(f"✓ 路径匹配配置创建成功")

                # 2. 创建匹配配置
                http_route_match = apig20240327_models.HttpRouteMatch(
                    path=http_route_match_path
                )
                logger.info("✓ 匹配配置创建成功")

                # 3. 使用已知存在的HTTP路由后端配置类
                backend_config_service = apig20240327_models.CreateHttpApiRouteRequestBackendConfigServices(
                    service_id=service_id
                )
                logger.info(f"✓ 后端服务配置创建成功: {service_id}")

                # 4. 使用已知存在的HTTP路由后端配置类
                backend_config = apig20240327_models.CreateHttpApiRouteRequestBackendConfig(
                    scene='SingleService',
                    services=[backend_config_service]
                )
                logger.info("✓ 后端配置创建成功")

                # 5. 创建MCP服务器请求
                create_mcp_server_request = apig20240327_models.CreateMcpServerRequest(
                    gateway_id=gateway_id,
                    name=fc3_name,
                    type='RealMCP',
                    domain_ids=domain_ids,
                    backend_config=backend_config,
                    match=http_route_match,
                    protocol='SSE',
                    exposed_uri_path='/sse'
                )
                logger.info("✓ MCP服务器请求创建成功")

                # 6. 发送请求
                response = self.client.create_mcp_server_with_options(
                    create_mcp_server_request, self.headers, self.runtime
                )

                logger.info(f"MCP服务器创建响应: {response.body}")

                if response.body.code == 'Ok':
                    mcp_server_id = response.body.data.mcp_server_id
                    mcp_server_mapping[fc3_name] = mcp_server_id
                    logger.info(f"✓ 创建MCP服务器成功: {fc3_name} -> {mcp_server_id}")
                else:
                    logger.error(f"❌ 创建MCP服务器失败: {fc3_name}, 错误: {getattr(response.body, 'message', '未知错误')}")

            except Exception as error:
                error_str = str(error)

                # 检查是否是MCP服务器已存在的错误
                if "Conflict.McpServerNameAlreadyExists" in error_str or ("409" in error_str and "已存在" in error_str):
                    logger.warning(f"⚠️ MCP服务器已存在，视为成功，跳过后续部署: {fc3_name}")
                    logger.info(f"MCP服务器已存在详情: {error_str}")
                    # 不添加到mcp_server_mapping中，这样就不会进入部署流程
                    continue
                else:
                    # 其他类型的错误，记录但不中断流程
                    logger.error(f"❌ 创建MCP服务器异常: {fc3_name}, 错误: {error}")
                    import traceback
                    logger.error(f"详细错误: {traceback.format_exc()}")

        logger.info(f"MCP服务器处理完成，共获得 {len(mcp_server_mapping)} 个需要部署的服务器: {mcp_server_mapping}")
        return mcp_server_mapping

    def deploy_mcp_servers(self, mcp_server_mapping: Dict[str, str]) -> Dict[str, str]:
        """批量部署MCP服务器，返回成功部署的映射"""
        deployed_mapping = {}  # 函数名 -> MCP服务器ID的映射

        for fc3_name, mcp_server_id in mcp_server_mapping.items():
            try:
                logger.info(f"部署MCP服务器: {fc3_name} -> {mcp_server_id}")

                response = self.client.deploy_mcp_server_with_options(
                    mcp_server_id, self.headers, self.runtime
                )

                logger.info(f"MCP服务器部署响应: {response.body}")

                if response.body.code == 'Ok':
                    deployed_mapping[fc3_name] = mcp_server_id
                    logger.info(f"✓ 部署MCP服务器成功: {fc3_name} -> {mcp_server_id}")

                    # 第一次部署成功后，等待10秒再部署一次
                    logger.info(f"⏰ 等待10秒后进行第二次部署...")
                    time.sleep(10)

                    logger.info(f"🔄 开始第二次部署: {fc3_name} -> {mcp_server_id}")
                    response2 = self.client.deploy_mcp_server_with_options(
                        mcp_server_id, self.headers, self.runtime
                    )
                    logger.info(f"第二次部署响应: {response2.body}")

                    if response2.body.code == 'Ok':
                        logger.info(f"✓ 第二次部署成功: {fc3_name} -> {mcp_server_id}")
                    else:
                        logger.warning(f"⚠️ 第二次部署返回非Ok状态: {getattr(response2.body, 'message', '未知错误')}")

                else:
                    logger.error(f"❌ 部署MCP服务器失败: {fc3_name} -> {mcp_server_id}, 错误: {getattr(response.body, 'message', '未知错误')}")

            except Exception as error:
                error_str = str(error)

                # 检查是否是已部署的错误
                if "已部署" in error_str or "deployed" in error_str.lower():
                    logger.warning(f"⚠️ MCP服务器已部署，跳过: {fc3_name} -> {mcp_server_id}")
                    deployed_mapping[fc3_name] = mcp_server_id  # 标记为已部署
                    continue
                else:
                    logger.error(f"❌ 部署MCP服务器异常: {fc3_name} -> {mcp_server_id}, 错误: {error}")
                    import traceback
                    logger.error(f"详细错误: {traceback.format_exc()}")

        logger.info(f"MCP服务器部署完成，共部署 {len(deployed_mapping)} 个服务器: {deployed_mapping}")
        return deployed_mapping

    def register_mcp_services(self, gateway_id: str, environment_id: str,
                              domain_ids: List[str], fc3_names: List[str],
                              resource_group_id: str = None) -> Dict[str, any]:
        """完整的MCP服务注册流程"""
        logger.info(f"🚀 开始注册MCP服务...")
        logger.info(f"   网关ID: {gateway_id}")
        logger.info(f"   环境ID: {environment_id}")
        logger.info(f"   域名IDs: {domain_ids}")
        logger.info(f"   FC3函数: {fc3_names}")

        result = {
            'success': False,
            'http_api_id': None,
            'service_mapping': {},
            'mcp_server_mapping': {},
            'deployed_mapping': {},
            'skipped_existing': [],  # 新增：跳过的已存在MCP服务器
            'errors': []
        }

        # 1. 获取HttpApiId（可能不需要，但保留用于验证）
        logger.info("📡 步骤1: 获取HttpApiId...")
        http_api_id = self.get_http_api_id(gateway_id)
        if http_api_id:
            result['http_api_id'] = http_api_id
            logger.info(f"✓ HttpApiId: {http_api_id}")
        else:
            logger.warning("⚠️ 未找到HttpApiId，但继续执行MCP服务创建")

        # 2. 创建APIG服务
        logger.info("🔧 步骤2: 创建APIG服务...")
        service_mapping = self.create_services(gateway_id, fc3_names, resource_group_id)
        if not service_mapping:
            result['errors'].append("未能创建任何APIG服务")
            return result
        result['service_mapping'] = service_mapping

        # 3. 创建MCP服务器
        logger.info("🖥️  步骤3: 创建MCP服务器...")
        mcp_server_mapping = self.create_mcp_servers(gateway_id, domain_ids, service_mapping)
        result['mcp_server_mapping'] = mcp_server_mapping

        # 计算跳过的已存在服务器
        skipped_existing = []
        for fc3_name in service_mapping.keys():
            if fc3_name not in mcp_server_mapping:
                skipped_existing.append(fc3_name)
        result['skipped_existing'] = skipped_existing

        if skipped_existing:
            logger.info(f"⚠️ 跳过已存在的MCP服务器: {skipped_existing}")

        # 4. 部署MCP服务器（只部署新创建的）
        if mcp_server_mapping:
            logger.info("🚀 步骤4: 部署MCP服务器...")
            deployed_mapping = self.deploy_mcp_servers(mcp_server_mapping)
            result['deployed_mapping'] = deployed_mapping
        else:
            logger.info("⚠️ 没有需要部署的MCP服务器，跳过部署步骤")
            result['deployed_mapping'] = {}

        # 检查结果
        total_processed = len(result['deployed_mapping']) + len(result['skipped_existing'])
        if total_processed == len(fc3_names):
            result['success'] = True
            logger.info("✅ 所有MCP服务处理成功!")
            logger.info(f"   新部署: {len(result['deployed_mapping'])} 个")
            logger.info(f"   已存在: {len(result['skipped_existing'])} 个")
        else:
            result['errors'].append(f"部分MCP服务处理失败: {total_processed}/{len(fc3_names)}")
            logger.warning(f"⚠️  部分MCP服务处理成功: {total_processed}/{len(fc3_names)}")

        return result


def handler(event, context):
    """FC3函数入口点"""
    logger.info("receive event: %s", event)
    logger.info("event type: %s", type(event))

    try:
        # 处理不同类型的事件参数
        if isinstance(event, bytes):
            # bytes类型，先解码为字符串
            logger.info("🔧 检测到bytes类型事件，进行解码")
            event_str = event.decode('utf-8')
            event_data = json.loads(event_str)

        elif isinstance(event, str):
            try:
                # 尝试解析为HTTP触发器事件
                event_json = json.loads(event)

                # 检查是否是HTTP触发器调用
                if "body" in event_json:
                    logger.info("📡 检测到HTTP触发器调用")
                    req_body = event_json['body']
                    if 'isBase64Encoded' in event_json and event_json['isBase64Encoded']:
                        req_body = base64.b64decode(event_json['body']).decode("utf-8")

                    # 解析请求体中的参数
                    event_data = json.loads(req_body)

                    # 执行注册逻辑
                    result = execute_registration(event_data)

                    # 返回HTTP响应格式
                    return {
                        'statusCode': 200,
                        'headers': {'Content-Type': 'application/json'},
                        'isBase64Encoded': False,
                        'body': json.dumps(result, ensure_ascii=False)
                    }
                else:
                    # 直接是参数JSON字符串（FunctionInvoker调用）
                    logger.info("🔧 检测到FunctionInvoker调用（JSON字符串）")
                    event_data = event_json

            except json.JSONDecodeError:
                # 不是JSON格式，可能是其他类型的调用
                logger.error(f"❌ 无法解析事件JSON: {event}")
                return {
                    'success': False,
                    'error': f'无法解析事件JSON: {event}'
                }

        elif isinstance(event, dict):
            # 直接是字典（FunctionInvoker调用）
            logger.info("🔧 检测到FunctionInvoker调用（字典）")
            event_data = event

        else:
            # 其他类型
            logger.error(f"❌ 不支持的事件类型: {type(event)}")
            return {
                'success': False,
                'error': f'不支持的事件类型: {type(event)}'
            }

        # 执行注册逻辑
        result = execute_registration(event_data)
        return result

    except Exception as e:
        error_msg = f"函数执行失败: {str(e)}"
        logger.error(error_msg)
        import traceback
        logger.error(f"错误堆栈: {traceback.format_exc()}")

        return {
            'success': False,
            'error': error_msg,
            'traceback': traceback.format_exc()
        }


def execute_registration(event_data: dict) -> dict:
    """执行MCP服务注册"""
    logger.info(f"📥 解析后的事件数据: {event_data}")

    # 提取参数
    gateway_id = event_data.get('gateway_id')
    environment_id = event_data.get('environment_id')
    domain_ids = event_data.get('domain_ids', [])
    fc3_names_raw = event_data.get('fc3_names', [])
    resource_group_id = event_data.get('resource_group_id')
    region = event_data.get('region', 'cn-hangzhou')

    # 处理可能的嵌套数组问题
    def flatten_array(arr):
        """扁平化数组"""
        result = []
        for item in arr:
            if isinstance(item, list):
                result.extend(flatten_array(item))
            else:
                result.append(item)
        return result

    # 扁平化函数名数组
    fc3_names = flatten_array(fc3_names_raw)

    logger.info(f"📋 参数解析结果:")
    logger.info(f"   gateway_id: {gateway_id}")
    logger.info(f"   environment_id: {environment_id}")
    logger.info(f"   domain_ids: {domain_ids}")
    logger.info(f"   fc3_names_raw: {fc3_names_raw}")
    logger.info(f"   fc3_names (扁平化后): {fc3_names}")
    logger.info(f"   resource_group_id: {resource_group_id}")
    logger.info(f"   region: {region}")

    # 参数验证
    if not all([gateway_id, domain_ids, fc3_names]):
        error_msg = '缺少必要参数: gateway_id, domain_ids, fc3_names'
        logger.error(f"❌ {error_msg}")
        return {
            'success': False,
            'error': error_msg
        }

    # 创建管理器并执行注册
    manager = APIMCPManager(region)
    result = manager.register_mcp_services(
        gateway_id=gateway_id,
        environment_id=environment_id,
        domain_ids=domain_ids,
        fc3_names=fc3_names,  # 使用扁平化后的数组
        resource_group_id=resource_group_id
    )

    logger.info(f"🎯 最终结果: {result}")
    return result
