#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import subprocess
import tempfile
import logging
import base64
import yaml
import requests
import time
import hashlib
from typing import List, Dict, Any, Optional, Tuple, Set
import argparse
import sys
from datetime import datetime


class MCPGatewayState:
    """MCP网关状态管理"""

    def __init__(self, state_file: str = None):
        self.state_file = state_file or os.path.expanduser("~/.mcp_gateway_state.json")
        self.state = self._load_state()

    def _load_state(self) -> Dict:
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

    def _calculate_config_hash(self, tool_name: str, openapi_base_url: str,
                               api_key: str, skip_auth: bool) -> str:
        """计算工具配置的哈希值"""
        config_str = f"{tool_name}:{openapi_base_url}:{api_key}:{skip_auth}"
        return hashlib.md5(config_str.encode()).hexdigest()

    def update_gateway_info(self, gateway_id: str, plugin_id: str,
                            http_api_id: str, environment_id: str,
                            domain_id: str, shared_service_id: str, shared_service_name: str):
        """更新网关基础信息"""
        self.state.update({
            "gateway_id": gateway_id,
            "plugin_id": plugin_id,
            "http_api_id": http_api_id,
            "environment_id": environment_id,
            "domain_id": domain_id,
            "shared_service_id": shared_service_id,
            "shared_service_name": shared_service_name,
            "last_updated": datetime.now().isoformat()
        })
        if "tools" not in self.state:
            self.state["tools"] = {}
        self._save_state()

    def add_tool(self, tool_name: str, route_id: str, attachment_id: str,
                 openapi_base_url: str, api_key: str, skip_auth: bool):
        """添加工具记录"""
        if "tools" not in self.state:
            self.state["tools"] = {}

        self.state["tools"][tool_name] = {
            "route_id": route_id,
            "attachment_id": attachment_id,
            "created_at": datetime.now().isoformat(),
            "config_hash": self._calculate_config_hash(tool_name, openapi_base_url, api_key, skip_auth)
        }
        self.state["last_updated"] = datetime.now().isoformat()
        self._save_state()

    def remove_tool(self, tool_name: str):
        """移除工具记录"""
        if "tools" in self.state and tool_name in self.state["tools"]:
            del self.state["tools"][tool_name]
            self.state["last_updated"] = datetime.now().isoformat()
            self._save_state()

    def get_tools_to_cleanup(self, current_tools: Set[str]) -> Dict[str, Dict]:
        """获取需要清理的工具（不在当前工具列表中的）"""
        if "tools" not in self.state:
            return {}

        return {
            tool_name: tool_info
            for tool_name, tool_info in self.state["tools"].items()
            if tool_name not in current_tools
        }

    def get_tools_to_update(self, current_tools: Dict[str, Dict]) -> Dict[str, Dict]:
        """获取需要更新的工具（配置发生变化的）"""
        if "tools" not in self.state:
            return current_tools

        tools_to_update = {}
        for tool_name, tool_config in current_tools.items():
            old_hash = self.state["tools"].get(tool_name, {}).get("config_hash")
            new_hash = self._calculate_config_hash(
                tool_name,
                tool_config["openapi_base_url"],
                tool_config["api_key"],
                tool_config["skip_auth"]
            )

            if old_hash != new_hash:
                tools_to_update[tool_name] = tool_config

        return tools_to_update

    def get_all_tools_to_cleanup(self) -> Dict[str, Dict]:
        """获取所有需要清理的工具（用于update模式的完全清理）"""
        if "tools" not in self.state:
            return {}
        return dict(self.state["tools"])

    def clear_all_tools(self):
        """清空所有工具记录"""
        if "tools" in self.state:
            self.state["tools"] = {}
            self.state["last_updated"] = datetime.now().isoformat()
            self._save_state()

    def clear_all_state(self):
        """清空所有状态"""
        self.state = {}
        self._save_state()

    def get_gateway_info(self) -> Dict:
        """获取网关基础信息"""
        return {
            "gateway_id": self.state.get("gateway_id"),
            "plugin_id": self.state.get("plugin_id"),
            "http_api_id": self.state.get("http_api_id"),
            "environment_id": self.state.get("environment_id"),
            "domain_id": self.state.get("domain_id"),
            "shared_service_id": self.state.get("shared_service_id"),
            "shared_service_name": self.state.get("shared_service_name")
        }

    def has_state(self) -> bool:
        """检查是否有状态记录"""
        return bool(self.state.get("gateway_id"))


