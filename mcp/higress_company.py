#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import subprocess
import tempfile
import traceback
import logging
import base64
import yaml
import requests
from typing import List, Dict, Any, Optional, Tuple
import argparse
import sys


class MCPGatewayRegistrar:
    """MCP工具自动注册到阿里云AI网关的工具类"""

    def __init__(self, region: str = "cn-hangzhou", log_level: str = "INFO", debug_response: bool = False):
        """
        初始化注册器

        Args:
            region: 阿里云区域
            log_level: 日志级别
            debug_response: 是否打印详细响应信息
        """
        self.region = region
        self.debug_response = debug_response
        self.logger = self._setup_logger(log_level)

    def _setup_logger(self, log_level: str) -> logging.Logger:
        """设置日志记录器"""
        logger = logging.getLogger("MCPGatewayRegistrar")
        logger.setLevel(getattr(logging, log_level.upper()))

        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        return logger

    def _log_caller_info(self):
        """记录调用者信息"""
        import inspect
        frame = inspect.currentframe().f_back
        self.logger.debug(f"调用方法: {frame.f_code.co_name}")

    def _execute_aliyun_cli(self, command: List[str]) -> Dict[str, Any]:
        """
        执行阿里云CLI命令

        Args:
            command: CLI命令列表

        Returns:
            Dict: 命令执行结果
        """
        self._log_caller_info()
        try:
            self.logger.info(f"执行阿里云CLI命令: {' '.join(command)}")

            # 兼容Python 3.6的写法
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                check=True
            )

            if result.stdout:
                response = json.loads(result.stdout)

                # 根据debug_response参数决定是否打印详细响应
                if self.debug_response:
                    print(f"\n=== CLI响应详情 ===")
                    print(json.dumps(response, indent=2, ensure_ascii=False))
                    print("=== 响应详情结束 ===\n")
                else:
                    self.logger.debug(f"CLI响应: {json.dumps(response, indent=2, ensure_ascii=False)}")

                return response
            else:
                self.logger.warning("CLI命令无输出")
                return {}

        except subprocess.CalledProcessError as e:
            self.logger.error(f"CLI命令执行失败: {e}")
            self.logger.error(f"错误输出: {e.stderr}")

            # 在debug模式下也打印错误详情
            if self.debug_response:
                print(f"\n=== CLI错误详情 ===")
                print(f"返回码: {e.returncode}")
                print(f"标准输出: {e.stdout}")
                print(f"错误输出: {e.stderr}")
                print("=== 错误详情结束 ===\n")

            raise RuntimeError(f"CLI命令执行失败: {e.stderr}")
        except json.JSONDecodeError as e:
            self.logger.error(f"解析CLI响应失败: {e}")
            self.logger.error(f"原始输出: {result.stdout}")

            # 在debug模式下打印解析错误详情
            if self.debug_response:
                print(f"\n=== JSON解析错误详情 ===")
                print(f"解析错误: {e}")
                print(f"原始输出: {result.stdout}")
                print("=== 解析错误详情结束 ===\n")

            raise RuntimeError(f"解析CLI响应失败: {e}")

    def check_service_exists(self, gateway_id: str, server_code: str) -> Optional[Dict[str, Any]]:
        """
        检查服务是否已存在

        Args:
            gateway_id: 网关ID
            server_code: 服务代码

        Returns:
            Optional[Dict]: 如果存在返回服务信息，否则返回None
        """
        self._log_caller_info()
        self.logger.info(f"检查服务是否存在: {server_code}")

        command = [
            "./aliyun", "apig", "GET", "/v1/services",
            "--region", self.region,
            "--gatewayId", gateway_id,
            "--gatewayType", "AI",  # 添加这个参数
            "--name", server_code,
            "--header", "Content-Type=application/json;"
        ]

        try:
            response = self._execute_aliyun_cli(command)

            if response.get("code") != "Ok":
                self.logger.warning(f"查询服务失败: {response}")
                return None

            items = response.get("data", {}).get("items", [])
            if items:
                service = items[0]  # 取第一个匹配的服务
                self.logger.info(f"服务 {server_code} 已存在，服务ID: {service.get('serviceId')}")
                return service
            else:
                self.logger.info(f"服务 {server_code} 不存在")
                return None

        except Exception as e:
            self.logger.warning(f"检查服务存在性时出错: {str(e)}")
            return None

    def check_route_exists(self, http_api_id: str, gateway_id: str, server_code: str) -> Optional[Dict[str, Any]]:
        """
        检查路由是否已存在

        Args:
            http_api_id: HTTP API ID
            gateway_id: 网关ID
            server_code: 服务代码

        Returns:
            Optional[Dict]: 如果存在返回路由信息，否则返回None
        """
        self._log_caller_info()
        self.logger.info(f"检查路由是否存在: {server_code}")

        command = [
            "./aliyun", "apig", "GET", f"/v1/http-apis/{http_api_id}/routes",
            "--region", self.region,
            "--name", server_code,
            "--gatewayId", gateway_id,
            "--gatewayType", "AI",  # 添加这个参数
            "--header", "Content-Type=application/json;"
        ]

        try:
            response = self._execute_aliyun_cli(command)

            if response.get("code") != "Ok":
                self.logger.warning(f"查询路由失败: {response}")
                return None

            items = response.get("data", {}).get("items", [])
            if items:
                route = items[0]  # 取第一个匹配的路由
                self.logger.info(f"路由 {server_code} 已存在，路由ID: {route.get('routeId')}")
                return route
            else:
                self.logger.info(f"路由 {server_code} 不存在")
                return None

        except Exception as e:
            self.logger.warning(f"检查路由存在性时出错: {str(e)}")
            return None

    def list_plugin_attachments_by_route(self, gateway_id: str, route_id: str) -> Optional[Dict[str, Any]]:
        """
        根据路由ID查询插件挂载

        Args:
            gateway_id: 网关ID
            route_id: 路由ID

        Returns:
            Optional[Dict]: 如果存在返回插件挂载信息，否则返回None
        """
        self._log_caller_info()
        self.logger.info(f"查询路由 {route_id} 的插件挂载")

        command = [
            "./aliyun", "apig", "GET", "/v1/plugin-attachments",
            "--region", self.region,
            "--gatewayId", gateway_id,
            "--gatewayType", "AI",  # 添加这个参数
            "--header", "Content-Type=application/json;"
        ]

        try:
            response = self._execute_aliyun_cli(command)

            if response.get("code") != "Ok":
                self.logger.warning(f"查询插件挂载失败: {response}")
                return None

            items = response.get("data", {}).get("items", [])

            # 查找匹配的插件挂载
            for attachment in items:
                attach_resource_ids = attachment.get("attachResourceIds", [])
                if route_id in attach_resource_ids:
                    self.logger.info(f"找到路由 {route_id} 的插件挂载: {attachment.get('pluginAttachmentId')}")
                    return attachment

            self.logger.info(f"路由 {route_id} 没有找到插件挂载")
            return None

        except Exception as e:
            self.logger.warning(f"查询插件挂载时出错: {str(e)}")
            return None

    def update_plugin_attachment(self, plugin_attachment_id: str, plugin_config: str,
                                 route_id: str, enable: bool = True) -> str:
        """
        更新插件挂载

        Args:
            plugin_attachment_id: 插件挂载ID
            plugin_config: 插件配置（base64编码）
            route_id: 路由ID
            enable: 是否启用

        Returns:
            str: 插件挂载ID
        """
        self._log_caller_info()
        self.logger.info(f"更新插件挂载: {plugin_attachment_id}")

        body = {
            "attachResourceIds": [route_id],
            "pluginConfig": plugin_config,
            "enable": enable
        }

        command = [
            "./aliyun", "apig", "PUT", f"/v1/plugin-attachments/{plugin_attachment_id}",
            "--region", self.region,
            "--header", "Content-Type=application/json;",
            "--body", json.dumps(body)
        ]

        response = self._execute_aliyun_cli(command)

        if response.get("code") != "Ok":
            raise RuntimeError(f"更新插件挂载失败: {response}")

        self.logger.info(f"插件挂载更新成功，插件挂载ID: {plugin_attachment_id}")
        return plugin_attachment_id

    def list_http_apis(self, gateway_id: str) -> List[Dict[str, Any]]:
        """获取HTTP API列表，筛选MCP类型的API"""
        self._log_caller_info()
        self.logger.info(f"获取网关 {gateway_id} 的HTTP API列表")

        command = [
            "./aliyun", "apig", "GET", "/v1/http-apis",
            "--region", self.region,
            "--gatewayId", gateway_id,
            "--gatewayType", "AI",  # 添加这个参数
            "--header", "Content-Type=application/json;"
        ]

        response = self._execute_aliyun_cli(command)

        if response.get("code") != "Ok":
            raise RuntimeError(f"获取HTTP API列表失败: {response}")

        # 筛选MCP类型的API
        mcp_apis = []
        items = response.get("data", {}).get("items", [])

        for item in items:
            if item.get("type") == "MCP":
                versioned_apis = item.get("versionedHttpApis", [])
                for api in versioned_apis:
                    if api.get("type") == "MCP":
                        mcp_apis.append(api)

        self.logger.info(f"找到 {len(mcp_apis)} 个MCP类型的API")
        return mcp_apis

    def list_domains(self, gateway_id: str) -> List[Dict[str, Any]]:
        """
        获取域名列表

        Args:
            gateway_id: 网关ID

        Returns:
            List[Dict]: 域名列表
        """
        self._log_caller_info()
        self.logger.info(f"获取网关 {gateway_id} 的域名列表")

        command = [
            "./aliyun", "apig", "GET", "/v1/domains",
            "--region", self.region,
            "--gatewayId", gateway_id,
            "--gatewayType", "AI",
            "--header", "Content-Type=application/json;"
        ]

        try:
            response = self._execute_aliyun_cli(command)

            if response.get("code") != "Ok":
                self.logger.warning(f"查询域名列表失败: {response}")
                return []

            items = response.get("data", {}).get("items", [])
            self.logger.info(f"找到 {len(items)} 个现有域名")
            return items

        except Exception as e:
            self.logger.warning(f"查询域名列表时出错: {str(e)}")
            return []

    def create_domain(self, gateway_id: str) -> str:
        """
        创建域名（如果不存在的话）

        Args:
            gateway_id: 网关ID

        Returns:
            str: 域名ID
        """
        self._log_caller_info()
        self.logger.info("检查并创建域名")

        # 首先检查是否已存在通配符域名
        existing_domains = self.list_domains(gateway_id)
        for domain in existing_domains:
            domain_name = domain.get("name", "")
            if domain_name == "*":
                domain_id = domain.get("domainId")
                self.logger.info(f"域名 '*' 已存在，跳过创建，使用现有域名ID: {domain_id}")
                return domain_id

        # 如果不存在，则创建新域名
        self.logger.info("域名 '*' 不存在，创建新域名")

        body = {
            "name": "*",
            "protocol": "HTTP",
            "gatewayType": "AI"
        }

        command = [
            "./aliyun", "apig", "POST", "/v1/domains",
            "--region", self.region,
            "--header", "Content-Type=application/json;",
            "--body", json.dumps(body)
        ]

        try:
            response = self._execute_aliyun_cli(command)

            if response.get("code") != "Ok":
                # 检查是否是域名已存在的错误
                error_message = str(response)
                if "Conflict.DomainExisted" in error_message or "域名*已存在" in error_message:
                    self.logger.warning("域名创建失败：域名已存在，尝试重新查询现有域名")
                    # 重新查询域名列表，找到通配符域名
                    existing_domains = self.list_domains(gateway_id)
                    for domain in existing_domains:
                        domain_name = domain.get("name", "")
                        if domain_name == "*":
                            domain_id = domain.get("domainId")
                            self.logger.info(f"找到现有域名 '*'，域名ID: {domain_id}")
                            return domain_id

                    # 如果还是找不到，抛出异常
                    raise RuntimeError("域名已存在但无法查询到对应的域名ID")
                else:
                    raise RuntimeError(f"创建域名失败: {response}")

            domain_id = response.get("data", {}).get("domainId")
            if not domain_id:
                raise RuntimeError("创建域名成功但未返回域名ID")

            self.logger.info(f"域名创建成功，域名ID: {domain_id}")
            return domain_id

        except RuntimeError:
            # 重新抛出已知的运行时错误
            raise
        except Exception as e:
            # 处理其他异常，也尝试查询现有域名
            error_message = str(e)
            if "Conflict.DomainExisted" in error_message or "域名*已存在" in error_message:
                self.logger.warning("域名创建异常：域名已存在，尝试查询现有域名")
                existing_domains = self.list_domains(gateway_id)
                for domain in existing_domains:
                    domain_name = domain.get("name", "")
                    if domain_name == "*":
                        domain_id = domain.get("domainId")
                        self.logger.info(f"找到现有域名 '*'，域名ID: {domain_id}")
                        return domain_id

                raise RuntimeError("域名已存在但无法查询到对应的域名ID")
            else:
                raise RuntimeError(f"创建域名时发生未知错误: {str(e)}")

    def get_environment_id(self, gateway_id: str) -> str:
        """获取环境ID"""
        self._log_caller_info()
        self.logger.info(f"获取网关 {gateway_id} 的环境ID")

        command = [
            "./aliyun", "apig", "GET", "/v1/environments",
            "--region", self.region,
            "--gatewayId", gateway_id,
            "--gatewayType", "AI",
            "--header", "Content-Type=application/json;"
        ]

        response = self._execute_aliyun_cli(command)

        if response.get("code") != "Ok":
            raise RuntimeError(f"获取环境列表失败: {response}")

        items = response.get("data", {}).get("items", [])
        if not items:
            raise RuntimeError("未找到任何环境")

        # 获取默认环境
        default_env = None
        for item in items:
            if item.get("default", False):
                default_env = item
                break

        if not default_env:
            default_env = items[0]  # 如果没有默认环境，使用第一个

        environment_id = default_env.get("environmentId")
        if not environment_id:
            raise RuntimeError("未找到有效的环境ID")

        self.logger.info(f"环境ID: {environment_id}")
        return environment_id

    def extract_tools_from_config(self, config_path: str) -> List[str]:
        """从MCP配置文件中提取工具列表"""
        self._log_caller_info()
        self.logger.info(f"从配置文件提取工具列表: {config_path}")

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)

                if 'mcpServers' in config:
                    tools = list(config['mcpServers'].keys())
                    self.logger.info(f"从配置文件中找到 {len(tools)} 个工具: {', '.join(tools)}")
                    return tools
                else:
                    self.logger.warning("配置文件中未找到 mcpServers 部分")
                    return []

        except Exception as e:
            self.logger.error(f"解析配置文件失败: {str(e)}")
            self.logger.error(traceback.format_exc())
            raise RuntimeError(f"解析配置文件失败: {str(e)}")

    def fetch_openapi_spec(self, url: str) -> Dict[str, Any]:
        """获取OpenAPI规范"""
        self._log_caller_info()
        self.logger.info(f"获取OpenAPI规范: {url}")

        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()

            # 在debug模式下打印OpenAPI响应
            if self.debug_response:
                print(f"\n=== OpenAPI响应详情 ===")
                print(f"URL: {url}")
                print(f"状态码: {response.status_code}")
                print(f"响应内容: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
                print("=== OpenAPI响应详情结束 ===\n")

            return response.json()
        except Exception as e:
            self.logger.error(f"获取OpenAPI规范失败: {str(e)}")

            # 在debug模式下打印错误详情
            if self.debug_response:
                print(f"\n=== OpenAPI请求错误详情 ===")
                print(f"URL: {url}")
                print(f"错误: {str(e)}")
                print("=== OpenAPI请求错误详情结束 ===\n")

            raise RuntimeError(f"获取OpenAPI规范失败: {str(e)}")

    def create_service(self, gateway_id: str, server_code: str, private_ip: str) -> str:
        """创建服务"""
        self._log_caller_info()
        self.logger.info(f"创建服务: {server_code}")

        body = {
            "gatewayId": gateway_id,
            "sourceType": "VIP",
            "serviceConfigs": [{
                "name": server_code,
                "addresses": [f"{private_ip}:8000"]
            }]
        }

        command = [
            "./aliyun", "apig", "POST", "/v1/services",
            "--region", self.region,
            "--header", "Content-Type=application/json;",
            "--body", json.dumps(body)
        ]

        response = self._execute_aliyun_cli(command)

        if response.get("code") != "Ok":
            raise RuntimeError(f"创建服务失败: {response}")

        service_ids = response.get("data", {}).get("serviceIds", [])
        if not service_ids:
            raise RuntimeError("创建服务成功但未返回服务ID")

        service_id = service_ids[0]
        self.logger.info(f"服务创建成功，服务ID: {service_id}")
        return service_id

    def create_http_api_route(self, http_api_id: str, domain_id: str, server_code: str,
                              server_name: str, service_id: str, environment_id: str) -> str:
        """创建HTTP API路由"""
        self._log_caller_info()
        self.logger.info(f"创建HTTP API路由: {server_code}")

        body = {
            "domainIds": [domain_id],
            "environmentId": environment_id,
            "match": {
                "path": {
                    "type": "Prefix",
                    "value": f"/{server_code}"
                }
            },
            "backendConfig": {
                "scene": "SingleService",
                "services": [{
                    "serviceId": service_id
                }]
            },
            "mcpRouteConfig": {
                "protocol": "HTTP"
            },
            "name": server_code,
            "description": server_name
        }

        command = [
            "./aliyun", "apig", "POST", f"/v1/http-apis/{http_api_id}/routes",
            "--region", self.region,
            "--header", "Content-Type=application/json;",
            "--body", json.dumps(body)
        ]

        response = self._execute_aliyun_cli(command)

        if response.get("code") != "Ok":
            raise RuntimeError(f"创建HTTP API路由失败: {response}")

        route_id = response.get("data", {}).get("routeId")
        if not route_id:
            raise RuntimeError("创建路由成功但未返回路由ID")

        self.logger.info(f"路由创建成功，路由ID: {route_id}")
        return route_id

    def convert_openapi_to_mcp(self, json_file_path: str, server_name: str) -> str:
        """调用openapi-to-mcp工具将OpenAPI JSON转换为MCP YAML配置"""
        self._log_caller_info()
        if not os.path.isfile(json_file_path):
            self.logger.error(f"OpenAPI JSON 文件不存在: {json_file_path}")
            raise FileNotFoundError(f"文件不存在: {json_file_path}")

        # 创建临时目录存放输出文件
        temp_dir = tempfile.mkdtemp(prefix="higress_mcp_")
        output_file = os.path.join(temp_dir, f"{server_name}.yaml")

        self.logger.info(f"将 OpenAPI JSON 转换为 MCP YAML")
        self.logger.info(f"输入文件: {json_file_path}")
        self.logger.info(f"输出文件: {output_file}")

        try:
            # 检查工具是否可用
            try:
                self.logger.info("检查 openapi-to-mcp 工具是否可用")
                version_cmd = ["./openapi-to-mcp", "--version"]
                version_result = subprocess.run(
                    version_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True
                )
                if version_result.returncode != 0:
                    self.logger.warning("无法获取 openapi-to-mcp 版本，但将继续尝试使用该工具")
                    self.logger.debug(f"版本命令错误: {version_result.stderr}")
                else:
                    self.logger.info(f"openapi-to-mcp 版本: {version_result.stdout.strip()}")
            except FileNotFoundError:
                self.logger.error("找不到 openapi-to-mcp 工具，请确保已安装并在 PATH 中")
                raise RuntimeError("找不到 openapi-to-mcp 工具，请确保已安装并在 PATH 中")

            # 构建命令
            cmd = [
                "./openapi-to-mcp",
                "--input", json_file_path,
                "--output", output_file,
                "--server-name", server_name
            ]

            self.logger.info(f"执行命令: {' '.join(cmd)}")

            # 执行命令
            result = subprocess.run(
                cmd,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )

            # 记录命令输出
            if result.stdout:
                self.logger.debug(f"命令标准输出: {result.stdout}")
                if self.debug_response:
                    print(f"\n=== openapi-to-mcp 输出详情 ===")
                    print(f"标准输出: {result.stdout}")
                    print("=== openapi-to-mcp 输出详情结束 ===\n")

            if result.stderr:
                self.logger.debug(f"命令错误输出: {result.stderr}")
                if self.debug_response:
                    print(f"\n=== openapi-to-mcp 错误输出详情 ===")
                    print(f"错误输出: {result.stderr}")
                    print("=== openapi-to-mcp 错误输出详情结束 ===\n")

            # 检查文件是否生成
            if not os.path.exists(output_file):
                self.logger.error("转换失败: 未生成 YAML 文件")
                if result.stderr:
                    self.logger.error(f"错误信息: {result.stderr}")
                raise RuntimeError("转换失败: 未生成 YAML 文件")

            self.logger.info(f"成功将 OpenAPI 规范转换为 MCP 配置: {output_file}")

            # 在debug模式下打印生成的YAML内容
            if self.debug_response:
                try:
                    with open(output_file, 'r', encoding='utf-8') as f:
                        yaml_content = f.read()
                    print(f"\n=== 生成的MCP YAML内容 ===")
                    print(yaml_content)
                    print("=== MCP YAML内容结束 ===\n")
                except Exception as e:
                    print(f"无法读取生成的YAML文件: {e}")

            return output_file

        except subprocess.CalledProcessError as e:
            self.logger.error(f"转换失败 (返回码 {e.returncode})")
            if e.stdout:
                self.logger.error(f"标准输出: {e.stdout}")
            if e.stderr:
                self.logger.error(f"错误输出: {e.stderr}")
            self.logger.error(traceback.format_exc())
            raise RuntimeError(f"转换失败 (返回码 {e.returncode}): {e.stderr}")
        except Exception as e:
            self.logger.error(f"执行 openapi-to-mcp 时出错: {str(e)}")
            self.logger.error(f"异常类型: {type(e).__name__}")
            self.logger.error(traceback.format_exc())
            raise RuntimeError(f"执行 openapi-to-mcp 时出错: {str(e)}")

    def modify_mcp_yaml(self, yaml_path: str, api_key: str, base_url: str = "http://127.0.0.1:8000",
                        skip_auth: bool = False) -> str:
        """修改MCP YAML文件"""
        self._log_caller_info()
        self.logger.info(f"修改 MCP YAML 文件: {yaml_path}")

        if skip_auth:
            self.logger.info("跳过添加鉴权信息")

        try:
            # 读取原始 YAML
            with open(yaml_path, 'r', encoding='utf-8') as f:
                yaml_content = f.read()
                config = yaml.safe_load(yaml_content)

            # 在debug模式下打印修改前的YAML配置
            if self.debug_response:
                print(f"\n=== 修改前的YAML配置 ===")
                print(json.dumps(config, indent=2, ensure_ascii=False))
                print("=== 修改前的YAML配置结束 ===\n")

            # 确保 server 部分存在
            if 'server' not in config:
                self.logger.warning(f"YAML 文件 {yaml_path} 中未找到 'server' 部分")
                config['server'] = {}

            # 添加或更新 server.config 部分
            if 'config' not in config['server']:
                config['server']['config'] = {}

            # 设置 baseUrl (无论是否跳过鉴权都需要)
            config['server']['config']['baseUrl'] = base_url

            # 只有在不跳过鉴权时才设置 apikey
            if not skip_auth:
                config['server']['config']['apikey'] = api_key

            # 检查 tools 部分
            if 'tools' not in config:
                self.logger.warning(f"YAML 文件 {yaml_path} 中未找到 'tools' 部分")
                return yaml_path

            # 修改每个工具
            for tool in config['tools']:
                if 'requestTemplate' in tool:
                    # 修改 URL 使用模板变量 (无论是否跳过鉴权都需要)
                    if 'url' in tool['requestTemplate']:
                        original_url = tool['requestTemplate']['url']

                        # 提取路径部分
                        if original_url.startswith('http://') or original_url.startswith('https://'):
                            # 绝对 URL，提取路径部分
                            path_parts = original_url.split('/', 3)
                            if len(path_parts) >= 4:
                                path = path_parts[3]  # 提取路径部分
                            else:
                                path = ""
                        else:
                            # 相对路径，直接使用
                            path = original_url.lstrip('/')

                        # 构建新 URL 使用模板变量
                        new_url = "{{.config.baseUrl}}/" + path
                        tool['requestTemplate']['url'] = new_url
                        self.logger.debug(f"URL 已修改: {original_url} -> {new_url}")

                    # 只有在不跳过鉴权时才更新或添加授权头
                    if not skip_auth:
                        # 更新或添加授权头，使用模板变量
                        if 'headers' not in tool['requestTemplate']:
                            tool['requestTemplate']['headers'] = []

                        # 检查是否已有授权头
                        has_auth = False
                        for header in tool['requestTemplate']['headers']:
                            if header.get('key') == 'Authorization':
                                has_auth = True
                                header['value'] = "Bearer {{.config.apikey}}"
                                self.logger.debug("已更新现有授权头")
                                break

                        # 如果没有授权头，添加一个
                        if not has_auth:
                            tool['requestTemplate']['headers'].append({
                                'key': 'Authorization',
                                'value': "Bearer {{.config.apikey}}"
                            })
                            self.logger.debug("已添加授权头")

            # 在debug模式下打印修改后的YAML配置
            if self.debug_response:
                print(f"\n=== 修改后的YAML配置 ===")
                print(json.dumps(config, indent=2, ensure_ascii=False))
                print("=== 修改后的YAML配置结束 ===\n")

            # 保存修改后的 YAML
            with open(yaml_path, 'w', encoding='utf-8') as f:
                try:
                    yaml.dump(config, f, allow_unicode=True, default_flow_style=False)
                except TypeError:
                    yaml.dump(config, f, default_flow_style=False)

            # 在debug模式下打印最终的YAML文件内容
            if self.debug_response:
                with open(yaml_path, 'r', encoding='utf-8') as f:
                    final_yaml_content = f.read()
                print(f"\n=== 最终YAML文件内容 ===")
                print(final_yaml_content)
                print("=== 最终YAML文件内容结束 ===\n")

            self.logger.info(f"MCP YAML 文件已成功修改: {yaml_path}")
            return yaml_path

        except Exception as e:
            self.logger.error(f"修改 YAML 文件失败: {str(e)}")
            self.logger.error(traceback.format_exc())
            # 返回原始文件路径，不中断流程
            return yaml_path

    def create_plugin_attachment(self, plugin_id: str, plugin_config: str, route_id: str) -> str:
        """创建插件附件"""
        self._log_caller_info()
        self.logger.info(f"创建插件附件，路由ID: {route_id}")

        body = {
            "pluginId": plugin_id,
            "pluginConfig": plugin_config,
            "attachResourceType": "GatewayRoute",
            "attachResourceIds": [route_id]
        }

        # 在debug模式下打印插件配置
        if self.debug_response:
            print(f"\n=== 插件挂载请求体 ===")
            print(f"插件ID: {plugin_id}")
            print(f"路由ID: {route_id}")
            print(f"插件配置长度: {len(plugin_config)} 字符")
            # 解码base64以显示实际配置内容
            try:
                decoded_config = base64.b64decode(plugin_config).decode('utf-8')
                print(f"解码后的插件配置:")
                print(decoded_config)
            except Exception as e:
                print(f"无法解码插件配置: {e}")
            print("=== 插件挂载请求体结束 ===\n")

        command = [
            "./aliyun", "apig", "POST", "/v1/plugin-attachments",
            "--region", self.region,
            "--header", "Content-Type=application/json;",
            "--body", json.dumps(body)
        ]

        response = self._execute_aliyun_cli(command)

        if response.get("code") != "200" and response.get("code") != "Ok":
            raise RuntimeError(f"创建插件附件失败: {response}")

        # 处理嵌套的响应结构
        data = response.get("data", {})
        if isinstance(data, dict) and "data" in data:
            plugin_attachment_id = data["data"].get("pluginAttachmentId")
        else:
            plugin_attachment_id = data.get("pluginAttachmentId")

        if not plugin_attachment_id:
            raise RuntimeError("创建插件附件成功但未返回插件附件ID")

        self.logger.info(f"插件附件创建成功，插件附件ID: {plugin_attachment_id}")
        return plugin_attachment_id

    def register_tools(self, gateway_id: str, plugin_id: str, private_ip: str,
                       tools_config: str, api_key: str, openapi_base_url: str = "http://127.0.0.1:8000",
                       skip_auth: bool = False, force_update: bool = False):
        """
        注册所有工具到AI网关（支持创建和更新）

        Args:
            gateway_id: 网关ID
            plugin_id: 插件ID
            private_ip: 内网IP
            tools_config: 工具配置文件路径
            api_key: API密钥
            openapi_base_url: OpenAPI基础URL
            skip_auth: 是否跳过鉴权
            force_update: 是否强制更新所有资源
        """
        self._log_caller_info()
        self.logger.info("开始注册MCP工具到AI网关")

        try:
            # 1. 获取MCP类型的HTTP API
            mcp_apis = self.list_http_apis(gateway_id)
            if not mcp_apis:
                raise RuntimeError("未找到MCP类型的HTTP API")

            http_api_id = mcp_apis[0].get("httpApiId")
            if not http_api_id:
                raise RuntimeError("未找到有效的HTTP API ID")

            self.logger.info(f"使用HTTP API ID: {http_api_id}")

            # 2. 创建域名（通常只需要创建一次）
            domain_id = self.create_domain(gateway_id)

            # 3. 获取环境ID
            environment_id = self.get_environment_id(gateway_id)

            # 4. 提取工具列表
            tools = self.extract_tools_from_config(tools_config)
            if not tools:
                self.logger.warning("未找到任何工具，退出注册流程")
                return

            # 5. 为每个工具执行注册流程
            for tool in tools:
                try:
                    self.logger.info(f"处理工具: {tool}")

                    # 使用工具名称作为服务名称
                    server_name = tool
                    server_code = tool

                    # 初始化变量
                    need_update_config = False

                    # a. 检查服务是否已存在
                    existing_service = self.check_service_exists(gateway_id, server_code)
                    if existing_service:
                        service_id = existing_service.get("serviceId")
                        self.logger.info(f"服务 {server_code} 已存在，跳过创建，使用现有服务ID: {service_id}")

                        # 检查地址是否匹配
                        existing_addresses = existing_service.get("addresses", [])
                        expected_address = f"{private_ip}:8000"
                        if expected_address not in existing_addresses:
                            self.logger.warning(
                                f"服务 {server_code} 的地址不匹配。期望: {expected_address}, 实际: {existing_addresses}")
                            if force_update:
                                self.logger.info("强制更新模式，但由于没有更新服务API，将继续使用现有服务")
                    else:
                        # 创建新服务
                        service_id = self.create_service(gateway_id, server_code, private_ip)

                    # b. 检查路由是否已存在
                    existing_route = self.check_route_exists(http_api_id, gateway_id, server_code)
                    if existing_route:
                        route_id = existing_route.get("routeId")
                        self.logger.info(f"路由 {server_code} 已存在，跳过后续的路由创建和配置转换")

                        # 检查是否需要更新插件挂载
                        existing_attachment = self.list_plugin_attachments_by_route(gateway_id, route_id)
                        if existing_attachment and not force_update:
                            self.logger.info(f"工具 {tool} 的插件挂载已存在，跳过配置更新")
                            self.logger.info(f"  - 服务ID: {service_id}")
                            self.logger.info(f"  - 路由ID: {route_id}")
                            self.logger.info(f"  - 插件挂载ID: {existing_attachment.get('pluginAttachmentId')}")
                            continue
                        elif existing_attachment and force_update:
                            self.logger.info(f"强制更新模式，将更新插件挂载配置")
                            # 需要重新生成配置并更新
                            need_update_config = True
                        else:
                            self.logger.info(f"路由 {route_id} 没有插件挂载，将创建新的插件挂载")
                            need_update_config = True
                    else:
                        # 创建新路由
                        route_id = self.create_http_api_route(http_api_id, domain_id, server_code, server_name,
                                                              service_id, environment_id)
                        need_update_config = True

                    # c. 如果需要更新配置，则执行配置转换和更新
                    if need_update_config:
                        # 获取工具的 OpenAPI 规范
                        tool_spec_url = f"{openapi_base_url}/{tool}/openapi.json"
                        self.logger.info(f"获取工具 OpenAPI 规范: {tool_spec_url}")
                        tool_spec = self.fetch_openapi_spec(tool_spec_url)

                        # 将规范保存为临时 JSON 文件
                        temp_dir = tempfile.mkdtemp(prefix=f"higress_mcp_{tool}_")
                        json_file_path = os.path.join(temp_dir, f"{tool}.json")

                        with open(json_file_path, 'w', encoding='utf-8') as f:
                            json.dump(tool_spec, f, ensure_ascii=False, indent=2)

                        self.logger.info(f"工具 OpenAPI 规范保存到: {json_file_path}")

                        # d. 转换OpenAPI到MCP配置
                        mcp_yaml_path = self.convert_openapi_to_mcp(json_file_path, server_name)

                        # e. 修改MCP YAML文件
                        self.logger.info(f"修改 MCP YAML 文件，添加授权头和修改 URL 前缀")
                        mcp_yaml_path = self.modify_mcp_yaml(
                            mcp_yaml_path,
                            api_key,
                            base_url=openapi_base_url,
                            skip_auth=skip_auth
                        )

                        # f. 读取YAML文件并进行base64编码
                        with open(mcp_yaml_path, 'r', encoding='utf-8') as f:
                            yaml_content = f.read()

                        plugin_config = base64.b64encode(yaml_content.encode('utf-8')).decode('utf-8')

                        # g. 创建或更新插件附件
                        existing_attachment = self.list_plugin_attachments_by_route(gateway_id, route_id)
                        if existing_attachment:
                            # 更新现有插件挂载
                            plugin_attachment_id = existing_attachment.get("pluginAttachmentId")
                            self.update_plugin_attachment(plugin_attachment_id, plugin_config, route_id)
                            operation = "更新"
                        else:
                            # 创建新插件挂载
                            plugin_attachment_id = self.create_plugin_attachment(plugin_id, plugin_config, route_id)
                            operation = "创建"

                        self.logger.info(f"工具 {tool} 处理完成 ({operation})")
                    else:
                        self.logger.info(f"工具 {tool} 处理完成 (跳过)")

                    self.logger.info(f"  - 服务ID: {service_id}")
                    self.logger.info(f"  - 路由ID: {route_id}")

                except Exception as e:
                    self.logger.error(f"处理工具 {tool} 失败: {str(e)}")
                    self.logger.error(traceback.format_exc())
                    # 继续处理下一个工具
                    continue

            self.logger.info("所有工具处理流程完成")

        except Exception as e:
            self.logger.error(f"注册工具失败: {str(e)}")
            self.logger.error(traceback.format_exc())
            raise


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="MCP工具自动注册到阿里云AI网关（支持创建和更新）")
    parser.add_argument("--gateway-id", required=True, help="AI网关ID")
    parser.add_argument("--plugin-id", required=True, help="插件ID")
    parser.add_argument("--private-ip", required=True, help="内网IP地址")
    parser.add_argument("--tools-config", required=True, help="工具配置文件路径")
    parser.add_argument("--api-key", required=True, help="API密钥")
    parser.add_argument("--openapi-base-url", default="http://127.0.0.1:8000",
                        help="OpenAPI基础URL (默认: http://127.0.0.1:8000)")
    parser.add_argument("--region", default="cn-hangzhou", help="阿里云区域 (默认: cn-hangzhou)")
    parser.add_argument("--skip-auth", action="store_true", help="跳过添加鉴权信息")
    parser.add_argument("--force-update", action="store_true", help="强制更新插件挂载配置")
    parser.add_argument("-d", "--debug-response", action="store_true", help="打印详细的API响应信息")
    parser.add_argument("--log-level", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                        help="日志级别 (默认: INFO)")

    args = parser.parse_args()

    try:
        registrar = MCPGatewayRegistrar(
            region=args.region,
            log_level=args.log_level,
            debug_response=args.debug_response
        )

        registrar.register_tools(
            gateway_id=args.gateway_id,
            plugin_id=args.plugin_id,
            private_ip=args.private_ip,
            tools_config=args.tools_config,
            api_key=args.api_key,
            openapi_base_url=args.openapi_base_url,
            skip_auth=args.skip_auth,
            force_update=args.force_update
        )

        print("✅ MCP工具注册/更新完成")

    except Exception as e:
        print(f"❌ 操作失败: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
