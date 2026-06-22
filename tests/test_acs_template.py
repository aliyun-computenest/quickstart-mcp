from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / ".computenest" / "config.yaml"
ACS_TEMPLATE_PATH = ROOT / ".computenest" / "ros_templates" / "acs.yaml"
FC_TEMPLATE_PATH = ROOT / ".computenest" / "ros_templates" / "fc.yaml"
ECS_TEMPLATE_PATH = ROOT / ".computenest" / "ros_templates" / "template.yaml"
ECS_ENTERPRISE_TEMPLATE_PATH = ROOT / ".computenest" / "ros_templates" / "template-enterprise.yaml"
ECS_SERVICE_TEST_PATH = ROOT / ".computenest" / "service_test" / "ECS单机版.yaml"
ACS_DOCKERFILE_PATH = ROOT / "mcp" / "Dockerfile.acs"
ROOT_DOCKERFILE_PATH = ROOT / "Dockerfile"


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
    assert all(item["Name"] != "ECS企业版" for item in supplier_templates)
    assert all(item["Name"] != "ECS企业版" for item in consumer_templates)
    status_operations = service["OperationMetadata"]["StatusOperationConfigs"]
    modify_configs = service["OperationMetadata"]["ModifyParametersConfig"]
    assert all(item["TemplateName"] != "ECS企业版" for item in status_operations)
    assert all(item["TemplateName"] != "ECS企业版" for item in modify_configs)

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
    assert config["Artifact"]["AcsMcpImage"]["ArtifactBuildType"] == "ContainerImage"
    assert config["Artifact"]["AcsMcpImage"]["ArtifactProperty"] == {
        "RepoName": "computenest/quickstart-mcp-acs",
        "Tag": "beta-20260618-streamable-181458",
        "RepoType": "Public",
    }
    assert config["Artifact"]["AcsMcpImage"]["ArtifactBuildProperty"]["RegionId"] == "cn-hangzhou"
    assert config["Artifact"]["AcsMcpImage"]["ArtifactBuildProperty"]["SourceContainerImage"] == (
        "compute-nest-registry.cn-hangzhou.cr.aliyuncs.com/computenest/quickstart-mcp-acs:beta-20260618-streamable-181458"
    )


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


def test_ecs_single_template_supports_regions_used_by_service_tests():
    config = load_yaml(CONFIG_PATH)
    service_test = load_yaml(ECS_SERVICE_TEST_PATH)
    service = config["Service"]
    supplier_templates = service["DeployMetadata"]["SupplierDeployMetadata"]["SupplierTemplateConfigs"]
    consumer_templates = service["DeployMetadata"]["TemplateConfigs"]
    supplier_ecs = next(item for item in supplier_templates if item["Name"] == "ECS单机版")
    consumer_ecs = next(item for item in consumer_templates if item["Name"] == "ECS单机版")
    ecs_artifact = config["Artifact"]["EcsImage"]
    required_regions = {"cn-hangzhou", "ap-southeast-1"}

    assert required_regions.issubset(set(supplier_ecs["AllowedRegions"]))
    assert required_regions.issubset(set(consumer_ecs["AllowedRegions"]))
    assert set(supplier_ecs["AllowedRegions"]).issubset(set(ecs_artifact["SupportRegionIds"]))
    assert set(consumer_ecs["AllowedRegions"]).issubset(set(ecs_artifact["SupportRegionIds"]))
    if "regionId" in service_test:
        assert service_test["regionId"] in consumer_ecs["AllowedRegions"]


def test_gateway_templates_only_expose_mcp_config_change_operation():
    config = load_yaml(CONFIG_PATH)

    for template_name in ("FC企业版", "ACS企业版"):
        operations = get_modify_operations(config, template_name)

        assert set(operations) == {"Modify-MCP-Servers"}
        assert operations["Modify-MCP-Servers"]["Parameters"] == ["McpConfigJson"]