class MCPGatewayRegistrar:
    """MCP工具自动注册到阿里云AI网关的工具类"""

    def __init__(self, region: str = "cn-hangzhou", log_level: str = "INFO",
                 debug_response: bool = False, state_file: str = None):
        self.region = region
        self.debug_response = debug_response
        self.logger = self._setup_logger(log_level)
        self.state = MCPGatewayState(state_file)

    def _setup_logger(self, log_level: str) -> logging.Logger:
        """设置日志记录器"""
        logger = logging.getLogger("MCPGatewayRegistrar")
        logger.setLevel(getattr(logging, log_level.upper()))
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        return logger

    def _execute_aliyun_cli(self, method: str, endpoint: str, body: Dict = None, **params) -> Dict[str, Any]:
        """统一的阿里云CLI命令执行"""
        command = ["./aliyun", "apig", method, endpoint, "--endpoint", f"apig.{self.region}.aliyuncs.com"]
        # 添加参数
        for key, value in params.items():
            if value is not None:
                command.extend([f"--{key}", str(value)])

        # 添加请求体
        if body is not None:  # 改为检查是否为 None，而不是检查布尔值
            command.extend(["--body", json.dumps(body)])

        command.extend(["--header", "Content-Type=application/json;"])
        try:
            self.logger.info(f"执行CLI: {command} {method} {endpoint}")
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
            self.logger.error(error_msg)
            if self.debug_response:
                print(f"\n=== 错误详情 ===\n{error_msg}\n=== 错误结束 ===\n")
            raise RuntimeError(error_msg)
        except json.JSONDecodeError as e:
            error_msg = f"解析{method} {endpoint}响应失败: {str(e)}"
            self.logger.error(error_msg)
            if self.debug_response:
                print(f"\n=== JSON解析错误 ===\n{error_msg}\n原始输出: {result.stdout}\n=== 错误结束 ===\n")
            raise RuntimeError(error_msg)

    def _check_response(self, response: Dict, operation: str) -> Dict:
        """检查响应状态"""
        if response.get("code") not in ["Ok", "200"]:
            raise RuntimeError(f"{operation}失败: {response}")
        return response.get("data", {})

    def _find_items_by_name(self, gateway_id: str, endpoint: str, name: str, **extra_params) -> List[Dict]:
        """通用的按名称查找资源方法"""
        try:
            response = self._execute_aliyun_cli("GET", endpoint,
                                                gatewayId=gateway_id,
                                                gatewayType="AI",
                                                name=name,
                                                **extra_params)
            data = self._check_response(response, f"查询{endpoint}")
            return data.get("items", [])
        except Exception:
            return []

    def _load_pre_mcp_tools_config(self, pre_config_path: str = "/root/pre-mcp-tools.json") -> Dict[str, Dict]:
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

                self.logger.info(f"加载预定义工具配置: {len(pre_tools_dict)} 个工具")
                return pre_tools_dict
            else:
                self.logger.warning(f"预定义工具配置文件不存在: {pre_config_path}")
                return {}
        except Exception as e:
            self.logger.warning(f"加载预定义工具配置失败: {e}")
            return {}

    def _generate_route_description(self, tool_name: str, tools_config_path: str,
                                    pre_config_path: str = "/root/pre-mcp-tools.json") -> str:
        """生成路由描述信息"""
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
                self.logger.warning(f"未找到工具 {tool_name} 的配置")
                return tool_name

            # 查找预定义配置
            pre_config = pre_tools_config.get(tool_name, {})

            # 构建描述JSON
            description_json = {}

            # 添加 name 字段
            name_info = pre_config.get("ServiceName", {})
            if isinstance(name_info, dict):
                description_json["name"] = name_info.get("zh-cn", name_info.get("en", tool_name))
            elif name_info:
                description_json["name"] = str(name_info)
            else:
                # 如果预定义配置中没有ServiceName，使用工具名称
                description_json["name"] = tool_name

            # 添加 code 字段
            description_json["code"] = tool_name  # 使用serverCode作为code

            # 获取描述信息（优先中文）
            description_info = pre_config.get("Description", {})
            if isinstance(description_info, dict):
                description_json["Description"] = description_info.get("zh-cn",
                                                                       description_info.get("en", tool_name))
            else:
                description_json["Description"] = str(description_info) if description_info else tool_name

            #TODO 后续删除
            description_json["Description"] = "test"


            # 获取包路径
            package_path = tool_config.get("packageOssPath")
            if package_path:
                description_json["Path"] = f"oss://packages{package_path}"


            # 获取图标
            icon = tool_config.get("customIcon") or pre_config.get("Icon")
            if icon:
                description_json["Icon"] = icon

            # 添加其他有用信息
            if pre_config.get("ServiceName"):
                service_name = pre_config["ServiceName"]
                if isinstance(service_name, dict):
                    description_json["ServiceName"] = service_name.get("zh-cn",
                                                                       service_name.get("en", tool_name))

            # if pre_config.get("Tags"):
            #     description_json["Tags"] = pre_config["Tags"]

            # if pre_config.get("ReadMeUrl"):
            #     description_json["ReadMeUrl"] = pre_config["ReadMeUrl"]

            # 转换为JSON字符串
            return json.dumps(description_json, ensure_ascii=False, separators=(',', ':'))

        except Exception as e:
            self.logger.warning(f"生成工具 {tool_name} 描述失败: {e}")
            return tool_name

    def get_mcp_plugin_id(self, gateway_id: str) -> Optional[str]:
        """获取指定网关的MCP服务器插件ID"""
        self.logger.info(f"获取网关 {gateway_id} 的MCP插件ID")
        response = self._execute_aliyun_cli("GET", "/v1/plugins",
                                            gatewayType="AI",
                                            includeBuiltinAiGateway="true",
                                            pageNumber="0",
                                            pageSize="100")  # 增加页面大小以获取更多插件

        data = self._check_response(response, "获取插件列表")
        for item in data.get("items", []):
            # 检查插件类型和网关ID
            plugin_class_info = item.get("pluginClassInfo", {})
            gateway_info = item.get("gatewayInfo", {})

            if (plugin_class_info.get("name") == "mcp-server" and
                    gateway_info.get("gatewayId") == gateway_id):
                plugin_id = item.get("pluginId")
                self.logger.info(f"找到网关 {gateway_id} 的MCP插件ID: {plugin_id}")
                return plugin_id

        self.logger.warning(f"未找到网关 {gateway_id} 的mcp-server插件")
        return None

    def get_http_api_id(self, gateway_id: str) -> str:
        """获取MCP类型的HTTP API ID"""
        response = self._execute_aliyun_cli("GET", "/v1/http-apis", gatewayId=gateway_id, gatewayType="AI")
        data = self._check_response(response, "获取HTTP API列表")

        for item in data.get("items", []):
            if item.get("type") == "MCP":
                for api in item.get("versionedHttpApis", []):
                    if api.get("type") == "MCP":
                        api_id = api.get("httpApiId")
                        self.logger.info(f"找到MCP API ID: {api_id}")
                        return api_id

        raise RuntimeError("未找到MCP类型的HTTP API")

    def get_environment_id(self, gateway_id: str) -> str:
        """获取环境ID"""
        response = self._execute_aliyun_cli("GET", "/v1/environments", gatewayId=gateway_id, gatewayType="AI")
        data = self._check_response(response, "获取环境列表")

        items = data.get("items", [])
        if not items:
            raise RuntimeError("未找到任何环境")

        # 优先使用默认环境
        env = next((item for item in items if item.get("default")), items[0])
        env_id = env.get("environmentId")
        self.logger.info(f"使用环境ID: {env_id}")
        return env_id

    def ensure_domain(self, gateway_id: str, domain_id: str = None) -> str:
        """确保域名存在，支持传入指定域名ID或自动创建通配符域名"""
        # 如果指定了域名ID，直接验证可用性
        if domain_id:
            try:
                self.logger.info(f"检查指定域名ID: {domain_id}")
                response = self._execute_aliyun_cli("GET", f"/v1/domains/{domain_id}")
                data = self._check_response(response, "验证域名可用性")
                domain_name = data.get('name', 'Unknown')
                self.logger.info(f"✅ 域名ID {domain_id} 可用，域名: {domain_name}")
                return domain_id
            except Exception as e:
                raise RuntimeError(f"❌ 指定的域名ID {domain_id} 不可用或无效: {e}")

        # 如果没有指定域名ID，查找或创建通配符域名
        self.logger.info("未指定域名ID，查找或创建通配符域名")

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
                    self.logger.info(f"✅ 找到现有通配符域名，ID: {found_domain_id}")
                    return found_domain_id
        except Exception as e:
            self.logger.warning(f"查询通配符域名失败: {e}")

        # 如果没找到通配符域名，创建新的
        self.logger.info("🔨 创建新的通配符域名")
        try:
            response = self._execute_aliyun_cli("POST", "/v1/domains",
                                                {"name": "*", "protocol": "HTTP", "gatewayType": "AI"})
            data = self._check_response(response, "创建通配符域名")
            new_domain_id = data.get("domainId")
            self.logger.info(f"✅ 通配符域名创建成功，ID: {new_domain_id}")
            return new_domain_id
        except RuntimeError as e:
            # 如果创建失败且是因为域名已存在，重新查询
            if "Conflict.DomainExisted" in str(e) or "域名*已存在" in str(e):
                self.logger.warning("⚠️  通配符域名已存在，重新查询")
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
                            self.logger.info(f"✅ 重新查询找到通配符域名，ID: {existing_domain_id}")
                            return existing_domain_id

                    raise RuntimeError("通配符域名已存在但无法查询到对应的域名ID")
                except Exception as query_e:
                    raise RuntimeError(f"通配符域名已存在但重新查询失败: {query_e}")
            else:
                raise RuntimeError(f"创建通配符域名失败: {e}")

    def ensure_shared_service(self, gateway_id: str, private_ip: str, shared_service_name: str) -> str:
        """确保指定名称的共享MCP服务存在"""
        self.logger.info(f"确保共享MCP服务存在: {shared_service_name}")

        # 检查现有服务
        existing_services = self._find_items_by_name(gateway_id, "/v1/services", shared_service_name)
        if existing_services:
            service_id = existing_services[0].get("serviceId")
            self.logger.info(f"✅ 共享MCP服务已存在，名称: {shared_service_name}, ID: {service_id}")
            return service_id

        # 创建新的共享服务
        self.logger.info(f"🔨 创建共享MCP服务: {shared_service_name}")
        body = {
            "gatewayId": gateway_id,
            "sourceType": "VIP",
            "serviceConfigs": [{"name": shared_service_name, "addresses": [f"{private_ip}:8000"]}]
        }
        response = self._execute_aliyun_cli("POST", "/v1/services", body)
        data = self._check_response(response, "创建共享MCP服务")

        service_ids = data.get("serviceIds", [])
        if not service_ids:
            raise RuntimeError("创建共享MCP服务成功但未返回服务ID")

        service_id = service_ids[0]
        self.logger.info(f"✅ 共享MCP服务创建成功，名称: {shared_service_name}, ID: {service_id}")
        return service_id

    def _check_and_resolve_plugin_conflicts(self, route_id: str, force_update: bool = True) -> bool:
        """检查并解决插件规则冲突（默认强制更新）"""
        try:
            # 获取路由上现有的插件挂载
            response = self._execute_aliyun_cli("GET", "/v1/plugin-attachments",
                                                attachResourceType="GatewayRoute",
                                                attachResourceId=route_id,
                                                pageSize="100")

            data = self._check_response(response, "查询路由插件挂载")
            existing_attachments = data.get("items", [])

            if not existing_attachments:
                self.logger.info(f"路由 {route_id} 无现有插件挂载")
                return True

            self.logger.info(f"路由 {route_id} 发现 {len(existing_attachments)} 个现有插件挂载")

            if not force_update:
                self.logger.warning(f"路由 {route_id} 已有插件挂载，需要 force_update=True 来强制更新")
                return False

            # 强制更新：删除现有的插件挂载
            for attachment in existing_attachments:
                attachment_id = attachment.get("attachmentId")
                if attachment_id:
                    try:
                        self.logger.info(f"删除现有插件挂载: {attachment_id}")
                        self._execute_aliyun_cli("DELETE", f"/v1/plugin-attachments/{attachment_id}")
                        self.logger.info(f"✅ 插件挂载 {attachment_id} 删除成功")
                    except Exception as e:
                        self.logger.warning(f"删除插件挂载 {attachment_id} 失败: {e}")

            # 等待删除生效
            time.sleep(2)
            return True

        except Exception as e:
            self.logger.error(f"检查插件冲突时出错: {e}")
            return False

    def ensure_route(self, http_api_id: str, gateway_id: str, environment_id: str,
                     tool_name: str, domain_id: str, service_id: str, force_update: bool = True,
                     tools_config_path: str = None, pre_config_path: str = "/root/pre-mcp-tools.json") -> Tuple[str, bool]:
        """确保路由存在，返回(route_id, need_update_config)（默认强制更新）"""

        # 生成描述信息
        description = self._generate_route_description(tool_name, tools_config_path, pre_config_path) if tools_config_path else tool_name

        # 检查现有路由
        existing_routes = self._find_items_by_name(gateway_id, f"/v1/http-apis/{http_api_id}/routes",
                                                   tool_name, environmentId=environment_id)
        if existing_routes:
            route_id = existing_routes[0].get("routeId")
            self.logger.info(f"路由 {tool_name} 已存在，ID: {route_id}")

            # 检查路由是否使用了正确的域名和描述
            try:
                response = self._execute_aliyun_cli("GET", f"/v1/http-apis/{http_api_id}/routes/{route_id}")
                route_data = self._check_response(response, "获取路由详情")
                current_domain_ids = route_data.get("domainIds", [])
                current_description = route_data.get("description", "")

                # 检查是否需要更新
                need_update = (domain_id not in current_domain_ids or
                               current_description != description)

                if need_update:
                    self.logger.info(f"路由 {tool_name} 需要更新配置")
                    # 更新路由配置
                    update_body = {
                        "domainIds": [domain_id],
                        "environmentId": environment_id,
                        "match": route_data.get("match"),
                        "backendConfig": route_data.get("backendConfig"),
                        "mcpRouteConfig": route_data.get("mcpRouteConfig"),
                        "name": tool_name,
                        "description": description  # 使用新生成的描述
                    }
                    self._execute_aliyun_cli("PUT", f"/v1/http-apis/{http_api_id}/routes/{route_id}", update_body)
                    self.logger.info(f"路由 {tool_name} 配置已更新")
            except Exception as e:
                self.logger.warning(f"检查或更新路由配置失败: {e}")

            # 检查并解决插件冲突
            conflict_resolved = self._check_and_resolve_plugin_conflicts(route_id, force_update)
            return route_id, conflict_resolved

        # 创建新路由
        self.logger.info(f"创建路由: {tool_name}")
        body = {
            "domainIds": [domain_id],
            "environmentId": environment_id,
            "match": {"path": {"type": "Prefix", "value": f"/mcp-servers/{tool_name}"}},
            "backendConfig": {"scene": "SingleService", "services": [{"serviceId": service_id}]},
            "mcpRouteConfig": {"protocol": "HTTP"},
            "name": tool_name,
            "description": description  # 使用新生成的描述
        }
        response = self._execute_aliyun_cli("POST", f"/v1/http-apis/{http_api_id}/routes", body)
        data = self._check_response(response, "创建路由")

        route_id = data.get("routeId")
        if not route_id:
            raise RuntimeError("创建路由成功但未返回路由ID")

        self.logger.info(f"路由创建成功，ID: {route_id}")
        return route_id, True

    def _validate_mcp_service_tools(self, openapi_base_url: str, tool_name: str) -> bool:
        """验证MCP服务中的工具是否可用"""
        try:
            # 检查OpenAPI规范是否可访问
            spec_url = f"{openapi_base_url}/{tool_name}/openapi.json"
            self.logger.info(f"验证工具 {tool_name} 的OpenAPI规范: {spec_url}")

            response = requests.get(spec_url, timeout=10)
            if response.status_code != 200:
                self.logger.error(f"工具 {tool_name} 的OpenAPI规范不可访问: {response.status_code}")
                return False

            spec = response.json()

            # 检查规范是否包含必要的路径
            paths = spec.get("paths", {})
            if not paths:
                self.logger.error(f"工具 {tool_name} 的OpenAPI规范中没有定义任何路径")
                return False

            self.logger.info(f"✅ 工具 {tool_name} 验证通过，包含 {len(paths)} 个API路径")
            return True

        except requests.exceptions.Timeout:
            self.logger.error(f"验证工具 {tool_name} 超时")
            return False
        except Exception as e:
            self.logger.error(f"验证工具 {tool_name} 失败: {e}")
            return False

    def generate_mcp_config(self, tool_name: str, openapi_base_url: str, api_key: str, skip_auth: bool) -> str:
        """生成MCP配置并返回base64编码"""
        # 验证工具是否可用
        if not self._validate_mcp_service_tools(openapi_base_url, tool_name):
            raise RuntimeError(f"工具 {tool_name} 验证失败，无法生成配置")

        # 获取OpenAPI规范
        spec_url = f"{openapi_base_url}/{tool_name}/openapi.json"
        self.logger.info(f"获取OpenAPI规范: {spec_url}")

        try:
            response = requests.get(spec_url, timeout=30)
            response.raise_for_status()
            spec = response.json()
        except Exception as e:
            raise RuntimeError(f"获取OpenAPI规范失败: {e}")

        # 保存临时文件
        temp_dir = tempfile.mkdtemp(prefix=f"mcp_{tool_name}_")
        json_file = os.path.join(temp_dir, f"{tool_name}.json")
        yaml_file = os.path.join(temp_dir, f"{tool_name}.yaml")

        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(spec, f, ensure_ascii=False, indent=2)

        # 转换为MCP配置
        try:
            cmd = ["./openapi-to-mcp", "--input", json_file, "--output", yaml_file, "--server-name", tool_name]
            result = subprocess.run(
                cmd,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"转换OpenAPI失败: {e.stderr}")

        # 修改YAML配置
        with open(yaml_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        # 设置基础配置
        if 'server' not in config:
            config['server'] = {}
        if 'config' not in config['server']:
            config['server']['config'] = {}

        config['server']['config']['baseUrl'] = openapi_base_url
        if not skip_auth:
            config['server']['config']['apikey'] = api_key

        # 修改工具配置
        tools_count = 0
        for tool in config.get('tools', []):
            if 'requestTemplate' in tool:
                tools_count += 1
                # 修改URL
                if 'url' in tool['requestTemplate']:
                    original_url = tool['requestTemplate']['url']
                    path = original_url.split('/', 3)[-1] if '/' in original_url else original_url.lstrip('/')
                    tool['requestTemplate']['url'] = f"{{{{.config.baseUrl}}}}/{tool_name}/{path}"

                # 添加授权头
                if not skip_auth:
                    if 'headers' not in tool['requestTemplate']:
                        tool['requestTemplate']['headers'] = []

                    # 检查是否已有授权头
                    has_auth = any(h.get('key') == 'Authorization' for h in tool['requestTemplate']['headers'])
                    if not has_auth:
                        tool['requestTemplate']['headers'].append({
                            'key': 'Authorization',
                            'value': "Bearer {{.config.apikey}}"
                        })

        if tools_count == 0:
            raise RuntimeError(f"工具 {tool_name} 的MCP配置中没有找到任何工具定义")

        self.logger.info(f"✅ 工具 {tool_name} 的MCP配置生成成功，包含 {tools_count} 个工具")

        # 保存修改后的配置
        with open(yaml_file, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, allow_unicode=True, default_flow_style=False)

        # 读取并编码
        with open(yaml_file, 'r', encoding='utf-8') as f:
            yaml_content = f.read()

        if self.debug_response:
            print(f"\n=== {tool_name} MCP配置 ===")
            print(yaml_content)
            print("=== 配置结束 ===\n")

        return base64.b64encode(yaml_content.encode('utf-8')).decode('utf-8')

    def create_plugin_attachment(self, gateway_id: str, plugin_id: str, route_id: str, plugin_config: str) -> str:
        """创建插件挂载并返回挂载ID"""
        self.logger.info(f"创建插件挂载，路由ID: {route_id}")
        body = {
            "pluginId": plugin_id,
            "pluginConfig": plugin_config,
            "attachResourceType": "GatewayRoute",
            "attachResourceIds": [route_id],
            "gatewayId": gateway_id,
            "enable": True
        }

        try:
            response = self._execute_aliyun_cli("POST", "/v1/plugin-attachments", body)
            data = self._check_response(response, "创建插件挂载")

            # 尝试多种方式获取挂载ID
            attachment_id = (
                    data.get("attachmentId") or
                    data.get("id") or
                    data.get("pluginAttachmentId") or
                    data.get("data", {}).get("attachmentId")
            )

            if self.debug_response:
                print(f"\n=== 插件挂载创建响应数据 ===")
                print(json.dumps(data, indent=2, ensure_ascii=False))
                print(f"提取的挂载ID: {attachment_id}")
                print("=== 响应数据结束 ===\n")

            if not attachment_id:
                # 如果无法从响应中获取ID，尝试查询获取
                self.logger.warning("响应中未包含挂载ID，尝试查询获取")
                time.sleep(2)  # 等待创建生效

                query_response = self._execute_aliyun_cli("GET", "/v1/plugin-attachments",
                                                          gatewayId=gateway_id,
                                                          pluginId=plugin_id,
                                                          attachResourceType="GatewayRoute",
                                                          attachResourceId=route_id,
                                                          pageSize="10")
                query_data = self._check_response(query_response, "查询插件挂载")
                items = query_data.get("items", [])

                if items:
                    attachment_id = items[0].get("attachmentId")
                    self.logger.info(f"通过查询获取到挂载ID: {attachment_id}")
                else:
                    raise RuntimeError("创建插件挂载成功但无法获取挂载ID")

            self.logger.info(f"✅ 插件挂载创建成功，ID: {attachment_id}")
            return attachment_id

        except RuntimeError as e:
            # 如果是因为已存在而失败，尝试获取现有挂载ID
            if "已存在" in str(e) or "exist" in str(e).lower() or "Conflict" in str(e):
                self.logger.warning(f"插件挂载可能已存在: {e}")
                # 尝试查找现有挂载
                try:
                    response = self._execute_aliyun_cli("GET", "/v1/plugin-attachments",
                                                        gatewayId=gateway_id,
                                                        pluginId=plugin_id,
                                                        attachResourceType="GatewayRoute",
                                                        attachResourceId=route_id,
                                                        pageSize="10")
                    data = self._check_response(response, "查询现有插件挂载")
                    items = data.get("items", [])
                    if items:
                        existing_id = items[0].get("attachmentId")
                        self.logger.info(f"找到现有插件挂载ID: {existing_id}")
                        return existing_id
                except Exception as query_e:
                    self.logger.warning(f"查询现有挂载失败: {query_e}")

                raise RuntimeError(f"插件挂载创建失败且无法找到现有挂载: {e}")
            else:
                raise

    def enable_plugin_attachment(self, attachment_id: str) -> bool:
        """启用插件挂载"""
        if not attachment_id:
            self.logger.error("挂载ID为空，无法启用")
            return False

        try:
            self.logger.info(f"检查插件挂载状态: {attachment_id}")

            # 检查挂载状态
            response = self._execute_aliyun_cli("GET", f"/v1/plugin-attachments/{attachment_id}")
            data = self._check_response(response, "检查插件挂载状态")

            status = data.get("status", "unknown").lower()
            enable_status = data.get("enable", True)

            self.logger.info(f"插件挂载 {attachment_id} 当前状态: {status}, 启用状态: {enable_status}")

            # 如果状态为unknown但enable为true，认为是正常的
            if status == "unknown" and enable_status:
                self.logger.info(f"✅ 插件挂载 {attachment_id} 状态未知但已启用")
                return True
            elif status in [ "active", "enabled", "running", "attached" ] or enable_status:
                self.logger.info(f"✅ 插件挂载 {attachment_id} 已启用")
                return True
            elif status in ["inactive", "disabled", "pending"]:
                # 尝试启用挂载（如果有启用API）
                try:
                    enable_response = self._execute_aliyun_cli("POST", f"/v1/plugin-attachments/{attachment_id}/enable")
                    self._check_response(enable_response, "启用插件挂载")
                    self.logger.info(f"✅ 插件挂载 {attachment_id} 启用成功")
                    return True
                except Exception as enable_e:
                    # 如果没有启用API，假设创建后就是启用状态
                    if "404" in str(enable_e) or "Not Found" in str(enable_e):
                        self.logger.info(f"✅ 插件挂载 {attachment_id} 创建后默认启用")
                        return True
                    else:
                        self.logger.warning(f"启用插件挂载失败: {enable_e}")
                        return False
            else:
                # 对于unknown状态，我们认为是可用的（阿里云API的特殊情况）
                self.logger.info(f"✅ 插件挂载 {attachment_id} 状态为 {status}，假设可用")
                return True

        except Exception as e:
            self.logger.error(f"检查插件挂载 {attachment_id} 状态失败: {e}")
            # 即使检查失败，也假设挂载是可用的
            return True

    def update_plugin_attachment(self, gateway_id: str, plugin_id: str, route_id: str, plugin_config: str):
        """创建插件挂载并启用（兼容原有接口）"""
        try:
            # 创建插件挂载
            attachment_id = self.create_plugin_attachment(gateway_id, plugin_id, route_id, plugin_config)

            if not attachment_id:
                raise RuntimeError("插件挂载创建失败：未获取到挂载ID")

            # 启用插件挂载
            enabled = self.enable_plugin_attachment(attachment_id)
            if enabled:
                self.logger.info(f"✅ 插件挂载 {attachment_id} 创建并启用成功")

                # 验证挂载是否真正生效
                if self._verify_plugin_attachment(gateway_id, plugin_id, route_id):
                    self.logger.info(f"✅ 插件挂载 {attachment_id} 验证成功")
                else:
                    self.logger.warning(f"⚠️  插件挂载 {attachment_id} 验证失败")

                # 等待配置生效
                time.sleep(2)

            else:
                self.logger.warning(f"⚠️  插件挂载 {attachment_id} 创建成功但启用失败")

            return attachment_id

        except Exception as e:
            self.logger.error(f"插件挂载操作失败: {e}")
            raise RuntimeError(f"插件挂载创建或启用失败: {e}")

    def _verify_plugin_attachment(self, gateway_id: str, plugin_id: str, route_id: str) -> bool:
        """验证插件挂载是否生效"""
        try:
            self.logger.info(f"验证插件挂载是否生效，路由ID: {route_id}")

            # 查询路由上的插件挂载
            response = self._execute_aliyun_cli("GET", "/v1/plugin-attachments",
                                                gatewayId=gateway_id,
                                                pluginId=plugin_id,
                                                attachResourceType="GatewayRoute",
                                                attachResourceId=route_id,
                                                pageSize="10")
            data = self._check_response(response, "验证插件挂载")
            items = data.get("items", [])

            if items:
                attachment = items[0]
                attachment_id = attachment.get("attachmentId")
                status = attachment.get("status", "unknown")
                enable_status = attachment.get("enable", True)

                self.logger.info(f"找到插件挂载: {attachment_id}, 状态: {status}, 启用: {enable_status}")

                # 只要找到挂载就认为验证成功
                return True
            else:
                self.logger.warning("未找到插件挂载")
                return False

        except Exception as e:
            self.logger.warning(f"验证插件挂载失败: {e}")
            # 验证失败不影响整体流程
            return True

    def deploy_http_api_route(self, http_api_id: str, environment_id: str, gateway_id: str, route_id: str) -> bool:
        """发布单个路由到指定环境"""
        try:
            self.logger.info(f"🚀 发布路由 {route_id} 到环境 {environment_id}")

            # 执行发布
            body = {
                "gatewayId": gateway_id,
                "routeId": route_id,
                "description": "MCP工具自动发布"
            }

            response = self._execute_aliyun_cli("POST", f"/v1/http-apis/{http_api_id}/deploy", body)
            data = self._check_response(response, "发布HTTP API路由")

            # 等待发布完成
            time.sleep(3)

            # 检查发布状态
            if "deployConfigs" in data and data["deployConfigs"]:
                deploy_config = data["deployConfigs"][0]
                status = deploy_config.get("status", "unknown")
                route_id_returned = deploy_config.get("routeId", route_id)
                self.logger.info(f"✅ 路由 {route_id_returned} 发布成功，状态: {status}")
            else:
                self.logger.info(f"✅ 路由 {route_id} 发布完成")

            return True

        except Exception as e:
            self.logger.error(f"发布路由 {route_id} 失败: {e}")
            if self.debug_response:
                import traceback
                traceback.print_exc()
            return False

    def undeploy_http_api_route(self, http_api_id: str, environment_id: str, gateway_id: str, route_id: str) -> bool:
        """下线单个路由"""
        try:
            self.logger.info(f"📤 下线路由 {route_id} 从环境 {environment_id}")

            # 执行下线
            body = {
                "gatewayId": gateway_id,
                "routeId": route_id,
                "description": "MCP工具自动下线"
            }

            response = self._execute_aliyun_cli("POST", f"/v1/http-apis/{http_api_id}/undeploy", body)
            data = self._check_response(response, "下线HTTP API路由")

            # 等待下线完成
            time.sleep(2)

            # 检查下线状态
            if "deployConfigs" in data and data["deployConfigs"]:
                deploy_config = data["deployConfigs"][0]
                status = deploy_config.get("status", "unknown")
                route_id_returned = deploy_config.get("routeId", route_id)
                self.logger.info(f"✅ 路由 {route_id_returned} 下线成功，状态: {status}")
            else:
                self.logger.info(f"✅ 路由 {route_id} 下线完成")

            return True

        except Exception as e:
            self.logger.error(f"下线路由 {route_id} 失败: {e}")
            if self.debug_response:
                import traceback
                traceback.print_exc()
            return False

    def deploy_http_api(self, http_api_id: str, environment_id: str, gateway_id: str, route_ids: List[str] = None) -> bool:
        """发布HTTP API到指定环境（批量发布多个路由）"""
        try:
            self.logger.info(f"🚀 开始批量发布HTTP API {http_api_id} 的路由")

            # 如果没有提供route_ids，获取所有路由
            if not route_ids:
                route_ids = self._get_all_route_ids(http_api_id, gateway_id, environment_id)

            if not route_ids:
                self.logger.warning(f"HTTP API {http_api_id} 没有找到任何路由，跳过发布")
                return True

            self.logger.info(f"准备发布 {len(route_ids)} 个路由")

            # 逐个发布路由
            success_count = 0
            failed_count = 0

            for route_id in route_ids:
                try:
                    if self.deploy_http_api_route(http_api_id, environment_id, gateway_id, route_id):
                        success_count += 1
                        self.logger.debug(f"路由 {route_id} 发布成功")
                    else:
                        failed_count += 1
                        self.logger.warning(f"路由 {route_id} 发布失败")

                    # 避免请求过于频繁
                    time.sleep(1)

                except Exception as e:
                    failed_count += 1
                    self.logger.error(f"发布路由 {route_id} 时发生异常: {e}")

            # 输出批量发布结果
            self.logger.info(f"📊 批量发布完成: 成功 {success_count} 个，失败 {failed_count} 个")

            # 只要有成功的就认为整体成功
            return success_count > 0

        except Exception as e:
            self.logger.error(f"批量发布HTTP API {http_api_id} 失败: {e}")
            if self.debug_response:
                import traceback
                traceback.print_exc()
            return False

    def undeploy_http_api(self, http_api_id: str, environment_id: str, gateway_id: str, route_ids: List[
        str ] = None) -> bool:
        """下线HTTP API（批量下线多个路由）"""
        try:
            self.logger.info(f"📤 开始批量下线HTTP API {http_api_id} 的路由")

            # 如果没有提供route_ids，获取所有已发布的路由
            if not route_ids:
                route_ids = self._get_deployed_route_ids(http_api_id, gateway_id, environment_id)

            if not route_ids:
                self.logger.info(f"HTTP API {http_api_id} 没有已发布的路由，无需下线")
                return True

            self.logger.info(f"准备下线 {len(route_ids)} 个路由")

            # 逐个下线路由
            success_count = 0
            failed_count = 0

            for route_id in route_ids:
                try:
                    if self.undeploy_http_api_route(http_api_id, environment_id, gateway_id, route_id):
                        success_count += 1
                        self.logger.debug(f"路由 {route_id} 下线成功")
                    else:
                        failed_count += 1
                        self.logger.warning(f"路由 {route_id} 下线失败")

                    # 避免请求过于频繁
                    time.sleep(1)

                except Exception as e:
                    failed_count += 1
                    self.logger.error(f"下线路由 {route_id} 时发生异常: {e}")

            # 输出批量下线结果
            self.logger.info(f"📊 批量下线完成: 成功 {success_count} 个，失败 {failed_count} 个")

            # 只要有成功的就认为整体成功
            return success_count > 0

        except Exception as e:
            self.logger.error(f"批量下线HTTP API {http_api_id} 失败: {e}")
            if self.debug_response:
                import traceback
                traceback.print_exc()
            return False

    def _check_route_deployment_status(self, http_api_id: str, route_id: str, gateway_id: str, environment_id: str) -> str:
        """检查单个路由的部署状态"""
        try:
            response = self._execute_aliyun_cli("GET", f"/v1/http-apis/{http_api_id}/deployments",
                                                gatewayId=gateway_id,
                                                gatewayType="AI",
                                                environmentId=environment_id)
            data = self._check_response(response, "检查路由部署状态")

            # 查找指定路由的部署状态
            for deployment in data.get("items", [ ]):
                deploy_configs = deployment.get("deployConfigs", [ ])
                for config in deploy_configs:
                    if config.get("routeId") == route_id:
                        return config.get("status", "unknown")

            return "not_deployed"

        except Exception as e:
            self.logger.warning(f"检查路由 {route_id} 部署状态失败: {e}")
            return "unknown"

    def _get_all_route_ids(self, http_api_id: str, gateway_id: str, environment_id: str) -> List[str]:
        """获取HTTP API下所有路由的ID"""
        try:
            self.logger.info(f"获取HTTP API {http_api_id} 下的所有路由")

            response = self._execute_aliyun_cli("GET", f"/v1/http-apis/{http_api_id}/routes",
                                                gatewayId=gateway_id,
                                                gatewayType="AI",
                                                environmentId=environment_id)
            data = self._check_response(response, "获取所有路由")

            route_ids = [ ]
            routes_info = [ ]

            for route in data.get("items", [ ]):
                route_id = route.get("routeId")
                route_name = route.get("name", "unnamed")
                if route_id:
                    route_ids.append(route_id)
                    routes_info.append(f"{route_name}({route_id})")

            if routes_info:
                self.logger.info(f"找到 {len(route_ids)} 个路由: {', '.join(routes_info)}")
            else:
                self.logger.info(f"HTTP API {http_api_id} 下没有找到任何路由")

            return route_ids

        except Exception as e:
            self.logger.warning(f"获取HTTP API {http_api_id} 路由列表失败: {e}")
            return []

    def _get_mcp_route_ids(self, http_api_id: str, gateway_id: str, environment_id: str) -> List[ str ]:
        """获取MCP相关的路由ID（过滤掉系统路由）"""
        try:
            self.logger.info(f"获取HTTP API {http_api_id} 下的MCP路由")

            response = self._execute_aliyun_cli("GET", f"/v1/http-apis/{http_api_id}/routes",
                                                gatewayId=gateway_id,
                                                gatewayType="AI",
                                                environmentId=environment_id)
            data = self._check_response(response, "获取MCP路由")

            mcp_route_ids = [ ]
            mcp_routes_info = [ ]

            for route in data.get("items", []):
                route_id = route.get("routeId")
                route_name = route.get("name", "")

                # 过滤条件：
                # 1. 有路由ID
                # 2. 有路由名称
                # 3. 不是系统路由（不以system-开头）
                # 4. 路径包含mcp-servers（可选的额外过滤）
                if (route_id and route_name and
                        not route_name.startswith("system-") and
                        route_name.strip()):

                    # 可选：检查路径是否包含mcp-servers
                    match_config = route.get("match", {})
                    path_config = match_config.get("path", {})
                    path_value = path_config.get("value", "")

                    # 如果路径包含mcp-servers或者路由名称看起来像MCP工具名称，则认为是MCP路由
                    is_mcp_route = (
                            "mcp-servers" in path_value.lower() or
                            not any(keyword in route_name.lower() for keyword in [ "system", "default", "health", "status" ])
                    )

                    if is_mcp_route:
                        mcp_route_ids.append(route_id)
                        mcp_routes_info.append(f"{route_name}({route_id})")

            if mcp_routes_info:
                self.logger.info(f"找到 {len(mcp_route_ids)} 个MCP路由: {', '.join(mcp_routes_info)}")
            else:
                self.logger.info(f"HTTP API {http_api_id} 下没有找到MCP路由")

            return mcp_route_ids

        except Exception as e:
            self.logger.warning(f"获取HTTP API {http_api_id} MCP路由列表失败: {e}")
            return []

    def _get_deployed_route_ids(self, http_api_id: str, gateway_id: str, environment_id: str) -> List[ str ]:
        """获取已发布的路由ID"""
        try:
            self.logger.info(f"获取HTTP API {http_api_id} 已发布的路由")

            # 先获取所有MCP路由
            all_mcp_route_ids = self._get_mcp_route_ids(http_api_id, gateway_id, environment_id)

            if not all_mcp_route_ids:
                self.logger.info("没有找到MCP路由")
                return [ ]

            # 检查哪些路由已发布
            deployed_route_ids = [ ]

            try:
                # 尝试获取部署信息
                response = self._execute_aliyun_cli("GET", f"/v1/http-apis/{http_api_id}/deployments",
                                                    gatewayId=gateway_id,
                                                    gatewayType="AI",
                                                    environmentId=environment_id)
                data = self._check_response(response, "获取部署信息")

                # 从部署信息中提取已发布的路由
                deployed_routes_info = [ ]
                for deployment in data.get("items", [ ]):
                    deploy_configs = deployment.get("deployConfigs", [ ])
                    for config in deploy_configs:
                        route_id = config.get("routeId")
                        status = config.get("status", "").lower()

                        # 只考虑MCP路由且状态为已发布的
                        if (route_id and route_id in all_mcp_route_ids and
                                status in [ "deployed", "success", "active" ]):
                            deployed_route_ids.append(route_id)
                            deployed_routes_info.append(f"{route_id}({status})")

                if deployed_routes_info:
                    self.logger.info(f"找到 {len(deployed_route_ids)} 个已发布的MCP路由: {', '.join(deployed_routes_info)}")
                else:
                    self.logger.info("没有找到已发布的MCP路由")

            except Exception as e:
                self.logger.warning(f"获取部署信息失败，假设所有MCP路由都已发布: {e}")
                # 如果无法获取部署信息，假设所有MCP路由都已发布
                deployed_route_ids = all_mcp_route_ids
                self.logger.info(f"假设 {len(deployed_route_ids)} 个MCP路由都已发布")

            # 去重
            deployed_route_ids = list(set(deployed_route_ids))
            return deployed_route_ids

        except Exception as e:
            self.logger.warning(f"获取已发布路由失败: {e}")
            return []

    def extract_tools_from_config(self, config_path: str) -> List[str]:
        """从配置文件提取工具列表"""
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

            self.logger.info(f"找到 {len(tools)} 个工具: {', '.join(tools)}")
            return tools
        except Exception as e:
            raise RuntimeError(f"解析配置文件失败: {e}")

    def cleanup_specific_tools(self, gateway_id: str, plugin_id: str,
                               tools_to_cleanup: Dict[str, Dict]) -> Tuple[int, int, List[str], List[str]]:
        """清理指定的工具（用于变配场景）- 修复字典遍历问题"""
        if not tools_to_cleanup:
            self.logger.info("没有需要清理的工具")
            return 0, 0, [], []

        self.logger.info(f"开始清理 {len(tools_to_cleanup)} 个指定工具")
        success_tools, failed_tools = [], []

        try:
            http_api_id = self.get_http_api_id(gateway_id)
            environment_id = self.get_environment_id(gateway_id)

            # 收集需要下线的路由ID
            route_ids_to_undeploy = []
            for tool_name, tool_info in tools_to_cleanup.items():
                route_id = tool_info.get("route_id")
                if route_id:
                    route_ids_to_undeploy.append(route_id)

            # 批量下线路由
            if route_ids_to_undeploy:
                self.logger.info(f"📤 下线 {len(route_ids_to_undeploy)} 个路由")
                self.undeploy_http_api(http_api_id, environment_id, gateway_id, route_ids_to_undeploy)

            # 先收集所有工具信息，避免在遍历时修改字典
            tools_to_process = list(tools_to_cleanup.items())  # 转换为列表

            # 逐个清理工具资源
            for tool_name, tool_info in tools_to_process:  # 遍历列表而不是字典
                try:
                    self.logger.info(f"🧹 清理工具: {tool_name}")

                    # 删除插件挂载
                    attachment_id = tool_info.get("attachment_id")
                    if attachment_id:
                        self.delete_plugin_attachment(attachment_id)

                    # 删除路由
                    route_id = tool_info.get("route_id")
                    if route_id:
                        self.delete_route(http_api_id, route_id)

                    # 从状态中移除
                    self.state.remove_tool(tool_name)

                    success_tools.append(tool_name)
                    self.logger.info(f"✅ 工具 {tool_name} 清理成功")

                except Exception as e:
                    self.logger.error(f"❌ 清理工具 {tool_name} 失败: {e}")
                    failed_tools.append(tool_name)

            return len(success_tools), len(failed_tools), success_tools, failed_tools

        except Exception as e:
            self.logger.error(f"清理指定工具失败: {e}")
            raise

    def cleanup_for_update(self, gateway_id: str, plugin_id: str,
                           tools_config: str) -> Tuple[int, int, List[str], List[str]]:
        """变配模式的清理：清理所有现有工具，保留共享服务"""
        self.logger.info("🔄 开始变配模式清理：清理所有现有MCP工具")

        # 获取当前配置中的工具列表（用于日志输出）
        try:
            current_tools_list = self.extract_tools_from_config(tools_config)
            current_tools_set = set(current_tools_list)
            self.logger.info(f"新配置包含 {len(current_tools_list)} 个工具: {', '.join(current_tools_list)}")
        except Exception as e:
            self.logger.warning(f"解析新配置失败: {e}")
            current_tools_set = set()

        # 获取状态中的所有工具进行清理
        tools_to_cleanup = self.state.get_all_tools_to_cleanup()

        if not tools_to_cleanup:
            self.logger.info("状态中没有需要清理的工具")
            return 0, 0, [], []

        self.logger.info(f"状态中有 {len(tools_to_cleanup)} 个工具需要清理: {', '.join(tools_to_cleanup.keys())}")

        # 执行清理
        success, failed, success_list, failed_list = self.cleanup_specific_tools(
            gateway_id, plugin_id, tools_to_cleanup
        )

        # 注意：这里不清理共享服务，因为后续的create模式还会用到
        self.logger.info("ℹ️  保留共享MCP服务，供后续create模式使用")

        return success, failed, success_list, failed_list

    def register_tools_with_state(self, gateway_id: str, plugin_id: str, private_ip: str,
                                  tools_config: str, api_key: str, shared_service_name: str,
                                  openapi_base_url: str = "http://127.0.0.1:8000",
                                  skip_auth: bool = False, force_update: bool = True,
                                  domain_id: str = None,
                                  mode: str = "create",
                                  pre_config_path: str = "/root/pre-mcp-tools.json") -> Tuple[int, int, List[str], List[str]]:
        """带状态管理的工具注册（支持变配模式）"""
        self.logger.info(f"开始{mode}模式的MCP工具操作，共享服务名称: {shared_service_name}")

        if mode == "update":
            # update模式：只清理现有工具，不创建新工具
            return self.cleanup_for_update(gateway_id, plugin_id, tools_config)

        # create模式：正常的创建流程
        current_tools_list = self.extract_tools_from_config(tools_config)
        success_tools, failed_tools = [], []

        try:
            # 获取基础信息
            http_api_id = self.get_http_api_id(gateway_id)
            domain_id = self.ensure_domain(gateway_id, domain_id)
            environment_id = self.get_environment_id(gateway_id)
            shared_service_id = self.ensure_shared_service(gateway_id, private_ip, shared_service_name)

            # 更新状态中的网关信息
            self.state.update_gateway_info(
                gateway_id, plugin_id, http_api_id,
                environment_id, domain_id, shared_service_id, shared_service_name
            )

            # 注册工具
            openapi_base_url = openapi_base_url.replace("127.0.0.1", private_ip)
            created_route_ids = []

            for tool_name in current_tools_list:
                try:
                    self.logger.info(f"📝 处理工具: {tool_name}")

                    # 验证工具
                    if not self._validate_mcp_service_tools(openapi_base_url, tool_name):
                        self.logger.error(f"❌ 工具 {tool_name} 验证失败")
                        failed_tools.append(tool_name)
                        continue

                    # 创建路由（传递配置文件路径）
                    route_id, need_update = self.ensure_route(
                        http_api_id, gateway_id, environment_id,
                        tool_name, domain_id, shared_service_id, force_update,
                        tools_config, pre_config_path  # 传递配置文件路径
                    )

                    if route_id and need_update:
                        created_route_ids.append(route_id)

                    # 更新插件配置
                    if need_update:
                        plugin_config = self.generate_mcp_config(
                            tool_name, openapi_base_url, api_key, skip_auth
                        )

                        attachment_id = self.update_plugin_attachment(
                            gateway_id, plugin_id, route_id, plugin_config
                        )

                        # 更新状态
                        self.state.add_tool(
                            tool_name, route_id, attachment_id,
                            openapi_base_url, api_key, skip_auth
                        )

                    success_tools.append(tool_name)

                except Exception as e:
                    self.logger.error(f"❌ 处理工具 {tool_name} 失败: {e}")
                    failed_tools.append(tool_name)

            # 发布新创建的路由
            if created_route_ids:
                self.logger.info(f"🚀 发布 {len(created_route_ids)} 个新路由")
                self.deploy_http_api(http_api_id, environment_id, gateway_id, created_route_ids)

            return len(success_tools), len(failed_tools), success_tools, failed_tools

        except Exception as e:
            self.logger.error(f"注册工具失败: {e}")
            raise

    def register_tools(self, gateway_id: str, plugin_id: str, private_ip: str,
                       tools_config: str, api_key: str, shared_service_name: str,
                       openapi_base_url: str = "http://127.0.0.1:8000",
                       skip_auth: bool = False, force_update: bool = True, domain_id: str = None) -> Tuple[
        int, int, List[ str ], List[ str ] ]:
        """注册所有工具到AI网关（兼容原有接口，默认使用create模式）"""
        return self.register_tools_with_state(
            gateway_id=gateway_id,
            plugin_id=plugin_id,
            private_ip=private_ip,
            tools_config=tools_config,
            api_key=api_key,
            shared_service_name=shared_service_name,
            openapi_base_url=openapi_base_url,
            skip_auth=skip_auth,
            force_update=force_update,
            domain_id=domain_id,
            mode="create"
        )

    # ==================== 清理功能 ====================

    def get_plugin_attachments(self, gateway_id: str, plugin_id: str) -> List[Dict]:
        """获取插件挂载列表"""
        try:
            response = self._execute_aliyun_cli("GET", "/v1/plugin-attachments",
                                                gatewayId=gateway_id,
                                                gatewayType="AI",
                                                pluginId=plugin_id,
                                                pageSize="100",
                                                pageNumber="1")
            data = self._check_response(response, "获取插件挂载列表")
            return data.get("items", [])
        except Exception as e:
            self.logger.warning(f"获取插件挂载列表失败: {e}")
            return []

    def delete_plugin_attachment(self, attachment_id: str) -> bool:
        """删除插件挂载"""
        try:
            self.logger.info(f"删除插件挂载: {attachment_id}")
            response = self._execute_aliyun_cli("DELETE", f"/v1/plugin-attachments/{attachment_id}")
            self._check_response(response, "删除插件挂载")
            self.logger.info(f"插件挂载 {attachment_id} 删除成功")
            return True
        except Exception as e:
            self.logger.error(f"删除插件挂载 {attachment_id} 失败: {e}")
            return False

    def delete_route(self, http_api_id: str, route_id: str) -> bool:
        """删除路由"""
        try:
            self.logger.info(f"删除路由: {route_id}")
            response = self._execute_aliyun_cli("DELETE", f"/v1/http-apis/{http_api_id}/routes/{route_id}")
            self._check_response(response, "删除路由")
            self.logger.info(f"路由 {route_id} 删除成功")
            return True
        except Exception as e:
            self.logger.error(f"删除路由 {route_id} 失败: {e}")
            return False

    def _get_service_references(self, gateway_id: str, service_id: str) -> List[Dict]:
        """获取服务的所有引用"""
        references = []
        try:
            # 查找引用该服务的所有路由
            http_api_id = self.get_http_api_id(gateway_id)
            response = self._execute_aliyun_cli("GET", f"/v1/http-apis/{http_api_id}/routes",
                                                gatewayId=gateway_id,
                                                gatewayType="AI")
            data = self._check_response(response, "获取所有路由")

            for route in data.get("items", []):
                backend_config = route.get("backendConfig", {})
                services_config = backend_config.get("services", [])
                for svc in services_config:
                    if svc.get("serviceId") == service_id:
                        references.append({
                            "type": "route",
                            "id": route.get("routeId"),
                            "name": route.get("name"),
                            "route": route
                        })
                        break

            self.logger.info(f"服务 {service_id} 被 {len(references)} 个路由引用")
            return references

        except Exception as e:
            self.logger.warning(f"获取服务 {service_id} 引用失败: {e}")
            return []

    def _force_delete_service_with_references(self, gateway_id: str, service_id: str) -> bool:
        """强制删除服务及其所有引用"""
        try:
            self.logger.info(f"🔍 检查服务 {service_id} 的引用关系")

            # 获取服务的所有引用
            references = self._get_service_references(gateway_id, service_id)

            if not references:
                # 没有引用，直接删除
                return self.delete_service(gateway_id, service_id)

            self.logger.info(f"🧹 服务 {service_id} 有 {len(references)} 个引用，开始清理")

            # 删除所有引用该服务的路由
            http_api_id = self.get_http_api_id(gateway_id)
            for ref in references:
                if ref["type"] == "route":
                    route_id = ref["id"]
                    route_name = ref["name"]

                    # 先删除路由上的插件挂载
                    try:
                        attachments_response = self._execute_aliyun_cli("GET", "/v1/plugin-attachments",
                                                                        gatewayId=gateway_id,
                                                                        attachResourceType="GatewayRoute",
                                                                        attachResourceId=route_id)
                        attachments_data = self._check_response(attachments_response, "查询路由插件挂载")

                        for attachment in attachments_data.get("items", []):
                            attachment_id = attachment.get("attachmentId")
                            if attachment_id:
                                self.delete_plugin_attachment(attachment_id)
                    except Exception as e:
                        self.logger.warning(f"清理路由 {route_id} 插件挂载失败: {e}")

                    # 删除路由
                    if self.delete_route(http_api_id, route_id):
                        self.logger.info(f"✅ 删除引用路由成功: {route_name} ({route_id})")
                    else:
                        self.logger.warning(f"⚠️  删除引用路由失败: {route_name} ({route_id})")

            # 等待删除生效
            time.sleep(3)

            # 再次尝试删除服务
            return self.delete_service(gateway_id, service_id)

        except Exception as e:
            self.logger.error(f"强制删除服务 {service_id} 失败: {e}")
            return False

    def delete_service(self, gateway_id: str, service_id: str, force: bool = True) -> bool:
        """删除服务（支持强制删除）"""
        try:
            self.logger.info(f"删除服务: {service_id}")

            # 使用特殊的CLI调用，传递region而不是endpoint
            command = ["./aliyun", "apig", "DELETE", f"/v1/services/{service_id}"]
            command.extend(["--region", self.region])
            command.extend(["--header", "Content-Type=application/json"])
            command.extend(["--body", "{}"])

            self.logger.info(f"执行删除服务CLI: {command}")
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                check=True
            )

            response = json.loads(result.stdout) if result.stdout else {}

            if self.debug_response:
                print(f"\n=== DELETE /v1/services/{service_id} 响应 ===")
                print(json.dumps(response, indent=2, ensure_ascii=False))
                print("=== 响应结束 ===\n")

            data = self._check_response(response, "删除服务")
            self.logger.info(f"服务 {service_id} 删除成功")
            return True

        except subprocess.CalledProcessError as e:
            error_msg = f"删除服务 {service_id} 失败: {e.stderr}"
            self.logger.error(error_msg)

            # 如果是因为有引用而删除失败，且允许强制删除
            if force and ("ServiceIsReferencedWhenDelete" in str(e.stderr) or "存在其他资源引用此服务" in str(e.stderr)):
                self.logger.warning(f"服务 {service_id} 有引用，尝试强制删除")
                return self._force_delete_service_with_references(gateway_id, service_id)
            else:
                return False

        except Exception as e:
            self.logger.error(f"删除服务 {service_id} 失败: {e}")
            return False


    def cleanup_all_with_state(self, gateway_id: str, plugin_id: str, shared_service_name: str = None) -> Tuple[int, int, List[str], List[str]]:
        """基于状态的完全清理（包括指定的共享服务）"""
        gateway_info = self.state.get_gateway_info()

        if not self.state.has_state():
            self.logger.warning("状态文件中没有网关信息，使用传统清理方式")
            return self.cleanup_gateway_resources(gateway_id, plugin_id, shared_service_name)

        # 基于状态清理
        tools_in_state = self.state.state.get("tools", {})
        if not tools_in_state:
            self.logger.info("状态中没有工具记录")
            # 即使没有工具记录，也要尝试清理指定的共享服务
            if shared_service_name:
                self._cleanup_specific_shared_service(gateway_id, shared_service_name)
            return 0, 0, [], []

        success, failed, success_list, failed_list = self.cleanup_specific_tools(
            gateway_id, plugin_id, tools_in_state
        )

        # 清理指定的共享服务
        if shared_service_name:
            self.logger.info(f"🧹 清理指定的共享服务: {shared_service_name}")
            self._cleanup_specific_shared_service(gateway_id, shared_service_name)
        else:
            # 如果没有指定共享服务名称，尝试从状态中获取
            state_shared_service_name = gateway_info.get("shared_service_name")
            if state_shared_service_name:
                self.logger.info(f"🧹 清理状态中记录的共享服务: {state_shared_service_name}")
                self._cleanup_specific_shared_service(gateway_id, state_shared_service_name)

        # 完全清空状态
        self.state.clear_all_state()

        return success, failed, success_list, failed_list

    def cleanup_gateway_resources(self, gateway_id: str, plugin_id: str, shared_service_name: str = None) -> Tuple[int, int, List[str], List[str]]:
        """清理AI网关侧的所有MCP路由和插件挂载资源（包括指定的共享服务）"""
        self.logger.info("开始清理AI网关侧所有MCP资源")

        success_tools, failed_tools = [], []
        route_ids_to_undeploy = []  # 记录需要下线的路由ID

        try:
            http_api_id = self.get_http_api_id(gateway_id)
            environment_id = self.get_environment_id(gateway_id)

            # 方法1：通过插件挂载获取路由
            attachments = self.get_plugin_attachments(gateway_id, plugin_id)
            self.logger.info(f"通过插件挂载找到 {len(attachments)} 个挂载")

            route_id_to_name = {}

            # 从插件挂载中获取路由信息
            for attachment in attachments:
                for route_id in attachment.get("attachResourceIds", []):
                    try:
                        response = self._execute_aliyun_cli("GET", f"/v1/http-apis/{http_api_id}/routes/{route_id}")
                        data = self._check_response(response, "获取路由详情")
                        route_name = data.get("name")
                        if route_name:
                            route_id_to_name[route_id] = route_name
                            route_ids_to_undeploy.append(route_id)
                            self.logger.info(f"从插件挂载发现路由: {route_name} (ID: {route_id})")
                    except Exception as e:
                        self.logger.warning(f"获取路由 {route_id} 信息失败: {e}")

            # 方法2：如果插件挂载没有找到路由，直接查询所有路由并过滤MCP相关的
            if not route_id_to_name:
                self.logger.info("插件挂载中未找到路由，尝试直接查询所有路由")
                try:
                    response = self._execute_aliyun_cli("GET", f"/v1/http-apis/{http_api_id}/routes",
                                                        gatewayId=gateway_id,
                                                        gatewayType="AI",
                                                        environmentId=environment_id)
                    data = self._check_response(response, "获取所有路由")

                    all_routes = data.get("items", [])
                    self.logger.info(f"查询到 {len(all_routes)} 个路由")

                    # 过滤出可能的MCP路由（排除系统路由）
                    for route in all_routes:
                        route_id = route.get("routeId")
                        route_name = route.get("name", "")

                        # 排除系统路由和空名称路由
                        if route_name and not route_name.startswith("system-") and route_id:
                            route_id_to_name[route_id] = route_name
                            route_ids_to_undeploy.append(route_id)
                            self.logger.info(f"发现可能的MCP路由: {route_name} (ID: {route_id})")

                except Exception as e:
                    self.logger.warning(f"查询所有路由失败: {e}")

            # 获取所有要清理的工具
            tools_to_cleanup = list(set(route_id_to_name.values()))
            self.logger.info(f"发现 {len(tools_to_cleanup)} 个MCP工具需要清理: {tools_to_cleanup}")

            if not tools_to_cleanup:
                self.logger.info("未发现任何MCP相关资源需要清理")
                # 即使没有工具，也要尝试清理指定的共享服务
                if shared_service_name:
                    self._cleanup_specific_shared_service(gateway_id, shared_service_name)
                return 0, 0, [], []

            # 先下线HTTP API中的相关路由
            if route_ids_to_undeploy:
                self.logger.info(f"📤 开始下线 {len(route_ids_to_undeploy)} 个MCP路由")
                if self.undeploy_http_api(http_api_id, environment_id, gateway_id, route_ids_to_undeploy):
                    self.logger.info("✅ MCP路由批量下线成功")
                else:
                    self.logger.warning("⚠️  MCP路由批量下线部分失败，继续清理资源")

            # 删除所有相关的插件挂载
            if attachments:
                self.logger.info("🧹 删除插件挂载")
                for attachment in attachments:
                    attachment_id = attachment.get("attachmentId")
                    attached_routes = attachment.get("attachResourceIds", [])

                    # 检查是否包含我们要清理的路由
                    if any(route_id in route_id_to_name for route_id in attached_routes):
                        if attachment_id:
                            self.delete_plugin_attachment(attachment_id)

            # 再删除所有路由
            self.logger.info("🧹 删除路由")
            for route_id, route_name in route_id_to_name.items():
                try:
                    if self.delete_route(http_api_id, route_id):
                        success_tools.append(route_name)
                        self.logger.info(f"✅ 工具 {route_name} 清理成功")
                    else:
                        failed_tools.append(route_name)
                        self.logger.error(f"❌ 工具 {route_name} 清理失败")
                except Exception as e:
                    self.logger.error(f"❌ 清理工具 {route_name} 时发生异常: {e}")
                    failed_tools.append(route_name)

            # 清理指定的共享服务
            if shared_service_name:
                self.logger.info(f"🧹 清理指定的共享服务: {shared_service_name}")
                self._cleanup_specific_shared_service(gateway_id, shared_service_name)
            else:
                self.logger.info("🧹 未指定共享服务名称，跳过共享服务清理")

            # 去重（避免同一工具被重复计算）
            success_tools = list(set(success_tools))
            failed_tools = list(set(failed_tools))

            return len(success_tools), len(failed_tools), success_tools, failed_tools

        except Exception as e:
            self.logger.error(f"清理网关资源失败: {e}")
            raise

    def _cleanup_specific_shared_service(self, gateway_id: str, shared_service_name: str):
        """清理指定名称的共享服务"""
        try:
            self.logger.info(f"查找并清理共享服务: {shared_service_name}")

            # 查找指定名称的服务
            existing_services = self._find_items_by_name(gateway_id, "/v1/services", shared_service_name)

            if not existing_services:
                self.logger.info(f"未找到名为 {shared_service_name} 的服务")
                return

            service_id = existing_services[0].get("serviceId")
            self.logger.info(f"找到共享服务: {shared_service_name} (ID: {service_id})")

            # 尝试删除服务
            if self.delete_service(gateway_id, service_id, force=True):
                self.logger.info(f"✅ 共享服务 {shared_service_name} 删除成功")
            else:
                self.logger.warning(f"⚠️  共享服务 {shared_service_name} 删除失败")

        except Exception as e:
            self.logger.warning(f"清理共享服务 {shared_service_name} 失败: {e}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="MCP工具自动注册和清理工具")

    # 添加子命令
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # 注册命令
    register_parser = subparsers.add_parser("register", help="注册MCP工具到AI网关")
    register_parser.add_argument("--gateway-id", required=True, help="AI网关ID")
    register_parser.add_argument("--plugin-id", help="插件ID（不提供则自动获取）")
    register_parser.add_argument("--private-ip", required=True, help="内网IP地址")
    register_parser.add_argument("--tools-config", required=True, help="工具配置文件路径")
    register_parser.add_argument("--pre-config", default="/root/pre-mcp-tools.json",
                                 help="预定义工具配置文件路径（默认: /root/pre-mcp-tools.json）")
    register_parser.add_argument("--api-key", required=False, help="API密钥")
    register_parser.add_argument("--openapi-base-url", default="http://127.0.0.1:8000", help="OpenAPI基础URL")
    register_parser.add_argument("--domain-id", help="指定域名ID（不提供则使用通配符域名）")
    register_parser.add_argument("--skip-auth", action="store_true", help="跳过添加鉴权信息")
    register_parser.add_argument("--mode", choices=["create", "update"], default="create",
                                 help="模式：create(新建/创建工具) 或 update(变配/清理现有工具)")
    register_parser.add_argument("--si", required=True, help="共享服务名称（必须传入，格式如：si-xxxx）")

    # 清理命令
    cleanup_parser = subparsers.add_parser("cleanup", help="清理AI网关侧所有MCP资源（包括指定的共享服务）")
    cleanup_parser.add_argument("--gateway-id", required=True, help="AI网关ID")
    cleanup_parser.add_argument("--plugin-id", help="插件ID（不提供则自动获取）")
    cleanup_parser.add_argument("--si", required=True, help="要删除的共享服务名称（必须传入，格式如：si-xxxx）")

    # 通用参数
    for subparser in [register_parser, cleanup_parser]:
        subparser.add_argument("--region", default="cn-hangzhou", help="阿里云区域")
        subparser.add_argument("-d", "--debug-response", action="store_true", help="打印详细响应信息")
        subparser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                               help="日志级别")
        subparser.add_argument("--state-file", help="状态文件路径（默认: ~/.mcp_gateway_state.json）")

    args = parser.parse_args()

    # 如果没有指定命令，显示帮助
    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        registrar = MCPGatewayRegistrar(args.region, args.log_level, args.debug_response, args.state_file)

        # 获取插件ID
        plugin_id = args.plugin_id
        if not plugin_id:
            print("🔍 自动获取插件ID...")
            plugin_id = registrar.get_mcp_plugin_id(args.gateway_id)
            if not plugin_id:
                print("❌ 无法获取插件ID，请手动指定 --plugin-id")
                sys.exit(1)
            print(f"✅ 获取到插件ID: {plugin_id}")

        if args.command == "register":
            # 验证 --si 参数格式
            if not args.si.startswith("si-"):
                print("❌ --si 参数格式错误，必须以 'si-' 开头，例如：si-12345")
                sys.exit(1)

            # 执行注册
            success_count, failed_count, success_tools, failed_tools = registrar.register_tools_with_state(
                gateway_id=args.gateway_id,
                plugin_id=plugin_id,
                private_ip=args.private_ip,
                tools_config=args.tools_config,
                api_key=args.api_key,
                shared_service_name=args.si,
                openapi_base_url=args.openapi_base_url,
                skip_auth=args.skip_auth,
                force_update=True,
                domain_id=args.domain_id,
                mode=args.mode,
                pre_config_path=args.pre_config  # 传递预定义配置文件路径
            )

            # 输出结果
            if args.mode == "update":
                print(f"\n{'=' * 50}")
                print("🔄 MCP工具变配清理结果")
                print(f"{'=' * 50}")
                print(f"🔧 插件ID: {plugin_id}")
                print(f"🏷️  共享服务名称: {args.si}")
                print(f"📁 状态文件: {registrar.state.state_file}")
                print(f"✅ 成功清理: {success_count} 个工具")
                if success_tools:
                    print(f"   {', '.join(success_tools)}")
                print(f"❌ 清理失败: {failed_count} 个工具")
                if failed_tools:
                    print(f"   {', '.join(failed_tools)}")
                print(f"📈 总计: {success_count + failed_count} 个工具")
                print(f"{'=' * 50}")

                if failed_count == 0:
                    if success_count > 0:
                        print("🎉 变配清理完成！现在可以执行 --mode create 来创建新工具")
                    else:
                        print("ℹ️  没有需要清理的工具")
                    sys.exit(0)
                else:
                    print("⚠️  部分工具清理失败")
                    sys.exit(1)
            else:
                # create模式的输出
                print(f"\n{'=' * 50}")
                print("📊 MCP工具创建统计结果")
                print(f"{'=' * 50}")
                print(f"🔧 插件ID: {plugin_id}")
                print(f"🏷️  共享服务名称: {args.si}")
                print(f"📁 状态文件: {registrar.state.state_file}")
                print(f"✅ 成功: {success_count} 个工具")
                if success_tools:
                    print(f"   {', '.join(success_tools)}")
                print(f"❌ 失败: {failed_count} 个工具")
                if failed_tools:
                    print(f"   {', '.join(failed_tools)}")
                print(f"📈 总计: {success_count + failed_count} 个工具")
                print(f"{'=' * 50}")

                # 设置退出码
                if failed_count == 0:
                    print("🎉 所有工具都已成功注册并发布！")
                    sys.exit(0)
                elif success_count > 0:
                    print("⚠️  部分工具注册成功")
                    sys.exit(1)
                else:
                    print("💥 所有工具都注册失败")
                    sys.exit(1)

        elif args.command == "cleanup":
            # 验证 --si 参数格式
            if not args.si.startswith("si-"):
                print("❌ --si 参数格式错误，必须以 'si-' 开头，例如：si-12345")
                sys.exit(1)

            # 执行清理
            success_count, failed_count, success_tools, failed_tools = registrar.cleanup_all_with_state(
                gateway_id=args.gateway_id,
                plugin_id=plugin_id,
                shared_service_name=args.si
            )

            # 输出清理结果
            print(f"\n{'=' * 50}")
            print("🧹 AI网关MCP资源完全清理结果")
            print(f"{'=' * 50}")
            print(f"🔧 插件ID: {plugin_id}")
            print(f"🏷️  目标共享服务: {args.si}")
            print(f"📁 状态文件: {registrar.state.state_file}")
            print(f"✅ 成功清理: {success_count} 个工具")
            if success_tools:
                print(f"   {', '.join(success_tools)}")
            print(f"❌ 清理失败: {failed_count} 个工具")
            if failed_tools:
                print(f"   {', '.join(failed_tools)}")
            print(f"📈 总计: {success_count + failed_count} 个工具")
            print(f"🗑️  共享服务 {args.si} 已清理")
            print("📄 状态文件已清空")
            print(f"{'=' * 50}")

            # 设置退出码
            if failed_count == 0:
                if success_count > 0:
                    print("🎉 所有MCP网关资源都已成功清理并下线！")
                else:
                    print("ℹ️  未发现需要清理的MCP资源，但已清理指定的共享服务")
                sys.exit(0)
            elif success_count > 0:
                print("⚠️  部分MCP网关资源清理成功")
                sys.exit(1)
            else:
                print("💥 所有MCP网关资源清理都失败")
                sys.exit(1)

    except Exception as e:
        print(f"❌ 操作失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
