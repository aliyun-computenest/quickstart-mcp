#!/usr/bin/env python3
import json
import subprocess
import os
import sys

def get_file_md5(file_path):
    """使用ossutil hash命令获取文件的MD5值（支持本地文件和OSS文件）"""
    try:
        # 使用ossutil hash md5命令获取文件的MD5值
        result = subprocess.run([
            'ossutil', 'hash', 'md5', file_path
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)

        if result.returncode == 0:
            # 解析输出，格式为：md5值 文件路径
            for line in result.stdout.split('\n'):
                line = line.strip()
                if line and not line.startswith('0.') and 'elapsed' not in line:
                    # 分割MD5值和文件路径
                    parts = line.split(None, 1)  # 按空白字符分割，最多分割1次
                    if len(parts) >= 2:
                        md5_value = parts[0].strip()
                        # 验证MD5格式（32位十六进制）
                        if len(md5_value) == 32 and all(c in '0123456789abcdef' for c in md5_value.lower()):
                            return md5_value.lower()
        else:
            print(f"获取文件MD5失败: {result.stderr}")

    except Exception as e:
        print(f"获取文件MD5异常: {str(e)}")

    return None

def files_are_same(local_path, oss_path):
    """比较本地文件和OSS文件是否相同"""
    if not os.path.exists(local_path):
        return False

    print(f"正在校验文件MD5...")

    # 获取本地文件MD5
    local_md5 = get_file_md5(local_path)
    if not local_md5:
        print(f"无法计算本地文件MD5，将重新下载")
        return False

    # 获取OSS文件MD5
    oss_md5 = get_file_md5(oss_path)
    if not oss_md5:
        print(f"无法获取OSS文件MD5，将重新下载")
        return False

    print(f"本地文件MD5: {local_md5}")
    print(f"OSS文件MD5:  {oss_md5}")

    return local_md5 == oss_md5

def download_package(package_oss_path, bucket_name):
    """从OSS下载包到本地package目录"""
    if not package_oss_path:
        return None

    # 处理OSS路径，如果已经包含oss://前缀则直接使用
    if package_oss_path.startswith('oss://'):
        oss_path = package_oss_path
    else:
        oss_path = f"oss://{bucket_name}{package_oss_path}"

    # 从OSS路径中提取文件名
    filename = os.path.basename(package_oss_path.replace('oss://', '').split('/', 1)[1] if package_oss_path.startswith('oss://') else package_oss_path)
    local_path = f"/root/mcp-package/{filename}"

    # 确保目录存在
    os.makedirs("/root/mcp-package", exist_ok=True)

    # 检查本地文件是否已存在，并比较MD5
    if os.path.exists(local_path):
        print(f"本地文件 {local_path} 已存在，正在校验是否需要更新...")
        if files_are_same(local_path, oss_path):
            print(f"文件MD5相同，跳过下载")
            return local_path
        else:
            print(f"文件MD5不同，需要重新下载")

    try:
        print(f"正在下载 {oss_path} 到 {local_path}")
        # 使用兼容的subprocess调用方式
        result = subprocess.run([
            'ossutil', 'cp', oss_path, local_path
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)

        if result.returncode == 0:
            print(f"下载成功: {local_path}")
            # 验证下载后的文件
            downloaded_md5 = get_file_md5(local_path)
            if downloaded_md5:
                print(f"下载文件MD5: {downloaded_md5}")
            return local_path
        else:
            print(f"下载失败 {oss_path}: {result.stderr}")
            return None

    except Exception as e:
        print(f"下载异常 {oss_path}: {str(e)}")
        return None

def main():
    if len(sys.argv) < 3:
        print("用法: python3 download_oss.py <bucket_name> <json_file_path>")
        sys.exit(1)

    bucket_name = sys.argv[1]
    json_file_path = sys.argv[2]

    success_count = 0
    total_count = 0
    failed_servers = []

    try:
        # 读取JSON文件
        with open(json_file_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        print(f"配置文件加载成功")

        # 获取mcpServers对象
        mcp_servers = config.get('mcpServers', {})

        if not isinstance(mcp_servers, dict):
            print(f"错误: mcpServers应该是一个对象，但得到了 {type(mcp_servers)}")
            sys.exit(1)

        print(f"找到 {len(mcp_servers)} 个服务器配置")

        # 遍历服务器配置（键值对）
        for server_name, server_config in mcp_servers.items():
            print(f"\n处理服务器: {server_name}")

            # 检查server_config是否为字典
            if not isinstance(server_config, dict):
                print(f"警告: 服务器 {server_name} 的配置不是字典格式，跳过: {server_config}")
                continue

            package_oss_path = server_config.get('packageOssPath')
            if package_oss_path:
                total_count += 1
                print(f"处理服务器 {server_name} 的包下载...")
                print(f"OSS路径: {package_oss_path}")

                # 下载包
                local_path = download_package(package_oss_path, bucket_name)
                if local_path:
                    success_count += 1
                    print(f"服务器 {server_name} 处理成功")
                else:
                    failed_servers.append(f"{server_name} (下载失败)")
                    print(f"服务器 {server_name} 下载失败")
            else:
                print(f"服务器 {server_name} 没有packageOssPath，跳过")

        # 输出总结
        print(f"\n=== 包下载总结 ===")
        print(f"总计需要处理: {total_count} 个包")
        print(f"成功处理: {success_count} 个包")
        print(f"失败: {len(failed_servers)} 个包")

        if failed_servers:
            print(f"失败的服务器: {', '.join(failed_servers)}")
            print("警告: 部分包下载失败，但部署将继续进行")
        else:
            print("所有包处理完成")

        # 即使有失败也返回0，让部署继续
        sys.exit(0)

    except FileNotFoundError:
        print(f"JSON文件不存在: {json_file_path}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"JSON解析错误: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"执行错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