def test_gateway_templates_do_not_define_managed_mcp_config_parameter():
    for template_path in (FC_TEMPLATE_PATH, ACS_TEMPLATE_PATH):
        template = load_yaml(template_path)

        assert "ManagedMcpConfigJson" not in template["Parameters"]


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
    workload_yaml = yaml.safe_dump(resources["McpServerWorkloads"], allow_unicode=True)
    ingress_yaml = yaml.safe_dump(resources["McpRuntimeIngress"], allow_unicode=True)

    assert parameters["McpConfigJson"]["AssociationProperty"] == "ALIYUN::MCP::Server::Server"
    assert parameters["GatewayOption"]["AllowedValues"] == ["ExistingGateway", "NewGateway"]
    assert resources["AckOrAcsCluster"]["Type"] == "ALIYUN::ACS::Cluster"
    assert resources["KnativeKourier"]["Type"] == "ALIYUN::CS::ClusterHelmApplication"
    assert resources["KnativeServing"]["Type"] == "ALIYUN::CS::ClusterHelmApplication"
    assert resources["HelmManagerAddon"]["Type"] == "ALIYUN::CS::ClusterAddons"
    assert resources["HelmManagerAddon"]["DependsOn"] == "ClusterReadySleep"
    assert resources["HelmManagerAddon"]["Properties"]["Addons"] == [{"Name": "ack-helm-manager"}]
    assert resources["HelmManagerSleep"]["DependsOn"] == ["HelmManagerAddon"]
    assert resources["KnativeServing"]["DependsOn"] == "HelmManagerSleep"
    assert resources["KnativeServingReadySleep"]["DependsOn"] == ["KnativeServing"]
    assert resources["KnativeKourier"]["DependsOn"] == "KnativeServingReadySleep"
    assert resources["KnativeKourierReadySleep"]["DependsOn"] == ["KnativeKourier"]
    assert "ack-knative-kourier" in resources["KnativeKourier"]["Properties"]["ChartUrl"]
    assert "ack-knative-serving" in resources["KnativeServing"]["Properties"]["ChartUrl"]
    assert resources["KnativeKourier"]["Properties"]["IgnoreExisting"] == "SkipAllOperationsIfExisting"
    assert resources["KnativeServing"]["Properties"]["IgnoreExisting"] == "SkipAllOperationsIfExisting"
    assert resources["KnativeKourier"]["Properties"]["ChartValues"]["registryURL"] == {
        "Fn::Sub": "registry-${ALIYUN::Region}.ack.aliyuncs.com"
    }
    assert resources["KnativeKourier"]["Properties"]["ChartValues"]["clusterId"] == {
        "Fn::GetAtt": ["AckOrAcsCluster", "ClusterId"]
    }
    assert resources["KnativeKourier"]["Properties"]["ChartValues"]["isDefault"] is False
    assert resources["McpNamespace"]["DependsOn"] == "KnativeKourierReadySleep"
    assert "McpRuntimeDeployment" not in resources
    assert "McpRuntimeService" not in resources
    assert "McpApiDeployment" not in resources
    assert "McpApiService" not in resources
    assert resources["McpServerWorkloads"]["Type"] == "ALIYUN::CS::ClusterApplication"
    assert resources["McpRuntimeIngress"]["Type"] == "ALIYUN::CS::ClusterApplication"
    assert parameters["EnableGatewayRegistration"]["Default"] is False
    assert resources["McpRegistrationJob"]["Type"] == "ALIYUN::CS::ClusterApplication"
    assert resources["McpRegistrationJob"]["Condition"] == "EnableGatewayRegistrationCondition"
    assert "{{ computenest::acrimage::quickstart-mcp-acs }}" in template_text
    assert "serverCode" in workload_yaml
    assert "serving.knative.dev/v1" in workload_yaml
    assert "kind: Service" in workload_yaml
    assert "apiVersion: apps/v1" not in workload_yaml
    assert "kind: Deployment" not in workload_yaml
    assert "autoscaling.knative.dev/min-scale" in workload_yaml
    assert "autoscaling.knative.dev/max-scale" in workload_yaml
    assert "networking.knative.dev/visibility: cluster-local" in workload_yaml
    assert "app: mcp-server-backend" in workload_yaml
    assert "serving.knative.dev/service: mcp-" in workload_yaml
    assert "containerPort:" in workload_yaml
    assert "8080" in workload_yaml
    assert "number: 80" in ingress_yaml
    assert "number: 8080" not in ingress_yaml
    assert "-backend" in ingress_yaml
    assert "/mcp-servers/" in template_text
    assert "mcp-api" not in template_text
    assert "mcpo" not in template_text
    assert "McpGatewayConsole" in outputs
    assert "McpRuntimeEndpoint" in outputs
    assert "McpApiEndpointHint" not in outputs


def test_acs_template_supports_remote_mcp_url_transport_types():
    template_text = ACS_TEMPLATE_PATH.read_text(encoding="utf-8")

    assert "def remote_input_arg" in template_text
    assert 'if $type == "streamable-http" or $type == "streamablehttp" then "--streamableHttp" else "--sse" end' in template_text
    assert '"exec supergateway " + remote_input_arg' in template_text
    assert "remote_command($name)" in template_text


def test_acs_runtime_image_installs_supergateway_without_changing_ecs_dockerfile():
    dockerfile = ACS_DOCKERFILE_PATH.read_text(encoding="utf-8")

    assert "npm install -g supergateway" in dockerfile
    assert "mcpo" not in dockerfile
    assert "COPY mcp/ /app/" in dockerfile
    assert "ENTRYPOINT" not in dockerfile
    assert "mcpo" in ROOT_DOCKERFILE_PATH.read_text(encoding="utf-8")


def test_acs_template_quotes_computenest_image_placeholder_inside_kubernetes_yaml():
    template_text = ACS_TEMPLATE_PATH.read_text(encoding="utf-8")

    assert 'image: {{ computenest::acrimage::quickstart-mcp-acs }}' not in template_text
    assert 'image: "{{ computenest::acrimage::quickstart-mcp-acs }}"' in template_text
