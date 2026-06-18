from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / ".computenest" / "config.yaml"
ACS_TEMPLATE_PATH = ROOT / ".computenest" / "ros_templates" / "acs.yaml"
FC_TEMPLATE_PATH = ROOT / ".computenest" / "ros_templates" / "fc.yaml"
ECS_TEMPLATE_PATH = ROOT / ".computenest" / "ros_templates" / "template.yaml"
ECS_ENTERPRISE_TEMPLATE_PATH = ROOT / ".computenest" / "ros_templates" / "template-enterprise.yaml"
ACS_DOCKERFILE_PATH = ROOT / "mcp" / "Dockerfile.acs"


def load_yaml(path: Path):
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def get_modify_operations(config, template_name):
    modify_configs = config["Service"]["OperationMetadata"]["ModifyParametersConfig"]
    modify_config = next(item for item in modify_configs if item["TemplateName"] == template_name)
    return {item["Name"]: item for item in modify_config["Operation"]}


def test_acs_template_is_registered_in_computenest_config():
    config = load_yaml(CONFIG_PATH)
    service = config["Service"]

    supplier_templates = service["DeployMetadata"]["SupplierDeployMetadata"]["SupplierTemplateConfigs"]
    consumer_templates = service["DeployMetadata"]["TemplateConfigs"]

    assert any(item["Name"] == "ACS企业版" and item["Url"] == "ros_templates/acs.yaml" for item in supplier_templates)
    assert any(item["Name"] == "ACS企业版" and item["Url"] == "ros_templates/acs.yaml" for item in consumer_templates)

    acs_operations = get_modify_operations(config, "ACS企业版")
    assert acs_operations["Modify-MCP-Servers"] == {
        "Name": "Modify-MCP-Servers",
        "Description": "修改已部署的MCP工具",
        "Type": "Custom",
        "SupportPredefinedParameters": False,
        "EnableLogging": False,
        "Parameters": ["McpConfigJson"],
    }

    supplier_metadata = service["DeployMetadata"]["SupplierDeployMetadata"]
    assert supplier_metadata["ArtifactRelation"]["ecs_image_quickstart-mcp"]["ArtifactVersion"] == "draft"
    assert supplier_metadata["AcrImageArtifactRelation"]["{{ computenest::acrimage::quickstart-mcp-acs }}"]["ArtifactVersion"] == "draft"
    assert "FileArtifactRelation" not in supplier_metadata
    assert "FcMcpCode" not in config["Artifact"]
    assert config["Artifact"]["EcsImage"]["ArtifactBuildProperty"]["CodeRepo"] == {
        "Platform": "github",
        "Owner": "aliyun-computenest",
        "RepoName": "aliyun-computenest/quickstart-mcp",
        "Branch": "main",
    }
    assert config["Artifact"]["AcsMcpImage"]["ArtifactType"] == "AcrImage"
    assert config["Artifact"]["AcsMcpImage"]["ArtifactBuildProperty"]["CodeRepo"]["DockerfilePath"] == "mcp/Dockerfile.acs"


def test_acs_runtime_image_artifact_supports_cn_hangzhou_beta_publish():
    config = load_yaml(CONFIG_PATH)
    service = config["Service"]
    supplier_templates = service["DeployMetadata"]["SupplierDeployMetadata"]["SupplierTemplateConfigs"]
    consumer_templates = service["DeployMetadata"]["TemplateConfigs"]
    supplier_acs = next(item for item in supplier_templates if item["Name"] == "ACS企业版")
    consumer_acs = next(item for item in consumer_templates if item["Name"] == "ACS企业版")
    acs_artifact = config["Artifact"]["AcsMcpImage"]

    assert "cn-hangzhou" in supplier_acs["AllowedRegions"]
    assert "cn-hangzhou" in consumer_acs["AllowedRegions"]
    assert acs_artifact["ArtifactName"] == "quickstart-mcp-acs"
    assert "cn-hangzhou" in acs_artifact["SupportRegionIds"]


def test_gateway_managed_mcp_change_operation_is_registered_for_gateway_templates():
    config = load_yaml(CONFIG_PATH)

    for template_name in ("FC企业版", "ACS企业版"):
        operations = get_modify_operations(config, template_name)

        assert operations["Modify-MCP-Servers"]["Parameters"] == ["McpConfigJson"]
        assert operations["Manage-Gateway-MCP"] == {
            "Name": "Manage-Gateway-MCP",
            "Description": "接入或移出网关MCP",
            "Type": "Custom",
            "SupportPredefinedParameters": False,
            "EnableLogging": False,
            "Parameters": ["ManagedMcpConfigJson"],
        }


