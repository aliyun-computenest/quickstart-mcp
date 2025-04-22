#!/usr/bin/env python3
import os
import sys
import argparse
import subprocess
import requests
from requests.exceptions import HTTPError, RequestException, ConnectionError, Timeout
import yaml
import logging
import tempfile
import json
import traceback
import inspect


class HigressClient:


    def init_system(self, api_key, domain):
        """
        初始化系统，在登录前调用

        Args:
            api_key: API密钥，用作管理员密码
        """

        self._log_caller_info()

        payload = {
            "adminUser": {
                "name": "admin",
                "displayName": "admin",
                "password": api_key
            }
        }

        self.logger.info("初始化系统")
        url = f"{self.base_url}/system/init"
        self.logger.debug(f"初始化URL: {url}")
        self.logger.debug(f"初始化载荷: {json.dumps(payload, ensure_ascii=False)}")

        try:
            response = self.session.post(url, json=payload, timeout=30)
            self.logger.debug(f"初始化响应状态码: {response.status_code}")

            try:
                response_data = response.json()
                self.logger.debug(f"初始化响应内容: {json.dumps(response_data, indent=2, ensure_ascii=False)}")

                # 检查响应是否成功
                if response.status_code == 200:
                    self.logger.info("系统初始化成功")
                    return True
                else:
                    # 如果状态码不是200，记录错误但不抛出异常
                    # 因为系统可能已经初始化过
                    error_msg = response_data.get('message', '未知错误')
                    if "initialized" in error_msg:
                        self.logger.info("系统已经初始化过，跳过初始化")
                        return True
                    self.logger.warning(f"系统初始化返回非200状态码: {response.status_code}, 消息: {error_msg}")
                    return False

            except json.JSONDecodeError:
                self.logger.warning(f"初始化响应不是有效的 JSON: {response.text[:1000]}")
                # 不抛出异常，继续尝试登录
                return False

        except Exception as e:
            self.logger.warning(f"系统初始化请求失败: {str(e)}")
            self.logger.debug(traceback.format_exc())
            # 不抛出异常，继续尝试登录
            return False

    def __init__(self, domain, base_url="http://localhost:8001", username="admin", apikey="admin", verbose=False, ):
        """
        初始化 Higress 客户端

        Args:
            base_url: Higress API 的基础 URL
            username: 登录用户名
            apikey: 登录密码
            verbose: 是否启用详细日志
        """
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.logger = self._setup_logger(verbose)
        self.verbose = verbose

        self.logger.info(f"初始化 HigressClient: base_url={self.base_url}, username={username}")

        # 测试连接
        self.check_and_create_higress_config(domain)
        self._test_connection()
        self.init_system(apikey, domain)

        # 自动登录
        try:
            self.login(username, apikey)
            self.logger.info(f"已成功连接并登录到 Higress 服务: {base_url}")
        except Exception as e:
            self.logger.error(f"登录失败: {str(e)}")
            raise

    def _setup_logger(self, verbose):
        """设置日志记录器"""
        logger = logging.getLogger("HigressClient")

        # 清除现有的处理程序
        if logger.handlers:
            for handler in logger.handlers:
                logger.removeHandler(handler)

        # 根据是否启用详细日志设置日志级别
        logger_level = logging.DEBUG if verbose else logging.INFO
        logger.setLevel(logger_level)

        # 控制台处理程序
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logger_level)  # 使用相同的日志级别
        console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

        # 文件处理程序 - 详细日志，包括文件名和行号
        file_handler = logging.FileHandler('higress_client.log')
        file_handler.setLevel(logging.DEBUG)  # 文件中仍然记录所有DEBUG日志，便于排查问题
        file_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s() - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

        return logger

    def _log_caller_info(self, level=logging.DEBUG):
        """记录调用者信息，帮助跟踪调用栈"""
        frame = inspect.currentframe().f_back
        filename = frame.f_code.co_filename
        lineno = frame.f_lineno
        function = frame.f_code.co_name
        self.logger.log(level, f"执行位置: {os.path.basename(filename)}:{lineno} in {function}()")

    def _test_connection(self):
        """测试与 Higress 服务的连接"""
        self._log_caller_info()
        try:
            self.logger.info(f"测试连接到 {self.base_url}/health")
            response = self.session.get(f"{self.base_url}/health", timeout=5)
            self.logger.debug(f"健康检查响应: 状态码={response.status_code}")

            if response.status_code == 200:
                self.logger.info(f"成功连接到 Higress 服务: {self.base_url}")
            else:
                self.logger.warning(f"Higress 服务返回非 200 状态码: {response.status_code}")
                self.logger.debug(f"响应内容: {response.text[:500]}")
        except ConnectionError as e:
            self.logger.error(f"无法连接到 Higress 服务 {self.base_url}: {str(e)}")
            raise ConnectionError(f"无法连接到 Higress 服务: {str(e)}")
        except Timeout as e:
            self.logger.error(f"连接到 Higress 服务超时: {str(e)}")
            raise Timeout(f"连接超时: {str(e)}")
        except Exception as e:
            self.logger.error(f"连接测试时发生未知错误: {str(e)}")
            self.logger.error(f"异常类型: {type(e).__name__}")
            self.logger.error(traceback.format_exc())
            raise

    def login(self, username, password):
        """
        用户登录 - 只要返回了 displayName 就表示登录成功
        """
        self._log_caller_info()
        payload = {
            "username": username,
            "password": password,
            "autoLogin": True
        }

        self.logger.info(f"尝试登录用户: {username}")
        url = f"{self.base_url}/session/login"
        self.logger.debug(f"登录URL: {url}")
        self.logger.debug(f"登录载荷: {json.dumps(payload, ensure_ascii=False)}")

        try:
            response = self.session.post(url, json=payload, timeout=30)
            self.logger.debug(f"登录响应状态码: {response.status_code}")

            try:
                response_data = response.json()
                self.logger.debug(f"登录响应内容: {json.dumps(response_data, indent=2, ensure_ascii=False)}")

                # 检查是否包含 displayName，这表示登录成功
                if response_data['displayName']:
                    display_name = response_data['displayName']
                    self.logger.info(f"用户 {username} 登录成功，显示名称: {display_name}")
                    return response_data
                else:
                    error_msg = response_data.get('message', '未知错误')
                    self.logger.error(f"登录失败: {error_msg}")
                    raise RuntimeError(f"登录失败: {error_msg}")

            except json.JSONDecodeError:
                self.logger.error(f"登录响应不是有效的 JSON: {response.text[:1000]}")
                raise RuntimeError(f"登录响应解析失败: 不是有效的 JSON")

            except Exception as e:
                self.logger.error(f"登录过程中出错: {str(e)}")
                self.logger.error(traceback.format_exc())
                raise RuntimeError(f"登录过程中出错: {str(e)}")

        except Exception as e:
            self.logger.error(f"登录请求失败: {str(e)}")
            self.logger.error(traceback.format_exc())

            # 尝试诊断登录问题
            try:
                test_response = self.session.get(f"{self.base_url}/session/login", timeout=5)
                self.logger.info(f"登录页面访问测试: 状态码={test_response.status_code}")
                if test_response.status_code != 200:
                    self.logger.error(f"无法访问登录页面，状态码: {test_response.status_code}")
                    self.logger.debug(f"响应内容: {test_response.text[:1000]}")
            except Exception as test_e:
                self.logger.error(f"测试登录页面时出错: {str(test_e)}")

            raise RuntimeError(f"登录失败: {str(e)}")

    def _handle_request(self, method, endpoint, **kwargs):
        """统一请求处理方法"""
        self._log_caller_info()
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        self.logger.info(f"发送 {method} 请求到 {url}")

        # 记录请求体 (如果存在)
        if 'json' in kwargs:
            self.logger.debug(f"请求体: {json.dumps(kwargs['json'], indent=2, ensure_ascii=False)}")

        try:
            # 设置合理的超时时间
            if 'timeout' not in kwargs:
                kwargs['timeout'] = 30

            self.logger.debug(f"请求参数: {kwargs}")

            response = self.session.request(method, url, **kwargs)

            # 记录响应状态和内容
            self.logger.info(f"响应状态码: {response.status_code}")

            try:
                # 尝试解析为 JSON
                response_data = response.json()
                self.logger.debug(f"响应内容: {json.dumps(response_data, indent=2, ensure_ascii=False)}")
                return response_data
            except json.JSONDecodeError:
                # 如果不是 JSON，记录文本
                self.logger.debug(f"响应内容 (非 JSON): {response.text[:1000]}")

        except json.JSONDecodeError as e:
            self.logger.error(f"响应解析错误: {str(e)}")
            self.logger.error(f"原始响应: {response.text[:1000]}")
            self.logger.error(traceback.format_exc())
            raise RuntimeError(f"响应解析错误: {str(e)}")

        except HTTPError as e:
            error_msg = f"HTTP Error ({e.response.status_code}): "
            try:
                error_data = e.response.json()
                error_detail = error_data.get('message', str(e))
                self.logger.error(f"错误响应内容: {json.dumps(error_data, indent=2, ensure_ascii=False)}")
                if 'data' in error_data:
                    self.logger.error(f"错误详情: {error_data['data']}")
            except:
                error_detail = e.response.text[:1000] if e.response.text else str(e)
                self.logger.error(f"非JSON错误响应: {e.response.text[:1000]}")

            self.logger.error(f"{error_msg}{error_detail}")
            self.logger.error(traceback.format_exc())
            raise RuntimeError(error_msg + error_detail)

        except ConnectionError as e:
            self.logger.error(f"连接错误: {str(e)}")
            self.logger.error(traceback.format_exc())
            raise RuntimeError(f"连接错误: {str(e)}")

        except Timeout as e:
            self.logger.error(f"请求超时: {str(e)}")
            self.logger.error(traceback.format_exc())
            raise RuntimeError(f"请求超时: {str(e)}")

        except RequestException as e:
            self.logger.error(f"请求失败: {str(e)}")
            self.logger.error(traceback.format_exc())
            raise RuntimeError(f"请求失败: {str(e)}")

        except Exception as e:
            self.logger.error(f"未知错误: {str(e)}")
            self.logger.error(f"异常类型: {type(e).__name__}")
            self.logger.error(traceback.format_exc())
            raise RuntimeError(f"未知错误: {str(e)}")

    def create_computenest_consumer(self, bearer_token):
        """创建/更新固定结构Consumer"""
        self._log_caller_info()
        payload = {
            "name": "computenest",
            "credentials": [{
                "values": [bearer_token],
                "source": "BEARER",
                "type": "key-auth"
            }],
            "version": 0
        }

        try:
            self.logger.info("尝试创建 Consumer: computenest")
            result = self._handle_request('POST', '/v1/consumers', json=payload)
            if result["name"]:
                self.logger.info(f"成功创建 Consumer: computenest")
                return result
        except RuntimeError as e:
            if "already exist" in str(e).lower():
                self.logger.info("Consumer 已存在，尝试更新...")
                try:
                    return self._update_consumer(payload)
                except Exception as update_e:
                    self.logger.error(f"更新 Consumer 失败: {str(update_e)}")
                    self.logger.error(traceback.format_exc())
                    raise RuntimeError(f"更新 Consumer 失败: {str(update_e)}")
            self.logger.error(f"创建 Consumer 失败: {str(e)}")
            raise

    def _update_consumer(self, payload):
        """更新已存在的Consumer"""
        self._log_caller_info()
        try:
            # 获取当前版本
            self.logger.info(f"获取 Consumer {payload['name']} 当前版本")
            current = self._handle_request('GET', f"/v1/consumers/{payload['name']}")
            payload["version"] = current.get("version", 0) + 1
            self.logger.info(f"更新 Consumer {payload['name']} 到版本 {payload['version']}")
            result = self._handle_request('PUT', f"/v1/consumers/{payload['name']}", json=payload)
            self.logger.info(f"成功更新 Consumer: {payload['name']}")
            return result
        except Exception as e:
            self.logger.error(f"更新 Consumer 时出错: {str(e)}")
            self.logger.error(traceback.format_exc())
            raise RuntimeError(f"更新 Consumer 失败: {str(e)}")

    def create_service_source(self, name, domain, domain_for_edit=None):
        """创建静态服务来源"""
        self._log_caller_info()

        # 确保域名包含端口号
        if ":" not in domain:
            domain = f"{domain}:8000"  # 使用端口 8000

        domain_for_edit = domain_for_edit or domain

        payload = {
            "type": "static",
            "name": name,
            "domainForEdit": domain_for_edit,
            "protocol": "http",
            "domain": domain,
            "port": 80,
            "sni": None
        }

        try:
            # 检查服务来源是否已存在
            try:
                self.logger.info(f"检查服务来源是否存在: {name}")
                existing = self._handle_request('GET', f"/v1/service-sources/{name}")
                if existing:
                    self.logger.info(f"服务来源 {name} 已存在，尝试更新...")
                    # 如果更新需要版本号，在更新方法中添加
                    return self._update_service_source(name, payload)
            except Exception as check_e:
                self.logger.info(f"服务来源 {name} 不存在，将创建新的")
                self.logger.debug(f"检查异常: {str(check_e)}")

            self.logger.info(f"创建服务来源: {name}, 域名: {domain}")
            self.logger.debug(f"请求体: {json.dumps(payload, indent=2, ensure_ascii=False)}")
            result = self._handle_request('POST', '/v1/service-sources', json=payload)
            self.logger.info(f"成功创建服务来源: {name}, 域名: {domain}")
            return result
        except Exception as e:
            self.logger.error(f"创建服务来源失败: {str(e)}")
            self.logger.error(traceback.format_exc())
            raise RuntimeError(f"创建服务来源失败: {str(e)}")

    def _update_service_source(self, name, payload):
        """更新已存在的服务来源"""
        self._log_caller_info()
        try:
            # 获取当前版本
            self.logger.info(f"获取服务来源 {name} 当前版本")
            current = self._handle_request('GET', f"/v1/service-sources/{name}")

            # 更新时需要添加版本号
            if "version" in current:
                # 确保版本是字符串或数字类型，根据API要求
                payload["version"] = current.get("version", 0) + 1

            self.logger.info(f"更新服务来源 {name} 到版本 {payload.get('version', '未知')}")
            self.logger.debug(f"更新请求体: {json.dumps(payload, indent=2, ensure_ascii=False)}")
            result = self._handle_request('PUT', f"/v1/service-sources/{name}", json=payload)
            self.logger.info(f"成功更新服务来源: {name}")
            return result
        except Exception as e:
            self.logger.error(f"更新服务来源时出错: {str(e)}")
            self.logger.error(traceback.format_exc())
            raise RuntimeError(f"更新服务来源失败: {str(e)}")

    def create_route(self, name, service_name):
        """创建路由"""
        self._log_caller_info()
        payload = {
            "name": name,
            "path": {
                "matchType": "PRE",
                "matchValue": f"/{service_name}",
                "caseSensitive": True
            },
            "authConfig": {
                "enabled": True,
                "allowedConsumers": ["computenest"]
            },
            "services": [{
                "name": f"{service_name}.static:80"
            }]
        }

        try:
            # 检查路由是否已存在
            try:
                self.logger.info(f"检查路由是否存在: {name}")
                existing = self._handle_request('GET', f"/v1/routes/{name}")
                if existing:
                    self.logger.info(f"路由 {name} 已存在，尝试更新...")
                    return self._update_route(name, payload)
            except Exception as check_e:
                self.logger.info(f"路由 {name} 不存在，将创建新的")
                self.logger.debug(f"检查异常: {str(check_e)}")

            self.logger.info(f"创建路由: {name}, 路径: /{service_name}")
            result = self._handle_request('POST', '/v1/routes', json=payload)
            self.logger.info(f"成功创建路由: {name}, 路径: /{service_name}")
            return result
        except Exception as e:
            self.logger.error(f"创建路由失败: {str(e)}")
            self.logger.error(traceback.format_exc())
            raise RuntimeError(f"创建路由失败: {str(e)}")

    def _update_route(self, name, payload):
        """更新已存在的路由"""
        self._log_caller_info()
        try:
            # 获取当前版本
            self.logger.info(f"获取路由 {name} 当前版本")
            current = self._handle_request('GET', f"/v1/routes/{name}")
            self.logger.info(f"************************: {current}")
            payload["version"] = current.get("data").get("version")
            self.logger.info(f"更新路由 {name} 版本 {payload['version']}")
            result = self._handle_request('PUT', f"/v1/routes/{name}", json=payload)
            self.logger.info(f"成功更新路由: {name}")
            return result
        except Exception as e:
            self.logger.error(f"更新路由时出错: {str(e)}")
            self.logger.error(traceback.format_exc())
            raise RuntimeError(f"更新路由失败: {str(e)}")

    def configure_mcp_plugin(self, route_name, yaml_config):
        """配置MCP插件"""
        self._log_caller_info()
        if isinstance(yaml_config, str) and os.path.isfile(yaml_config):
            # 如果提供的是文件路径，则加载文件内容
            try:
                self.logger.info(f"从文件加载 MCP 配置: {yaml_config}")
                with open(yaml_config, 'r', encoding='utf-8') as f:
                    config_data = yaml.safe_load(f)
                    self.logger.info(f"成功从文件加载 MCP 配置: {yaml_config}")
            except Exception as e:
                self.logger.error(f"无法加载配置文件 {yaml_config}: {str(e)}")
                self.logger.error(traceback.format_exc())
                raise ValueError(f"无法加载配置文件: {str(e)}")
        else:
            # 否则假设直接提供了配置数据
            self.logger.info("使用提供的配置数据")
            config_data = yaml_config

        try:
            # 尝试使用兼容性更好的方式转储 YAML
            try:
                # 首先尝试不使用 sort_keys 参数
                raw_config = yaml.dump(config_data, allow_unicode=True)
            except TypeError:
                # 如果还有问题，尝试最简单的调用
                raw_config = yaml.dump(config_data)

            # 注释掉打印YAML配置的部分
            # self.logger.debug(f"MCP 配置 YAML:\n{raw_config}")
        except yaml.YAMLError as e:
            self.logger.error(f"无效的 YAML 配置: {str(e)}")
            self.logger.error(traceback.format_exc())
            raise ValueError(f"无效的 YAML 配置: {str(e)}")

        payload = {
            "version": None,
            "scope": "ROUTE",
            "target": route_name,
            "targets": {"ROUTE": route_name},
            "pluginName": "mcp-server",
            "enabled": True,
            "rawConfigurations": raw_config
        }

        try:
            # 检查插件是否已存在
            try:
                self.logger.info(f"检查路由 {route_name} 的 MCP 插件是否存在")
                existing = self._handle_request('GET', f"/v1/routes/{route_name}/plugin-instances/mcp-server")
                if existing:
                    self.logger.info(f"路由 {route_name} 的 MCP 插件已存在，将更新配置...")
                    payload["version"] = existing.get("version", 0) + 1
                    self.logger.info(f"更新插件到版本 {payload['version']}")
            except Exception as check_e:
                self.logger.info(f"路由 {route_name} 没有 MCP 插件，将创建新的")
                self.logger.debug(f"检查异常: {str(check_e)}")

            self.logger.info(f"配置路由 {route_name} 的 MCP 插件")
            result = self._handle_request(
                'PUT',
                f"/v1/routes/{route_name}/plugin-instances/mcp-server",
                json=payload
            )
            self.logger.info(f"成功为路由 {route_name} 配置 MCP 插件")
            return result
        except Exception as e:
            self.logger.error(f"配置 MCP 插件失败: {str(e)}")
            self.logger.debug(f"插件配置负载: {json.dumps(payload, indent=2, ensure_ascii=False)}")
            self.logger.error(traceback.format_exc())
            raise RuntimeError(f"配置 MCP 插件失败: {str(e)}")

    def convert_openapi_to_mcp(self, json_file_path, server_name):
        """
        调用 openapi-to-mcp 工具将 OpenAPI JSON 转换为 MCP YAML 配置
        """
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
                # 使用 universal_newlines 替代 text 参数，兼容 Python 3.6
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

            # 执行命令 - 同样使用 universal_newlines 替代 text
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
            if result.stderr:
                self.logger.debug(f"命令错误输出: {result.stderr}")

            # 检查文件是否生成
            if not os.path.exists(output_file):
                self.logger.error("转换失败: 未生成 YAML 文件")
                if result.stderr:
                    self.logger.error(f"错误信息: {result.stderr}")
                raise RuntimeError("转换失败: 未生成 YAML 文件")

            self.logger.info(f"成功将 OpenAPI 规范转换为 MCP 配置: {output_file}")

            # 注释掉打印YAML内容的部分
            # try:
            #     with open(output_file, 'r', encoding='utf-8') as f:
            #         yaml_content = f.read()
            #         self.logger.debug(f"生成的 YAML 内容:\n{yaml_content}")
            # except Exception as e:
            #     self.logger.warning(f"无法读取生成的 YAML 文件: {str(e)}")

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

    def modify_mcp_yaml(self, yaml_path, api_key, base_url="http://127.0.0.1:8000"):
        """
        修改 MCP YAML 文件，将 API 密钥和基础 URL 放在 server.config 中，
        并在 requestTemplate 中使用模板变量引用它们

        Args:
            yaml_path: YAML 文件路径
            api_key: API 密钥
            base_url: 基础 URL 前缀

        Returns:
            str: 修改后的 YAML 文件路径
        """
        self._log_caller_info()
        self.logger.info(f"修改 MCP YAML 文件: {yaml_path}")

        try:
            # 读取原始 YAML
            with open(yaml_path, 'r', encoding='utf-8') as f:
                yaml_content = f.read()
                config = yaml.safe_load(yaml_content)

            # 确保 server 部分存在
            if 'server' not in config:
                self.logger.warning(f"YAML 文件 {yaml_path} 中未找到 'server' 部分")
                config['server'] = {}

            # 添加或更新 server.config 部分
            if 'config' not in config['server']:
                config['server']['config'] = {}

            # 设置 apikey 和 baseUrl
            config['server']['config']['apikey'] = api_key
            config['server']['config']['baseUrl'] = base_url

            # 检查 tools 部分
            if 'tools' not in config:
                self.logger.warning(f"YAML 文件 {yaml_path} 中未找到 'tools' 部分")
                return yaml_path

            # 修改每个工具
            for tool in config['tools']:
                if 'requestTemplate' in tool:
                    # 修改 URL 使用模板变量
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

            # 保存修改后的 YAML
            with open(yaml_path, 'w', encoding='utf-8') as f:
                # 使用兼容性更好的方式保存 YAML
                try:
                    yaml.dump(config, f, allow_unicode=True, default_flow_style=False)
                except TypeError:
                    # 如果上面的方法失败，尝试更简单的调用
                    yaml.dump(config, f, default_flow_style=False)

            self.logger.info(f"MCP YAML 文件已成功修改: {yaml_path}")
            return yaml_path

        except Exception as e:
            self.logger.error(f"修改 YAML 文件失败: {str(e)}")
            self.logger.error(traceback.format_exc())
            # 返回原始文件路径，不中断流程
            return yaml_path

    def extract_tools_from_config(self, config_path):
        """从 MCP 配置文件中提取工具列表"""
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

    def fetch_openapi_spec(self, url):
        """获取 OpenAPI 规范文件"""
        self._log_caller_info()
        self.logger.info(f"获取 OpenAPI 规范: {url}")

        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            spec = response.json()
            self.logger.info(f"成功获取 OpenAPI 规范: {url}")
            # 注释掉打印规范内容的部分
            # self.logger.debug(f"规范内容: {json.dumps(spec, indent=2, ensure_ascii=False)}")
            return spec
        except Exception as e:
            self.logger.error(f"获取 OpenAPI 规范失败: {url}")
            self.logger.error(f"错误: {str(e)}")
            self.logger.error(traceback.format_exc())
            raise RuntimeError(f"获取 OpenAPI 规范失败: {str(e)}")

    def check_and_create_higress_config(self, domain):
        """
        创建或覆盖 configmaps 目录中的 higress-config.yaml 文件

        Args:
            domain: 域名（不包含端口和协议前缀）
        """
        logger = logging.getLogger("main")

        # 处理 domain 参数，确保不包含协议前缀和端口
        clean_domain = domain

        # 如果包含协议前缀 (http:// 或 https://)，则移除
        if "://" in clean_domain:
            clean_domain = clean_domain.split("://")[1]

        # 如果包含端口号，则移除
        if ":" in clean_domain:
            clean_domain = clean_domain.split(":")[0]

        # 如果包含路径，则移除
        if "/" in clean_domain:
            clean_domain = clean_domain.split("/")[0]

        logger.info(f"处理后的域名: {clean_domain}")

        # 确保 configmaps 目录存在
        configmaps_dir = os.path.join(os.getcwd(), "configmaps")
        if not os.path.exists(configmaps_dir):
            logger.info(f"创建 configmaps 目录: {configmaps_dir}")
            os.makedirs(configmaps_dir)

        # 配置文件路径
        config_file_path = os.path.join(configmaps_dir, "higress-config.yaml")

        # 读取模板文件
        template_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     "higress-config-template.yaml")

        if os.path.exists(template_path):
            logger.info(f"使用模板文件: {template_path}")
            with open(template_path, 'r', encoding='utf-8') as f:
                config_template = f.read()
        else:
            logger.info("使用内置模板")
            # 内置模板
            config_template = """
    apiVersion: v1
    kind: ConfigMap
    metadata:
      name: higress-config
      namespace: higress-system
      creationTimestamp: "2000-01-01T00:00:00Z"
      resourceVersion: "1"
    data:
      higress: |-
        mcpServer:
          sse_path_suffix: /sse  # SSE 连接的路径后缀
          enable: true          # 启用 MCP Server
          redis:
            address: ${domain}:6379 # Redis服务地址。这里需要使用本机的内网 IP，不可以使用 127.0.0.1
            username: "" # Redis用户名（可选）
            password: "" # Redis密码（可选）
            db: 0 # Redis数据库（可选）
          match_list:          # MCP Server 会话保持路由规则（当匹配下面路径时，将被识别为一个 MCP 会话，通过 SSE 等机制进行会话保持）
            - match_rule_domain: "*"
              match_rule_path: /
              match_rule_type: "prefix"
          servers: []
        downstream:
          connectionBufferLimits: 32768
          http2:
            initialConnectionWindowSize: 1048576
            initialStreamWindowSize: 65535
            maxConcurrentStreams: 100
          idleTimeout: 180
          maxRequestHeadersKb: 60
          routeTimeout: 0
        upstream:
          connectionBufferLimits: 10485760
          idleTimeout: 10
    """

        # 替换模板中的变量
        config_content = config_template.replace("${domain}", clean_domain)

        # 写入文件
        try:
            with open(config_file_path, 'w', encoding='utf-8') as f:
                f.write(config_content)
            logger.info(f"成功创建/覆盖 higress-config.yaml 文件")
            return config_file_path
        except Exception as e:
            logger.error(f"创建/覆盖 higress-config.yaml 文件失败: {str(e)}")
            logger.error(traceback.format_exc())
            raise RuntimeError(f"创建/覆盖 higress-config.yaml 文件失败: {str(e)}")

    def setup_from_config(self, config_path, openapi_base_url="http://localhost:8000", api_key=None, domain=None):
        """
        从 MCP 配置文件获取工具列表并配置所有工具

        Args:
            config_path: MCP 配置文件路径
            openapi_base_url: OpenAPI 服务的基础 URL
            api_key: API密钥
            domain: 域名

        Returns:
            dict: 包含操作结果的字典
        """
        self._log_caller_info(logging.INFO)
        result = {"tools": []}

        try:
            self.logger.info(f"开始从配置文件配置工具...")
            self.logger.info(f"配置文件: {config_path}")
            self.logger.info(f"OpenAPI 基础 URL: {openapi_base_url}")

            # 步骤 1: 从配置文件提取工具列表
            self.logger.info(f"步骤 1: 从配置文件提取工具列表")
            tools = self.extract_tools_from_config(config_path)

            if not tools:
                self.logger.warning("未找到工具列表，将退出")
                return {"tools": [], "status": "no_tools_found"}

            # 创建消费者 (只需要一个)
            try:
                self.logger.info("步骤 2: 创建/更新 Consumer")
                consumer = self.create_computenest_consumer(api_key)
                result["consumer"] = consumer
                self.logger.info("Consumer 创建/更新成功")
            except Exception as e:
                self.logger.error(f"创建 Consumer 失败: {str(e)}")
                self.logger.error(traceback.format_exc())
                raise RuntimeError(f"创建 Consumer 失败: {str(e)}")

            # 步骤 3: 为每个工具获取 OpenAPI 规范并配置
            for tool in tools:
                try:
                    self.logger.info(f"配置工具: {tool}")

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

                    # 使用工具名称作为服务名称
                    server_name = tool

                    # 转换 OpenAPI JSON 为 MCP YAML
                    self.logger.info(f"转换 {tool} OpenAPI 规范为 MCP YAML")
                    mcp_yaml_path = self.convert_openapi_to_mcp(json_file_path, server_name)
                    self.logger.info(f"MCP 配置文件生成在: {mcp_yaml_path}")

                    # 修改 MCP YAML，添加授权头和修改 URL 前缀
                    self.logger.info(f"修改 MCP YAML 文件，添加授权头和修改 URL 前缀")
                    mcp_yaml_path = self.modify_mcp_yaml(
                        mcp_yaml_path,
                        api_key,
                        base_url=openapi_base_url
                    )

                    # 创建服务来源
                    self.logger.info(f"为 {tool} 创建服务来源")
                    service = self.create_service_source(name=server_name, domain=domain)

                    # 创建路由
                    self.logger.info(f"为 {tool} 创建路由")
                    route = self.create_route(name=server_name, service_name=server_name)

                    # 应用 MCP 插件配置
                    self.logger.info(f"为 {tool} 配置 MCP 插件")
                    plugin = self.configure_mcp_plugin(server_name, mcp_yaml_path)

                    # 记录结果
                    tool_result = {
                        "name": tool,
                        "spec_url": tool_spec_url,
                        "mcp_yaml_path": mcp_yaml_path,
                        "service": service,
                        "route": route,
                        "plugin": plugin
                    }
                    result["tools"].append(tool_result)

                    self.logger.info(f"工具 {tool} 配置成功")

                except Exception as e:
                    self.logger.error(f"配置工具 {tool} 失败: {str(e)}")
                    self.logger.error(traceback.format_exc())
                    # 继续处理其他工具，不中断整个流程
                    result["tools"].append({
                        "name": tool,
                        "error": str(e),
                        "status": "failed"
                    })

            self.logger.info(
                f"完成从配置文件配置工具，成功配置 {len([t for t in result['tools'] if 'error' not in t])} 个工具")
            return result

        except Exception as e:
            self.logger.error(f"从配置文件配置工具失败: {str(e)}")
            self.logger.error(f"异常类型: {type(e).__name__}")
            self.logger.error(traceback.format_exc())
            raise RuntimeError(f"从配置文件配置工具失败: {str(e)}")




