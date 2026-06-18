#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import subprocess
import logging
import hashlib
import argparse
import sys
import time
import requests
import base64
import yaml
import tempfile

# 全局日志，与 fc-mcp.py 保持一致
logger = logging.getLogger()


class MCPGatewayState:
    """MCP网关状态管理"""

    def __init__(self, state_file=None):
        self.state_file = state_file or os.path.expanduser('~/.mcp_gateway_state.json')
        self.state = self._load_state()

    def _load_state(self):
        """加载状态文件"""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_state(self):
        """保存状态文件"""
        os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
        with open(self.state_file, 'w', encoding='utf-8') as f:
            json.dump(self.state, f, indent=2, ensure_ascii=False)

    def update_gateway_info(self, gateway_id, domain_id, service_id, service_name):
        """更新网关基础信息"""
        self.state.update({
            "gateway_id": gateway_id,
            "domain_id": domain_id,
            "service_id": service_id,
            "service_name": service_name,
            "last_updated": time.strftime('%Y-%m-%dT%H:%M:%S')
        })
        if "tools" not in self.state:
            self.state["tools"] = {}
        self._save_state()

    def add_tool(self, tool_name, mcp_server_id):
        """添加工具记录"""
        if "tools" not in self.state:
            self.state["tools"] = {}

        self.state["tools"][tool_name] = {
            "mcp_server_id": mcp_server_id,
            "created_at": time.strftime('%Y-%m-%dT%H:%M:%S')
        }
        self.state["last_updated"] = time.strftime('%Y-%m-%dT%H:%M:%S')
        self._save_state()

    def remove_tool(self, tool_name):
        """移除工具记录"""
        if "tools" in self.state and tool_name in self.state["tools"]:
            del self.state["tools"][tool_name]
            self.state["last_updated"] = time.strftime('%Y-%m-%dT%H:%M:%S')
            self._save_state()

    def get_all_tools(self):
        """返回所有工具 dict"""
        return self.state.get("tools", {})

    def clear_all_state(self):
        """清空所有状态"""
        self.state = {}
        self._save_state()

    def get_gateway_info(self):
        """返回网关信息"""
        return {
            "gateway_id": self.state.get("gateway_id"),
            "domain_id": self.state.get("domain_id"),
            "service_id": self.state.get("service_id"),
            "service_name": self.state.get("service_name")
        }

    def has_state(self):
        """检查是否有状态记录"""
        return bool(self.state.get("gateway_id"))


