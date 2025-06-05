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
from typing import List, Dict, Any, Optional, Tuple
import argparse
import sys


class MCPGatewayRegistrar:
    """MCP工具自动注册到阿里云AI网关的工具类"""

    def __init__(self, region: str = "cn-hangzhou", log_level: str = "INFO", debug_response: bool = False):
        self.region = region
        self.debug_response = debug_response
        self.logger = self._setup_logger(log_level)

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
        command = ["./aliyun", "apig", method,endpoint, "--endpoint", f"apig.{self.region}.aliyuncs.com"]
        # 添加参数
        for key, value in params.items():
            if value is not None:
                command.extend([f"--{key}", str(value)])

        # 添加请求体
        if body:
            command.extend(["--body", json.dumps(body)])

        command.extend(["--header", "Content-Type=application/json;"])
        try:
            self.logger.info(f"执行CLI: {method} {endpoint}")
            # 使用兼容Python 3.6的写法
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

    def get_mcp_plugin_id(self, gateway_id: str) -> Optional[str]:
        """获取MCP服务器插件ID"""
        self.logger.info("获取MCP插件ID")
        response = self._execute_aliyun_cli("GET", "/v1/plugins",
                                            gatewayType="AI",
                                            includeBuiltinAiGateway="true",
                                            pageNumber="0",
                                            pageSize="10")

        data = self._check_response(response, "获取插件列表")
        for item in data.get("items", []):
            if item.get("pluginClassInfo", {}).get("name") == "mcp-server":
                plugin_id = item.get("pluginId")
                self.logger.info(f"找到MCP插件ID: {plugin_id}")
                return plugin_id

        self.logger.warning("未找到mcp-server插件")
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

    def ensure_domain(self, gateway_id: str) -> str:
        """确保通配符域名存在"""
        # 先查询现有域名，使用nameLike参数
        try:
            response = self._execute_aliyun_cli("GET", "/v1/domains",
                                                gatewayType="AI",
                                                nameLike="*",
                                                pageSize="10",
                                                pageNumber="1")
            data = self._check_response(response, "查询域名列表")

            # 查找通配符域名
            for domain in data.get("items", []):
                if domain.get("name") == "*":
                    domain_id = domain.get("domainId")
                    self.logger.info(f"域名已存在，ID: {domain_id}")
                    return domain_id
        except Exception as e:
            self.logger.warning(f"查询域名列表失败: {e}")

        # 如果没找到，尝试创建新域名
        self.logger.info("创建通配符域名")
        try:
            response = self._execute_aliyun_cli("POST", "/v1/domains",
                                                {"name": "*", "protocol": "HTTP", "gatewayType": "AI"})
            data = self._check_response(response, "创建域名")
            domain_id = data.get("domainId")
            self.logger.info(f"域名创建成功，ID: {domain_id}")
            return domain_id
        except RuntimeError as e:
            # 如果创建失败且是因为域名已存在，重新查询
            if "Conflict.DomainExisted" in str(e) or "域名*已存在" in str(e):
                self.logger.warning("域名创建失败：域名已存在，重新查询")
                try:
                    response = self._execute_aliyun_cli("GET", "/v1/domains",
                                                        gatewayId=gateway_id,
                                                        gatewayType="AI",
                                                        nameLike="*",
                                                        pageSize="10",
                                                        pageNumber="1")
                    data = self._check_response(response, "重新查询域名列表")

                    for domain in data.get("items", []):
                        if domain.get("name") == "*":
                            domain_id = domain.get("domainId")
                            self.logger.info(f"重新查询找到域名，ID: {domain_id}")
                            return domain_id

                    raise RuntimeError("域名已存在但无法查询到对应的域名ID")
                except Exception as query_e:
                    raise RuntimeError(f"域名已存在但重新查询失败: {query_e}")
            else:
                raise

    def ensure_service(self, gateway_id: str, tool_name: str, private_ip: str) -> str:
        """确保服务存在"""
        # 检查现有服务
        existing_services = self._find_items_by_name(gateway_id, "/v1/services", tool_name)
        if existing_services:
            service_id = existing_services[0].get("serviceId")
            self.logger.info(f"服务 {tool_name} 已存在，ID: {service_id}")
            return service_id

        # 创建新服务
        self.logger.info(f"创建服务: {tool_name}")
        body = {
            "gatewayId": gateway_id,
            "sourceType": "VIP",
            "serviceConfigs": [{"name": tool_name, "addresses": [f"{private_ip}:8000"]}]
        }
        response = self._execute_aliyun_cli("POST", "/v1/services", body)
        data = self._check_response(response, "创建服务")

        service_ids = data.get("serviceIds", [])
        if not service_ids:
            raise RuntimeError("创建服务成功但未返回服务ID")

        service_id = service_ids[0]
        self.logger.info(f"服务创建成功，ID: {service_id}")
        return service_id

    def ensure_route(self, http_api_id: str, gateway_id: str, environment_id: str,
                     tool_name: str, domain_id: str, service_id: str, force_update: bool) -> Tuple[str, bool]:
        """确保路由存在，返回(route_id, need_update_config)"""
        # 检查现有路由
        existing_routes = self._find_items_by_name(gateway_id, f"/v1/http-apis/{http_api_id}/routes",
                                                   tool_name, environmentId=environment_id)
        if existing_routes:
            route_id = existing_routes[0].get("routeId")
            self.logger.info(f"路由 {tool_name} 已存在，ID: {route_id}")
            # 路由已存在时，总是需要尝试创建/更新插件挂载
            return route_id, True

        # 创建新路由
        self.logger.info(f"创建路由: {tool_name}")
        body = {
            "domainIds": [domain_id],
            "environmentId": environment_id,
            "match": {"path": {"type": "Prefix", "value": f"/{tool_name}"}},
            "backendConfig": {"scene": "SingleService", "services": [{"serviceId": service_id}]},
            "mcpRouteConfig": {"protocol": "HTTP"},
            "name": tool_name,
            "description": tool_name
        }
        response = self._execute_aliyun_cli("POST", f"/v1/http-apis/{http_api_id}/routes", body)
        data = self._check_response(response, "创建路由")

        route_id = data.get("routeId")
        if not route_id:
            raise RuntimeError("创建路由成功但未返回路由ID")

        self.logger.info(f"路由创建成功，ID: {route_id}")
        return route_id, True

    def generate_mcp_config(self, tool_name: str, openapi_base_url: str, api_key: str, skip_auth: bool) -> str:
        """生成MCP配置并返回base64编码"""
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
            # 使用兼容的写法
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
        for tool in config.get('tools', []):
            if 'requestTemplate' in tool:
                # 修改URL
                if 'url' in tool['requestTemplate']:
                    original_url = tool['requestTemplate']['url']
                    path = original_url.split('/', 3)[-1] if '/' in original_url else original_url.lstrip('/')
                    tool['requestTemplate']['url'] = f"{{{{.config.baseUrl}}}}/{path}"

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

    def update_plugin_attachment(self, gateway_id: str, plugin_id: str, route_id: str, plugin_config: str):
        """创建插件挂载"""
        self.logger.info("创建插件挂载")
        body = {
            "pluginId": plugin_id,
            "pluginConfig": plugin_config,
            "attachResourceType": "GatewayRoute",
            "attachResourceIds": [route_id],
            "gatewayId": gateway_id
        }

        try:
            response = self._execute_aliyun_cli("POST", "/v1/plugin-attachments", body)
            self._check_response(response, "创建插件挂载")
            self.logger.info("插件挂载创建成功")
        except RuntimeError as e:
            # 如果是因为已存在而失败，记录警告但不抛出异常
            if "已存在" in str(e) or "exist" in str(e).lower():
                self.logger.warning(f"插件挂载可能已存在: {e}")
            else:
                raise

    def extract_tools_from_config(self, config_path: str) -> List[str]:
        """从配置文件提取工具列表"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            tools = list(config.get('mcpServers', {}).keys())
            self.logger.info(f"找到 {len(tools)} 个工具: {', '.join(tools)}")
            return tools
        except Exception as e:
            raise RuntimeError(f"解析配置文件失败: {e}")

    def register_tools(self, gateway_id: str, plugin_id: str, private_ip: str,
                       tools_config: str, api_key: str, openapi_base_url: str = "http://127.0.0.1:8000",
                       skip_auth: bool = False, force_update: bool = False) -> Tuple[int, int, List[str], List[str]]:
        """注册所有工具到AI网关"""
        self.logger.info("开始注册MCP工具到AI网关")

        success_tools, failed_tools = [], []

        try:
            # 获取基础信息
            http_api_id = self.get_http_api_id(gateway_id)
            domain_id = self.ensure_domain(gateway_id)
            environment_id = self.get_environment_id(gateway_id)
            tools = self.extract_tools_from_config(tools_config)

            # 处理每个工具
            for tool in tools:
                try:
                    self.logger.info(f"处理工具: {tool}")

                    # 确保服务和路由存在
                    service_id = self.ensure_service(gateway_id, tool, private_ip)
                    route_id, need_update = self.ensure_route(http_api_id, gateway_id, environment_id,
                                                              tool, domain_id, service_id, force_update)

                    # 更新插件配置
                    if need_update:
                        plugin_config = self.generate_mcp_config(tool, openapi_base_url, api_key, skip_auth)
                        self.update_plugin_attachment(gateway_id, plugin_id, route_id, plugin_config)
                        self.logger.info(f"工具 {tool} 配置已更新")
                    else:
                        self.logger.info(f"工具 {tool} 跳过配置更新")

                    success_tools.append(tool)

                except Exception as e:
                    self.logger.error(f"处理工具 {tool} 失败: {e}")
                    failed_tools.append(tool)

            return len(success_tools), len(failed_tools), success_tools, failed_tools

        except Exception as e:
            self.logger.error(f"注册工具失败: {e}")
            raise


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="MCP工具自动注册到阿里云AI网关")
    parser.add_argument("--gateway-id", required=True, help="AI网关ID")
    parser.add_argument("--plugin-id", help="插件ID（不提供则自动获取）")
    parser.add_argument("--private-ip", required=True, help="内网IP地址")
    parser.add_argument("--tools-config", required=True, help="工具配置文件路径")
    parser.add_argument("--api-key", required=False, help="API密钥")
    parser.add_argument("--openapi-base-url", default="http://127.0.0.1:8000", help="OpenAPI基础URL")
    parser.add_argument("--region", default="cn-hangzhou", help="阿里云区域")
    parser.add_argument("--skip-auth", action="store_true", help="跳过添加鉴权信息")
    parser.add_argument("--force-update", action="store_true", help="强制更新配置")
    parser.add_argument("-d", "--debug-response", action="store_true", help="打印详细响应信息")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"], help="日志级别")

    args = parser.parse_args()

    try:
        registrar = MCPGatewayRegistrar(args.region, args.log_level, args.debug_response)

        # 获取插件ID
        plugin_id = args.plugin_id
        if not plugin_id:
            print("🔍 自动获取插件ID...")
            plugin_id = registrar.get_mcp_plugin_id(args.gateway_id)
            if not plugin_id:
                print("❌ 无法获取插件ID，请手动指定 --plugin-id")
                sys.exit(1)
            print(f"✅ 获取到插件ID: {plugin_id}")

        # 执行注册
        success_count, failed_count, success_tools, failed_tools = registrar.register_tools(
            gateway_id=args.gateway_id,
            plugin_id=plugin_id,
            private_ip=args.private_ip,
            tools_config=args.tools_config,
            api_key=args.api_key,
            openapi_base_url=args.openapi_base_url,
            skip_auth=args.skip_auth,
            force_update=args.force_update
        )

        # 输出结果
        print(f"\n{'=' * 50}")
        print("📊 MCP工具注册统计结果")
        print(f"{'=' * 50}")
        print(f"🔧 插件ID: {plugin_id}")
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
            print("🎉 所有工具都已成功注册！")
            sys.exit(0)
        elif success_count > 0:
            print("⚠️  部分工具注册成功")
            sys.exit(1)
        else:
            print("💥 所有工具都注册失败")
            sys.exit(1)

    except Exception as e:
        print(f"❌ 操作失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