def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='OpenAPI 到 Higress MCP 配置工具',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    # 必要参数
    parser.add_argument('--api-key', required=True, help='API密钥')
    parser.add_argument('--config', required=True, help='MCP 配置文件路径 (JSON)')

    # 可选参数
    parser.add_argument('--domain', required=True, help='域名必填，用于服务来源和Redis配置')
    parser.add_argument('--openapi-url', default='http://localhost:8000', help='OpenAPI 服务基础 URL')
    parser.add_argument('--base-url', default='http://localhost:8001', help='Higress API基础URL')
    parser.add_argument('--username', default='admin', help='登录用户名')
    parser.add_argument('--verbose', '-v', action='store_true', help='启用详细日志')
    parser.add_argument('--debug', '-d', action='store_true', help='启用调试模式')

    return parser.parse_args()



def main():
    """主函数"""
    args = parse_args()

    # 设置根日志级别
    log_level = logging.DEBUG if args.debug or args.verbose else logging.INFO

    # 配置根日志记录器
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s() - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('higress_client.log', mode='w')  # 使用 'w' 模式覆盖旧日志
        ]
    )
    # 为控制台处理程序单独设置日志级别
    for handler in logging.getLogger().handlers:
        if isinstance(handler, logging.StreamHandler) and handler.stream == sys.stdout:
            handler.setLevel(log_level)
        elif isinstance(handler, logging.FileHandler):
            handler.setLevel(logging.DEBUG)

    logger = logging.getLogger("main")
    logger.info("Higress OpenAPI 到 MCP 配置工具启动")

    try:
        # 显示运行环境信息
        logger.info(f"Python 版本: {sys.version}")
        logger.info(f"运行命令: {' '.join(sys.argv)}")
        logger.info(f"工作目录: {os.getcwd()}")
        logger.info(f"参数: {vars(args)}")


        # 检查配置文件是否存在
        if not os.path.isfile(args.config):
            logger.error(f"配置文件不存在: {args.config}")
            print(f"错误: 配置文件不存在: {args.config}", file=sys.stderr)
            return 1

        # 初始化客户端并登录
        client = HigressClient(
            base_url=args.base_url,
            username=args.username,
            apikey=args.api_key,
            verbose=args.debug or args.verbose,
            domain=args.domain
        )

        # 从配置文件配置工具
        result = client.setup_from_config(
            config_path=args.config,
            openapi_base_url=args.openapi_url,
            api_key=args.api_key,
            domain=args.domain,
        )

        # 输出结果摘要
        if result.get("status") == "no_tools_found":
            logger.warning("未找到任何工具，请检查配置文件")
            print("警告: 未找到任何工具，请检查配置文件")
            return 1

        success_count = len([t for t in result['tools'] if 'error' not in t])
        total_count = len(result['tools'])
        logger.info(f"从配置文件配置完成: {success_count}/{total_count} 个工具成功")
        print(f"从配置文件配置完成: {success_count}/{total_count} 个工具成功")

        # 输出详细结果
        for tool in result['tools']:
            if 'error' in tool:
                print(f"  - {tool['name']}: 失败 ({tool['error']})")
            else:
                print(f"  - {tool['name']}: 成功")

        return 0

    except Exception as e:
        logger.error(f"错误: {str(e)}")
        logger.error(f"异常类型: {type(e).__name__}")
        logger.error(traceback.format_exc())
        print(f"错误: {str(e)}", file=sys.stderr)
        print("查看 higress_client.log 获取详细错误信息", file=sys.stderr)
        return 1


# 作为模块导入时可以直接使用 HigressClient 类
# 作为脚本运行时使用命令行参数
if __name__ == "__main__":
    sys.exit(main())