class MCPGatewayRegistrar:
    """MCP工具自动注册到阿里云AI网关的工具类（使用高级MCP Server API）"""

    def __init__(self, region='cn-hangzhou', log_level='INFO', debug_response=False, state_file=None):
        self.region = region
        self.debug_response = debug_response
        self.state = MCPGatewayState(state_file)
        logging.basicConfig(level=getattr(logging, log_level.upper(), logging.INFO))

    def _execute_aliyun_cli(self, method, endpoint, body=None, **params):
        """统一的阿里云CLI命令执行"""
        command = ["./aliyun", "apig", method, endpoint, "--endpoint", f"apig.{self.region}.aliyuncs.com"]
        # 添加参数
        for key, value in params.items():
            if value is not None:
                command.extend([f"--{key}", str(value)])

        # 添加请求体
        if body is not None:
            command.extend(["--body", json.dumps(body)])

        command.extend(["--header", "Content-Type=application/json;"])
        try:
            logger.info(f"执行CLI: {command} {method} {endpoint}")
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                check=True
            )

            response = json.loads(result.stdout) if result.stdout else {}

            if self.debug_response:
                print(f"\n=== {method} {endpoint} 响应 ===")
                print(json.dumps(response, indent=2, ensure_ascii=False))
                print("=== 响应结束 ===\n")

            return response

        except subprocess.CalledProcessError as e:
            error_msg = f"{method} {endpoint} 失败: {e.stderr}"
            logger.error(error_msg)
            if self.debug_response:
                print(f"\n=== 错误详情 ===\n{error_msg}\n=== 错误结束 ===\n")
            raise RuntimeError(error_msg)
        except json.JSONDecodeError as e:
            error_msg = f"解析{method} {endpoint}响应失败: {str(e)}"
            logger.error(error_msg)
            if self.debug_response:
                print(f"\n=== JSON解析错误 ===\n{error_msg}\n原始输出: {result.stdout}\n=== 错误结束 ===\n")
            raise RuntimeError(error_msg)

    def _check_response(self, response, operation):
        """检查响应状态（CLI返回双层嵌套：response.data.data）"""
        # 外层检查
        outer_code = response.get('code')
        if outer_code not in ['Ok', '200']:
            raise RuntimeError(f'{operation}失败: {response}')

        inner = response.get('data', {})

        # 如果内层也是 {code, data} 结构（CLI双层嵌套），再解一层
        if isinstance(inner, dict) and 'code' in inner and 'data' in inner:
            inner_code = inner.get('code')
            if inner_code not in ['Ok', '200']:
                raise RuntimeError(f'{operation}失败: {inner}')
            return inner.get('data', {})

        return inner

    # ===== 保留的辅助方法 =====

    def _load_pre_mcp_tools_config(self, pre_config_path='/root/pre-mcp-tools.json'):
        """加载预定义的MCP工具配置"""
        try:
            if os.path.exists(pre_config_path):
                with open(pre_config_path, 'r', encoding='utf-8') as f:
                    pre_tools = json.load(f)

                # 转换为以ServerCode为key的字典
                pre_tools_dict = {}
                for tool in pre_tools:
                    server_code = tool.get("ServerCode")
                    if server_code:
                        pre_tools_dict[server_code] = tool

                logger.info(f"加载预定义工具配置: {len(pre_tools_dict)} 个工具")
                return pre_tools_dict
            else:
                logger.warning(f"预定义工具配置文件不存在: {pre_config_path}")
                return {}
        except Exception as e:
            logger.warning(f"加载预定义工具配置失败: {e}")
            return {}

    def _generate_tool_description(self, tool_name, tools_config_path, pre_config_path='/root/pre-mcp-tools.json'):
        """生成工具描述信息（重命名自 _generate_route_description）"""
        try:
            # 加载主配置文件
            with open(tools_config_path, 'r', encoding='utf-8') as f:
                main_config = json.load(f)

            # 加载预定义配置
            pre_tools_config = self._load_pre_mcp_tools_config(pre_config_path)

            # 查找当前工具的配置
            tool_config = None
            mcp_servers = main_config.get("mcpServers", [])
            if isinstance(mcp_servers, list):
                # 新格式：mcpServers是数组
                for server in mcp_servers:
                    if server.get("serverCode") == tool_name:
                        tool_config = server
                        break
            else:
                # 旧格式：mcpServers是对象
                tool_config = mcp_servers.get(tool_name, {})

            if not tool_config:
                logger.warning(f"未找到工具 {tool_name} 的配置")
                return tool_name

            # 查找预定义配置
            pre_config = pre_tools_config.get(tool_name, {})

            # 构建描述JSON
            description_json = {}

            # 添加 name 字段
            name_info = pre_config.get("ServiceName", {})
            if isinstance(name_info, dict):
                description_json["Name"] = name_info.get("zh-cn", name_info.get("en", tool_name))
            elif name_info:
                description_json["Name"] = str(name_info)
            else:
                # 如果预定义配置中没有ServiceName，使用工具名称
                description_json["Name"] = tool_name

            # 获取描述信息（优先中文）
            description_info = pre_config.get("Description", {})
            if isinstance(description_info, dict):
                full_description = description_info.get("zh-cn", description_info.get("en", tool_name))
            else:
                full_description = str(description_info) if description_info else tool_name

            # 截取前60个字符并添加省略号
            if len(full_description) > 60:
                description_json["Description"] = full_description[:60] + "..."
            else:
                description_json["Description"] = full_description

            # 获取图标
            icon = tool_config.get("icon") or pre_config.get("Icon")
            if icon:
                description_json["Icon"] = icon

            # 转换为JSON字符串
            return json.dumps(description_json, ensure_ascii=False, separators=(',', ':'))

        except Exception as e:
            logger.warning(f"生成工具 {tool_name} 描述失败: {e}")
            return tool_name

    def _validate_mcp_service_tools(self, openapi_base_url, tool_name):
        """验证MCP服务中的工具是否可用"""
        try:
            # 检查OpenAPI规范是否可访问
            spec_url = f"{openapi_base_url}/{tool_name}/openapi.json"
            logger.info(f"验证工具 {tool_name} 的OpenAPI规范: {spec_url}")

            response = requests.get(spec_url, timeout=10)
            if response.status_code != 200:
                logger.error(f"工具 {tool_name} 的OpenAPI规范不可访问: {response.status_code}")
                return False

            spec = response.json()

            # 检查规范是否包含必要的路径
            paths = spec.get("paths", {})
            if not paths:
                logger.error(f"工具 {tool_name} 的OpenAPI规范中没有定义任何路径")
                return False

            logger.info(f"✅ 工具 {tool_name} 验证通过，包含 {len(paths)} 个API路径")
            return True

        except requests.exceptions.Timeout:
            logger.error(f"验证工具 {tool_name} 超时")
            return False
        except Exception as e:
            logger.error(f"验证工具 {tool_name} 失败: {e}")
            return False

    def extract_tools_from_config(self, config_path):
        """从配置文件提取工具名称列表"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)

            # 适应新的配置格式
            mcp_servers = config.get('mcpServers', [])
            if isinstance(mcp_servers, list):
                # 新格式：mcpServers是数组
                tools = [server.get('serverCode') for server in mcp_servers
                         if server.get('serverCode')]
            else:
                # 旧格式：mcpServers是对象
                tools = list(mcp_servers.keys())

            logger.info(f"找到 {len(tools)} 个工具: {', '.join(tools)}")
            return tools
        except Exception as e:
            raise RuntimeError(f"解析配置文件失败: {e}")

    # ===== 新的 MCP Server API 方法（CLI调用，对标 fc-mcp.py 的 SDK 调用）=====

    def get_environment_id(self, gateway_id):
        """获取环境ID"""
        response = self._execute_aliyun_cli('GET', '/v1/environments', gatewayId=gateway_id, gatewayType='AI')
        data = self._check_response(response, '获取环境列表')
        items = data.get('items', [])
        if not items:
            raise RuntimeError('未找到任何环境')
        env = next((item for item in items if item.get('default')), items[0])
        return env.get('environmentId')

    def ensure_domain(self, gateway_id, domain_id=None):
        """确保域名存在，支持传入指定域名ID或自动创建通配符域名"""
        # 如果指定了域名ID，直接验证可用性
        if domain_id:
            try:
                logger.info(f"检查指定域名ID: {domain_id}")
                response = self._execute_aliyun_cli("GET", f"/v1/domains/{domain_id}")
                data = self._check_response(response, "验证域名可用性")
                domain_name = data.get('name', 'Unknown')
                logger.info(f"✅ 域名ID {domain_id} 可用，域名: {domain_name}")
                return domain_id
            except Exception as e:
                raise RuntimeError(f"❌ 指定的域名ID {domain_id} 不可用或无效: {e}")

        # 如果没有指定域名ID，查找或创建通配符域名
        logger.info("未指定域名ID，查找或创建通配符域名")

        # 先查询现有通配符域名
        try:
            response = self._execute_aliyun_cli("GET", "/v1/domains",
                                                gatewayType="AI",
                                                nameLike="*",
                                                pageSize="10",
                                                pageNumber="1")
            data = self._check_response(response, "查询通配符域名")

            # 查找通配符域名
            for domain in data.get("items", []):
                if domain.get("name") == "*":
                    found_domain_id = domain.get("domainId")
                    logger.info(f"✅ 找到现有通配符域名，ID: {found_domain_id}")
                    return found_domain_id
        except Exception as e:
            logger.warning(f"查询通配符域名失败: {e}")

        # 如果没找到通配符域名，创建新的
        logger.info("🔨 创建新的通配符域名")
        try:
            response = self._execute_aliyun_cli("POST", "/v1/domains",
                                                {"name": "*", "protocol": "HTTP", "gatewayType": "AI"})
            data = self._check_response(response, "创建通配符域名")
            new_domain_id = data.get("domainId")
            logger.info(f"✅ 通配符域名创建成功，ID: {new_domain_id}")
            return new_domain_id
        except RuntimeError as e:
            # 如果创建失败且是因为域名已存在，重新查询
            if "Conflict.DomainExisted" in str(e) or "域名*已存在" in str(e):
                logger.warning("⚠️  通配符域名已存在，重新查询")
                try:
                    response = self._execute_aliyun_cli("GET", "/v1/domains",
                                                        gatewayId=gateway_id,
                                                        gatewayType="AI",
                                                        nameLike="*",
                                                        pageSize="10",
                                                        pageNumber="1")
                    data = self._check_response(response, "重新查询通配符域名")

                    for domain in data.get("items", []):
                        if domain.get("name") == "*":
                            existing_domain_id = domain.get("domainId")
                            logger.info(f"✅ 重新查询找到通配符域名，ID: {existing_domain_id}")
                            return existing_domain_id

                    raise RuntimeError("通配符域名已存在但无法查询到对应的域名ID")
                except Exception as query_e:
                    raise RuntimeError(f"通配符域名已存在但重新查询失败: {query_e}")
            else:
                raise RuntimeError(f"创建通配符域名失败: {e}")

    def ensure_service(self, gateway_id, private_ip, service_name):
        """确保VIP类型服务存在（原名 ensure_shared_service，改名更简洁）"""
        logger.info(f"确保共享MCP服务存在: {service_name}")

        # 检查现有服务
        try:
            response = self._execute_aliyun_cli("GET", "/v1/services",
                                                gatewayId=gateway_id,
                                                gatewayType="AI",
                                                name=service_name)
            data = self._check_response(response, "查询Service")
            existing_services = data.get("items", [])
        except Exception:
            existing_services = []

        if existing_services:
            service_id = existing_services[0].get("serviceId")
            logger.info(f"✅ 共享MCP服务已存在，名称: {service_name}, ID: {service_id}")
            return service_id

        # 创建新的共享服务
        logger.info(f"🔨 创建共享MCP服务: {service_name}")
        body = {
            "gatewayId": gateway_id,
            "sourceType": "VIP",
            "serviceConfigs": [{"name": service_name, "addresses": [f"{private_ip}:80"]}]
        }
        response = self._execute_aliyun_cli("POST", "/v1/services", body)
        data = self._check_response(response, "创建共享MCP服务")

        service_ids = data.get("serviceIds", [])
        if not service_ids:
            raise RuntimeError("创建共享MCP服务成功但未返回服务ID")

        service_id = service_ids[0]
        logger.info(f"✅ 共享MCP服务创建成功，名称: {service_name}, ID: {service_id}")
        return service_id

    def create_mcp_server(self, gateway_id, name, domain_ids, service_id, description=''):
        """创建MCP Server（对标fc-mcp.py的create_mcp_servers）"""
        # 调用 POST /v1/mcp-servers
        body = {
            'gatewayId': gateway_id,
            'name': name.lower(),  # MCP Server名称要求全小写
            'description': description,
            'type': 'RealMCP',
            'domainIds': domain_ids if isinstance(domain_ids, list) else [domain_ids],
            'backendConfig': {
                'scene': 'SingleService',
                'services': [{'serviceId': service_id}]
            },
            'match': {
                'path': {
                    'type': 'Prefix',
                    'value': f'/mcp-servers/{name.lower()}'
                }
            },
            'protocol': 'StreamableHTTP',
            'exposedUriPath': f'/mcp-servers/{name.lower()}'
        }
        try:
            response = self._execute_aliyun_cli('POST', '/v1/mcp-servers', body)
            data = self._check_response(response, '创建MCP Server')
            mcp_server_id = data.get('mcpServerId')
            logger.info(f'✅ 创建MCP Server成功: {name} -> {mcp_server_id}')
            return mcp_server_id
        except RuntimeError as e:
            error_str = str(e)
            if 'Conflict' in error_str or '已存在' in error_str or 'Duplicated' in error_str or '409' in error_str:
                logger.warning(f'⚠️ MCP Server已存在，跳过: {name}')
                return None  # 返回None表示已存在
            raise

    def deploy_mcp_server(self, mcp_server_id):
        """部署MCP Server（对标fc-mcp.py的deploy_mcp_servers）"""
        try:
            response = self._execute_aliyun_cli('POST', f'/v1/mcp-servers/{mcp_server_id}/deploy', body={})
            self._check_response(response, '部署MCP Server')
            logger.info(f'✅ MCP Server部署成功: {mcp_server_id}')

            # 与fc-mcp.py一致：第一次部署后等10秒再部署一次
            logger.info('⏰ 等待10秒后进行第二次部署...')
            time.sleep(10)
            response2 = self._execute_aliyun_cli('POST', f'/v1/mcp-servers/{mcp_server_id}/deploy', body={})
            try:
                self._check_response(response2, '第二次部署MCP Server')
                logger.info(f'✅ 第二次部署成功: {mcp_server_id}')
            except Exception:
                logger.warning(f'⚠️ 第二次部署返回非Ok状态，但不影响')

            return True
        except Exception as e:
            if '已部署' in str(e) or 'deployed' in str(e).lower():
                logger.warning(f'⚠️ MCP Server已部署: {mcp_server_id}')
                return True
            logger.error(f'❌ 部署MCP Server失败: {mcp_server_id}, {e}')
            return False

    def list_mcp_servers(self, gateway_id):
        """列出所有MCP Server"""
        try:
            response = self._execute_aliyun_cli('GET', '/v1/mcp-servers',
                                                gatewayId=gateway_id, gatewayType='AI',
                                                pageSize='100', pageNumber='1')
            data = self._check_response(response, '列出MCP Server')
            return data.get('items', [])
        except Exception as e:
            logger.warning(f'列出MCP Server失败: {e}')
            return []

    def get_mcp_server(self, mcp_server_id):
        """获取MCP Server详情"""
        response = self._execute_aliyun_cli('GET', f'/v1/mcp-servers/{mcp_server_id}')
        return self._check_response(response, '获取MCP Server详情')

    def delete_mcp_server(self, mcp_server_id):
        """删除MCP Server"""
        try:
            response = self._execute_aliyun_cli('DELETE', f'/v1/mcp-servers/{mcp_server_id}')
            self._check_response(response, '删除MCP Server')
            logger.info(f'✅ MCP Server删除成功: {mcp_server_id}')
            return True
        except Exception as e:
            logger.error(f'❌ 删除MCP Server失败: {mcp_server_id}, {e}')
            return False

    def delete_service(self, gateway_id, service_id):
        """删除Service"""
        try:
            response = self._execute_aliyun_cli('DELETE', f'/v1/services/{service_id}')
            self._check_response(response, '删除Service')
            logger.info(f'✅ Service删除成功: {service_id}')
            return True
        except Exception as e:
            logger.error(f'❌ 删除Service失败: {service_id}, {e}')
            return False

    def _find_service_by_name(self, gateway_id, name):
        """按名称查找Service"""
        try:
            response = self._execute_aliyun_cli('GET', '/v1/services', gatewayId=gateway_id, gatewayType='AI', name=name)
            data = self._check_response(response, '查询Service')
            items = data.get('items', [])
            return items[0] if items else None
        except Exception:
            return None

    # ==================== 注册功能 ====================

    def register_tools(self, gateway_id: str, private_ip: str,
                       tools_config: str, service_name: str,
                       domain_id: str = None,
                       mode: str = "create",
                       pre_config_path: str = "/root/pre-mcp-tools.json",
                       service_instance_name: str = None):
        """注册MCP工具到AI网关（使用 CreateMcpServer/DeployMcpServer API，与fc-mcp.py一致）"""
        logger.info(f"开始{mode}模式的MCP工具注册，服务名称: {service_name}")

        current_tools_list = self.extract_tools_from_config(tools_config)
        success_tools, failed_tools, skipped_tools = [], [], []

        try:
            # 1. 获取基础信息
            domain_id = self.ensure_domain(gateway_id, domain_id)
            domain_ids = [domain_id]
            service_id = self.ensure_service(gateway_id, private_ip, service_name)

            # 更新状态中的网关信息
            self.state.update_gateway_info(gateway_id, domain_id, service_id, service_name)

            openapi_base_url = f"http://{private_ip}:80"

            # 2. 逐个注册工具
            for tool_name in current_tools_list:
                try:
                    # MCP Server名称直接用serverCode（与控制台匹配逻辑一致）
                    mcp_name = tool_name
                    logger.info(f"📝 处理工具: {tool_name}，MCP名称: {mcp_name}")

                    # create-skip模式：检查是否已存在
                    if mode == "create-skip":
                        existing_servers = self.list_mcp_servers(gateway_id)
                        already_exists = any(s.get("name") == mcp_name.lower() for s in existing_servers)
                        if already_exists:
                            logger.info(f"⏭️  MCP Server {mcp_name} 已存在，跳过")
                            skipped_tools.append(tool_name)
                            continue

                    # 验证工具可用性
                    if not self._validate_mcp_service_tools(openapi_base_url, tool_name):
                        logger.error(f"❌ 工具 {tool_name} 验证失败")
                        if mode == "create-skip":
                            skipped_tools.append(tool_name)
                        else:
                            failed_tools.append(tool_name)
                        continue

                    # 生成描述
                    description = self._generate_tool_description(tool_name, tools_config, pre_config_path)

                    # 创建MCP Server（对标 fc-mcp.py 的 create_mcp_servers）
                    mcp_server_id = self.create_mcp_server(
                        gateway_id, mcp_name, domain_ids, service_id, description
                    )

                    if mcp_server_id is None:
                        # 已存在，统一跳过
                        skipped_tools.append(tool_name)
                        continue

                    # 部署MCP Server（对标 fc-mcp.py 的 deploy_mcp_servers）
                    if self.deploy_mcp_server(mcp_server_id):
                        # 更新状态
                        self.state.add_tool(tool_name, mcp_server_id)
                        success_tools.append(tool_name)
                    else:
                        failed_tools.append(tool_name)

                except Exception as e:
                    if mode == "create-skip":
                        logger.warning(f"⚠️  处理工具 {tool_name} 失败，跳过: {e}")
                        skipped_tools.append(tool_name)
                    else:
                        logger.error(f"❌ 处理工具 {tool_name} 失败: {e}")
                        failed_tools.append(tool_name)

            # 输出跳过的工具信息
            if skipped_tools:
                logger.info(f"⏭️  跳过 {len(skipped_tools)} 个已存在工具: {', '.join(skipped_tools)}")

            return len(success_tools), len(failed_tools), success_tools, failed_tools, skipped_tools

        except Exception as e:
            logger.error(f"注册工具失败: {e}")
            raise

    # ==================== 清理功能 ====================

    def cleanup_all(self, gateway_id: str, service_name: str = None):
        """清理所有MCP资源（使用 ListMcpServers + DeleteMcpServer API）"""
        logger.info("开始清理AI网关侧所有MCP资源")
        success_tools, failed_tools = [], []

        try:
            # 1. 列出所有MCP Server
            mcp_servers = self.list_mcp_servers(gateway_id)
            logger.info(f"发现 {len(mcp_servers)} 个MCP Server")

            if not mcp_servers:
                logger.info("未发现任何MCP Server")
                # 仍然清理共享服务
                if service_name:
                    self._cleanup_service(gateway_id, service_name)
                return 0, 0, [], []

            # 2. 逐个删除MCP Server
            for server in mcp_servers:
                mcp_server_id = server.get("mcpServerId")
                server_name = server.get("name", "unknown")

                if not mcp_server_id:
                    continue

                if self.delete_mcp_server(mcp_server_id):
                    success_tools.append(server_name)
                    logger.info(f"✅ MCP Server {server_name} 清理成功")
                else:
                    failed_tools.append(server_name)
                    logger.error(f"❌ MCP Server {server_name} 清理失败")

            # 3. 清理共享服务
            if service_name:
                self._cleanup_service(gateway_id, service_name)

            # 4. 清空状态
            self.state.clear_all_state()

            return len(success_tools), len(failed_tools), success_tools, failed_tools

        except Exception as e:
            logger.error(f"清理网关资源失败: {e}")
            raise

    def _cleanup_service(self, gateway_id: str, service_name: str):
        """清理指定名称的服务"""
        try:
            logger.info(f"查找并清理服务: {service_name}")
            service = self._find_service_by_name(gateway_id, service_name)
            if not service:
                logger.info(f"未找到名为 {service_name} 的服务")
                return

            service_id = service.get("serviceId")
            if self.delete_service(gateway_id, service_id):
                logger.info(f"✅ 服务 {service_name} 删除成功")
            else:
                logger.warning(f"⚠️  服务 {service_name} 删除失败")
        except Exception as e:
            logger.warning(f"清理服务 {service_name} 失败: {e}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="MCP工具自动注册和清理工具（使用MCP Server API）")

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # 注册命令
    register_parser = subparsers.add_parser("register", help="注册MCP工具到AI网关")
    register_parser.add_argument("--gateway-id", required=True, help="AI网关ID")
    register_parser.add_argument("--private-ip", required=True, help="内网IP地址")
    register_parser.add_argument("--tools-config", required=True, help="工具配置文件路径")
    register_parser.add_argument("--pre-config", default="/root/pre-mcp-tools.json",
                                 help="预定义工具配置文件路径（默认: /root/pre-mcp-tools.json）")
    register_parser.add_argument("--domain-id", help="指定域名ID（不提供则使用通配符域名）")
    register_parser.add_argument("--mode", choices=["create", "create-skip"], default="create",
                                 help="模式：create(新建) 或 create-skip(跳过已存在)")
    register_parser.add_argument("--si", required=True, help="服务名称（必须传入，格式如：si-xxxx）")
    register_parser.add_argument("--service-instance-name",
                                 help="服务实例名称，MCP名称将使用 serviceInstanceName-serverCode 格式")

    # 清理命令
    cleanup_parser = subparsers.add_parser("cleanup", help="清理AI网关侧所有MCP资源")
    cleanup_parser.add_argument("--gateway-id", required=True, help="AI网关ID")
    cleanup_parser.add_argument("--si", required=True, help="要删除的服务名称（必须传入，格式如：si-xxxx）")

    # 通用参数
    for subparser in [register_parser, cleanup_parser]:
        subparser.add_argument("--region", default="cn-hangzhou", help="阿里云区域")
        subparser.add_argument("-d", "--debug-response", action="store_true", help="打印详细响应信息")
        subparser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                               help="日志级别")
        subparser.add_argument("--state-file", help="状态文件路径（默认: ~/.mcp_gateway_state.json）")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        registrar = MCPGatewayRegistrar(args.region, args.log_level, args.debug_response, args.state_file)

        if args.command == "register":
            # 验证 --si 参数格式
            if not args.si.startswith("si-"):
                print("❌ --si 参数格式错误，必须以 'si-' 开头，例如：si-12345")
                sys.exit(1)

            success_count, failed_count, success_tools, failed_tools, skipped_tools = registrar.register_tools(
                gateway_id=args.gateway_id,
                private_ip=args.private_ip,
                tools_config=args.tools_config,
                service_name=args.si,
                domain_id=args.domain_id,
                mode=args.mode,
                pre_config_path=args.pre_config,
                service_instance_name=args.service_instance_name
            )

            # 输出结果
            print(f"\n{'=' * 50}")
            print(f"📊 MCP工具注册结果")
            print(f"{'=' * 50}")
            print(f"🏷️  服务名称: {args.si}")
            if args.service_instance_name:
                print(f"🏷️  服务实例名称: {args.service_instance_name}")
            print(f"✅ 新建成功: {success_count} 个")
            if success_tools:
                print(f"   {', '.join(success_tools)}")
            print(f"⏭️  已存在跳过: {len(skipped_tools)} 个")
            if skipped_tools:
                print(f"   {', '.join(skipped_tools)}")
            print(f"❌ 失败: {failed_count} 个")
            if failed_tools:
                print(f"   {', '.join(failed_tools)}")
            print(f"📈 总计: {success_count + len(skipped_tools) + failed_count} 个")
            print(f"{'=' * 50}")

            sys.exit(1 if failed_count > 0 else 0)

        elif args.command == "cleanup":
            success_count, failed_count, success_tools, failed_tools = registrar.cleanup_all(
                gateway_id=args.gateway_id,
                service_name=args.si
            )

            print(f"\n{'=' * 50}")
            print("🧹 MCP资源清理结果")
            print(f"{'=' * 50}")
            print(f"🏷️  服务名称: {args.si}")
            print(f"✅ 成功清理: {success_count} 个")
            if success_tools:
                print(f"   {', '.join(success_tools)}")
            print(f"❌ 清理失败: {failed_count} 个")
            if failed_tools:
                print(f"   {', '.join(failed_tools)}")
            print(f"{'=' * 50}")

            sys.exit(1 if failed_count > 0 else 0)

    except Exception as e:
        print(f"❌ 执行失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