def test_gateway_templates_define_hidden_managed_mcp_config_parameter():
    for template_path in (FC_TEMPLATE_PATH, ACS_TEMPLATE_PATH):
        template = load_yaml(template_path)
        parameter = template["Parameters"]["ManagedMcpConfigJson"]

        assert parameter["Type"] == "Json"
        assert parameter["Default"] == "[]"
        assert parameter["AssociationPropertyMetadata"]["Visible"] == {
            "Condition": {
                "Fn::Equals": [True, False],
            },
        }


def test_artifact_relations_match_ecs_image_ids_and_fc_uses_inline_registration_code():
    config = load_yaml(CONFIG_PATH)
    supplier_metadata = config["Service"]["DeployMetadata"]["SupplierDeployMetadata"]
    config_image_ids = set(supplier_metadata["ArtifactRelation"])
    template_configs = config["Service"]["DeployMetadata"]["TemplateConfigs"]
    ecs_image_support_regions = set(config["Artifact"]["EcsImage"]["SupportRegionIds"])

    for template_path in (ECS_TEMPLATE_PATH, ECS_ENTERPRISE_TEMPLATE_PATH):
        template = load_yaml(template_path)
        template_text = yaml.safe_dump(template)
        template_image_ids = {
            line.split(":", 1)[1].strip()
            for line in template_text.splitlines()
            if line.strip().startswith("ImageId:")
        }
        assert template_image_ids == config_image_ids

    for template_config in template_configs:
        assert set(template_config["AllowedRegions"]).issubset(ecs_image_support_regions)

    fc_template_text = FC_TEMPLATE_PATH.read_text(encoding="utf-8")
    fc_template = load_yaml(FC_TEMPLATE_PATH)
    registration_function = fc_template["Resources"]["McpRegistrationFunction"]
    assert registration_function["Properties"]["Handler"] == "index.handler"
    assert "SourceCode" in registration_function["Properties"]["Code"]
    assert "computenest::file::FcMcpCode" not in fc_template_text


def test_acs_template_contains_runtime_gateway_and_registration_resources():
    template = load_yaml(ACS_TEMPLATE_PATH)
    template_text = ACS_TEMPLATE_PATH.read_text(encoding="utf-8")
    parameters = template["Parameters"]
    resources = template["Resources"]
    outputs = template["Outputs"]

    assert parameters["McpConfigJson"]["AssociationProperty"] == "ALIYUN::MCP::Server::Server"
    assert parameters["GatewayOption"]["AllowedValues"] == ["ExistingGateway", "NewGateway"]
    assert resources["AckOrAcsCluster"]["Type"] == "ALIYUN::ACS::Cluster"
    assert "McpRuntimeDeployment" not in resources
    assert "McpRuntimeService" not in resources
    assert resources["McpApiDeployment"]["Type"] == "ALIYUN::CS::ClusterApplication"
    assert resources["McpApiService"]["Type"] == "ALIYUN::CS::ClusterApplication"
    assert resources["McpServerWorkloads"]["Type"] == "ALIYUN::CS::ClusterApplication"
    assert resources["McpRuntimeIngress"]["Type"] == "ALIYUN::CS::ClusterApplication"
    assert parameters["EnableGatewayRegistration"]["Default"] is False
    assert resources["McpRegistrationJob"]["Type"] == "ALIYUN::CS::ClusterApplication"
    assert resources["McpRegistrationJob"]["Condition"] == "EnableGatewayRegistrationCondition"
    assert "{{ computenest::acrimage::quickstart-mcp-acs }}" in template_text
    assert "serverCode" in yaml.safe_dump(resources["McpServerWorkloads"])
    assert "/mcp-servers/" in template_text
    assert "McpGatewayConsole" in outputs
    assert "McpRuntimeEndpoint" in outputs


def test_acs_runtime_image_installs_supergateway_without_changing_ecs_dockerfile():
    dockerfile = ACS_DOCKERFILE_PATH.read_text(encoding="utf-8")

    assert "npm install -g supergateway" in dockerfile
    assert "COPY mcp/ /app/" in dockerfile
    assert "ENTRYPOINT" not in dockerfile


def test_acs_template_quotes_computenest_image_placeholder_inside_kubernetes_yaml():
    template_text = ACS_TEMPLATE_PATH.read_text(encoding="utf-8")

    assert 'image: {{ computenest::acrimage::quickstart-mcp-acs }}' not in template_text
    assert 'image: "{{ computenest::acrimage::quickstart-mcp-acs }}"' in template_text
