import time
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum


class ServiceCategory(Enum):
    COMPUTE = "compute"
    STORAGE = "storage"
    DATABASE = "database"
    NETWORKING = "networking"
    CONTAINER = "container"
    SERVERLESS = "serverless"
    SECURITY = "security"
    MONITORING = "monitoring"
    MESSAGING = "messaging"
    CDN = "cdn"


class DifficultyLevel(Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


@dataclass
class DPIaCScenario:
    id: str
    name: str
    description: str
    natural_language_request: str
    category: ServiceCategory
    difficulty: DifficultyLevel
    cloud_provider: str
    required_resources: List[str]
    validation_rules: Dict[str, Any]
    reference_solution: Optional[str] = None
    intent_criteria: List[str] = field(default_factory=list)
    security_requirements: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "request": self.natural_language_request,
            "category": self.category.value,
            "difficulty": self.difficulty.value,
            "cloud_provider": self.cloud_provider,
            "required_resources": self.required_resources,
            "validation_rules": self.validation_rules,
            "intent_criteria": self.intent_criteria,
            "security_requirements": self.security_requirements,
        }


@dataclass
class EvaluationResult:
    scenario_id: str
    success: bool
    deployable: bool
    intent_aligned: bool
    security_compliant: bool
    iterations: int
    time_ms: float
    generated_code: str
    errors: List[str] = field(default_factory=list)
    scores: Dict[str, float] = field(default_factory=dict)


@dataclass
class BenchmarkResults:
    total_scenarios: int
    successful: int
    first_attempt_success: int
    pass_at_1: float
    pass_at_5: float
    pass_at_10: float
    pass_at_25: float
    avg_iterations: float
    avg_time_ms: float
    intent_alignment_rate: float
    security_compliance_rate: float
    by_category: Dict[str, Dict]
    by_difficulty: Dict[str, Dict]
    individual_results: List[EvaluationResult]


class DPIaCEvalBenchmark:
    def __init__(self, max_iterations: int = 10):
        self.max_iterations = max_iterations
        self.scenarios = self._load_scenarios()
        self.results: List[EvaluationResult] = []

    def _load_scenarios(self) -> List[DPIaCScenario]:
        scenarios = []

        scenarios.extend(self._aws_compute_scenarios())
        scenarios.extend(self._aws_storage_scenarios())
        scenarios.extend(self._aws_database_scenarios())
        scenarios.extend(self._aws_networking_scenarios())
        scenarios.extend(self._aws_container_scenarios())
        scenarios.extend(self._aws_serverless_scenarios())
        scenarios.extend(self._multi_service_scenarios())

        return scenarios

    def _aws_compute_scenarios(self) -> List[DPIaCScenario]:
        return [
            DPIaCScenario(
                id="dpiac-001",
                name="Basic EC2 Instance",
                description="Create a basic EC2 instance with SSH access",
                natural_language_request="Create an AWS EC2 t2.micro instance running Amazon Linux 2 with SSH access from my IP",
                category=ServiceCategory.COMPUTE,
                difficulty=DifficultyLevel.EASY,
                cloud_provider="aws",
                required_resources=["aws_instance", "aws_security_group"],
                validation_rules={
                    "has_instance": True,
                    "has_security_group": True,
                    "instance_type": "t2.micro",
                },
                intent_criteria=[
                    "EC2 instance created",
                    "SSH port 22 allowed",
                    "Amazon Linux 2 AMI",
                ],
                security_requirements=["Security group restricts SSH to specific IP"],
            ),
            DPIaCScenario(
                id="dpiac-002",
                name="EC2 with EBS Volume",
                description="EC2 instance with attached EBS volume",
                natural_language_request="Create an EC2 instance with a 100GB gp3 EBS volume attached for data storage",
                category=ServiceCategory.COMPUTE,
                difficulty=DifficultyLevel.MEDIUM,
                cloud_provider="aws",
                required_resources=[
                    "aws_instance",
                    "aws_ebs_volume",
                    "aws_volume_attachment",
                ],
                validation_rules={
                    "has_instance": True,
                    "has_ebs": True,
                    "ebs_size": 100,
                    "ebs_type": "gp3",
                },
                intent_criteria=[
                    "EC2 instance created",
                    "100GB EBS volume",
                    "gp3 volume type",
                    "Volume attached",
                ],
            ),
            DPIaCScenario(
                id="dpiac-003",
                name="Auto Scaling Group",
                description="EC2 Auto Scaling with launch template",
                natural_language_request="Create an Auto Scaling group with 2-10 instances using t3.medium, with CPU-based scaling policy",
                category=ServiceCategory.COMPUTE,
                difficulty=DifficultyLevel.HARD,
                cloud_provider="aws",
                required_resources=[
                    "aws_launch_template",
                    "aws_autoscaling_group",
                    "aws_autoscaling_policy",
                ],
                validation_rules={
                    "has_asg": True,
                    "min_size": 2,
                    "max_size": 10,
                    "has_scaling_policy": True,
                },
                intent_criteria=[
                    "ASG created",
                    "Min 2 instances",
                    "Max 10 instances",
                    "CPU scaling policy",
                ],
            ),
            DPIaCScenario(
                id="dpiac-004",
                name="EC2 with User Data",
                description="EC2 with startup script for web server",
                natural_language_request="Create an EC2 instance that automatically installs and starts nginx on boot",
                category=ServiceCategory.COMPUTE,
                difficulty=DifficultyLevel.EASY,
                cloud_provider="aws",
                required_resources=["aws_instance"],
                validation_rules={
                    "has_instance": True,
                    "has_user_data": True,
                    "nginx_installed": True,
                },
                intent_criteria=[
                    "EC2 instance created",
                    "User data script",
                    "nginx installation",
                ],
            ),
            DPIaCScenario(
                id="dpiac-005",
                name="Spot Instance Fleet",
                description="Cost-optimized spot instance fleet",
                natural_language_request="Create a spot instance fleet with mixed instance types for cost optimization, capacity 5 instances",
                category=ServiceCategory.COMPUTE,
                difficulty=DifficultyLevel.HARD,
                cloud_provider="aws",
                required_resources=["aws_spot_fleet_request"],
                validation_rules={
                    "has_spot_fleet": True,
                    "target_capacity": 5,
                    "mixed_instances": True,
                },
                intent_criteria=[
                    "Spot fleet created",
                    "5 instance capacity",
                    "Mixed instance types",
                ],
            ),
        ]

    def _aws_storage_scenarios(self) -> List[DPIaCScenario]:
        return [
            DPIaCScenario(
                id="dpiac-010",
                name="S3 Bucket with Versioning",
                description="Create S3 bucket with versioning enabled",
                natural_language_request="Create an S3 bucket with versioning enabled and server-side encryption",
                category=ServiceCategory.STORAGE,
                difficulty=DifficultyLevel.EASY,
                cloud_provider="aws",
                required_resources=[
                    "aws_s3_bucket",
                    "aws_s3_bucket_versioning",
                    "aws_s3_bucket_server_side_encryption_configuration",
                ],
                validation_rules={
                    "has_bucket": True,
                    "versioning_enabled": True,
                    "encryption_enabled": True,
                },
                intent_criteria=[
                    "S3 bucket created",
                    "Versioning enabled",
                    "SSE enabled",
                ],
                security_requirements=["Server-side encryption configured"],
            ),
            DPIaCScenario(
                id="dpiac-011",
                name="S3 Static Website",
                description="S3 bucket configured for static website hosting",
                natural_language_request="Create an S3 bucket for hosting a static website with index.html and error.html",
                category=ServiceCategory.STORAGE,
                difficulty=DifficultyLevel.MEDIUM,
                cloud_provider="aws",
                required_resources=[
                    "aws_s3_bucket",
                    "aws_s3_bucket_website_configuration",
                    "aws_s3_bucket_policy",
                ],
                validation_rules={
                    "has_bucket": True,
                    "website_enabled": True,
                    "public_read": True,
                },
                intent_criteria=[
                    "S3 bucket created",
                    "Website hosting enabled",
                    "Index document configured",
                ],
            ),
            DPIaCScenario(
                id="dpiac-012",
                name="S3 Cross-Region Replication",
                description="S3 bucket with cross-region replication",
                natural_language_request="Create S3 buckets with cross-region replication from us-east-1 to us-west-2",
                category=ServiceCategory.STORAGE,
                difficulty=DifficultyLevel.HARD,
                cloud_provider="aws",
                required_resources=[
                    "aws_s3_bucket",
                    "aws_s3_bucket_replication_configuration",
                    "aws_iam_role",
                ],
                validation_rules={
                    "has_source_bucket": True,
                    "has_destination_bucket": True,
                    "replication_enabled": True,
                },
                intent_criteria=[
                    "Source bucket in us-east-1",
                    "Destination bucket in us-west-2",
                    "Replication rule configured",
                ],
            ),
            DPIaCScenario(
                id="dpiac-013",
                name="EFS File System",
                description="EFS with mount targets in multiple AZs",
                natural_language_request="Create an EFS file system with mount targets in 3 availability zones for shared storage",
                category=ServiceCategory.STORAGE,
                difficulty=DifficultyLevel.MEDIUM,
                cloud_provider="aws",
                required_resources=["aws_efs_file_system", "aws_efs_mount_target"],
                validation_rules={
                    "has_efs": True,
                    "mount_targets": 3,
                },
                intent_criteria=[
                    "EFS created",
                    "3 mount targets",
                    "Multi-AZ deployment",
                ],
            ),
        ]

    def _aws_database_scenarios(self) -> List[DPIaCScenario]:
        return [
            DPIaCScenario(
                id="dpiac-020",
                name="RDS PostgreSQL",
                description="Create RDS PostgreSQL instance",
                natural_language_request="Create an RDS PostgreSQL 15 database with db.t3.medium instance class and 100GB storage",
                category=ServiceCategory.DATABASE,
                difficulty=DifficultyLevel.MEDIUM,
                cloud_provider="aws",
                required_resources=[
                    "aws_db_instance",
                    "aws_db_subnet_group",
                    "aws_security_group",
                ],
                validation_rules={
                    "has_rds": True,
                    "engine": "postgres",
                    "engine_version_prefix": "15",
                    "instance_class": "db.t3.medium",
                    "storage": 100,
                },
                intent_criteria=[
                    "RDS instance created",
                    "PostgreSQL 15",
                    "db.t3.medium",
                    "100GB storage",
                ],
                security_requirements=[
                    "Database in private subnet",
                    "Security group configured",
                ],
            ),
            DPIaCScenario(
                id="dpiac-021",
                name="RDS Multi-AZ",
                description="RDS with Multi-AZ deployment",
                natural_language_request="Create a highly available RDS MySQL database with Multi-AZ deployment and automated backups",
                category=ServiceCategory.DATABASE,
                difficulty=DifficultyLevel.MEDIUM,
                cloud_provider="aws",
                required_resources=["aws_db_instance"],
                validation_rules={
                    "has_rds": True,
                    "multi_az": True,
                    "backup_retention": True,
                },
                intent_criteria=[
                    "RDS instance created",
                    "Multi-AZ enabled",
                    "Automated backups configured",
                ],
            ),
            DPIaCScenario(
                id="dpiac-022",
                name="ElastiCache Redis",
                description="ElastiCache Redis cluster",
                natural_language_request="Create an ElastiCache Redis cluster with 2 nodes for caching",
                category=ServiceCategory.DATABASE,
                difficulty=DifficultyLevel.MEDIUM,
                cloud_provider="aws",
                required_resources=[
                    "aws_elasticache_cluster",
                    "aws_elasticache_subnet_group",
                ],
                validation_rules={
                    "has_elasticache": True,
                    "engine": "redis",
                    "num_cache_nodes": 2,
                },
                intent_criteria=["ElastiCache created", "Redis engine", "2 nodes"],
            ),
            DPIaCScenario(
                id="dpiac-023",
                name="DynamoDB Table",
                description="DynamoDB table with GSI",
                natural_language_request="Create a DynamoDB table with a partition key 'id' and a global secondary index on 'email'",
                category=ServiceCategory.DATABASE,
                difficulty=DifficultyLevel.MEDIUM,
                cloud_provider="aws",
                required_resources=["aws_dynamodb_table"],
                validation_rules={
                    "has_dynamodb": True,
                    "hash_key": "id",
                    "has_gsi": True,
                },
                intent_criteria=[
                    "DynamoDB table created",
                    "Partition key 'id'",
                    "GSI on 'email'",
                ],
            ),
        ]

    def _aws_networking_scenarios(self) -> List[DPIaCScenario]:
        return [
            DPIaCScenario(
                id="dpiac-030",
                name="Basic VPC",
                description="VPC with public and private subnets",
                natural_language_request="Create a VPC with CIDR 10.0.0.0/16, 2 public subnets and 2 private subnets across 2 AZs",
                category=ServiceCategory.NETWORKING,
                difficulty=DifficultyLevel.MEDIUM,
                cloud_provider="aws",
                required_resources=[
                    "aws_vpc",
                    "aws_subnet",
                    "aws_internet_gateway",
                    "aws_nat_gateway",
                    "aws_route_table",
                ],
                validation_rules={
                    "has_vpc": True,
                    "vpc_cidr": "10.0.0.0/16",
                    "public_subnets": 2,
                    "private_subnets": 2,
                },
                intent_criteria=[
                    "VPC created",
                    "CIDR 10.0.0.0/16",
                    "2 public subnets",
                    "2 private subnets",
                    "Multi-AZ",
                ],
            ),
            DPIaCScenario(
                id="dpiac-031",
                name="Application Load Balancer",
                description="ALB with target group",
                natural_language_request="Create an Application Load Balancer with HTTPS listener and target group for EC2 instances",
                category=ServiceCategory.NETWORKING,
                difficulty=DifficultyLevel.MEDIUM,
                cloud_provider="aws",
                required_resources=["aws_lb", "aws_lb_listener", "aws_lb_target_group"],
                validation_rules={
                    "has_alb": True,
                    "has_https_listener": True,
                    "has_target_group": True,
                },
                intent_criteria=[
                    "ALB created",
                    "HTTPS listener",
                    "Target group configured",
                ],
                security_requirements=["HTTPS configured", "SSL certificate attached"],
            ),
            DPIaCScenario(
                id="dpiac-032",
                name="VPC Peering",
                description="VPC peering connection",
                natural_language_request="Create a VPC peering connection between two VPCs with proper route table entries",
                category=ServiceCategory.NETWORKING,
                difficulty=DifficultyLevel.HARD,
                cloud_provider="aws",
                required_resources=[
                    "aws_vpc",
                    "aws_vpc_peering_connection",
                    "aws_route",
                ],
                validation_rules={
                    "has_peering": True,
                    "routes_configured": True,
                },
                intent_criteria=[
                    "VPC peering created",
                    "Routes configured in both VPCs",
                ],
            ),
        ]

    def _aws_container_scenarios(self) -> List[DPIaCScenario]:
        return [
            DPIaCScenario(
                id="dpiac-040",
                name="ECS Fargate Service",
                description="ECS Fargate service with ALB",
                natural_language_request="Create an ECS Fargate service running nginx with 2 tasks behind an Application Load Balancer",
                category=ServiceCategory.CONTAINER,
                difficulty=DifficultyLevel.HARD,
                cloud_provider="aws",
                required_resources=[
                    "aws_ecs_cluster",
                    "aws_ecs_task_definition",
                    "aws_ecs_service",
                    "aws_lb",
                ],
                validation_rules={
                    "has_ecs_cluster": True,
                    "has_task_definition": True,
                    "has_service": True,
                    "desired_count": 2,
                    "launch_type": "FARGATE",
                },
                intent_criteria=[
                    "ECS cluster created",
                    "Fargate launch type",
                    "2 tasks",
                    "ALB integration",
                ],
            ),
            DPIaCScenario(
                id="dpiac-041",
                name="EKS Cluster",
                description="EKS cluster with managed node group",
                natural_language_request="Create an EKS cluster version 1.28 with a managed node group of 3 t3.medium instances",
                category=ServiceCategory.CONTAINER,
                difficulty=DifficultyLevel.HARD,
                cloud_provider="aws",
                required_resources=[
                    "aws_eks_cluster",
                    "aws_eks_node_group",
                    "aws_iam_role",
                ],
                validation_rules={
                    "has_eks": True,
                    "version": "1.28",
                    "has_node_group": True,
                    "node_count": 3,
                },
                intent_criteria=[
                    "EKS cluster created",
                    "Version 1.28",
                    "Managed node group",
                    "3 nodes",
                ],
            ),
            DPIaCScenario(
                id="dpiac-042",
                name="ECR Repository",
                description="ECR repository with lifecycle policy",
                natural_language_request="Create an ECR repository with image scanning enabled and lifecycle policy to keep only last 10 images",
                category=ServiceCategory.CONTAINER,
                difficulty=DifficultyLevel.EASY,
                cloud_provider="aws",
                required_resources=["aws_ecr_repository", "aws_ecr_lifecycle_policy"],
                validation_rules={
                    "has_ecr": True,
                    "scan_on_push": True,
                    "has_lifecycle_policy": True,
                },
                intent_criteria=[
                    "ECR repository created",
                    "Image scanning enabled",
                    "Lifecycle policy configured",
                ],
            ),
        ]

    def _aws_serverless_scenarios(self) -> List[DPIaCScenario]:
        return [
            DPIaCScenario(
                id="dpiac-050",
                name="Lambda with API Gateway",
                description="Lambda function with REST API",
                natural_language_request="Create a Python Lambda function exposed through API Gateway REST API with /hello endpoint",
                category=ServiceCategory.SERVERLESS,
                difficulty=DifficultyLevel.MEDIUM,
                cloud_provider="aws",
                required_resources=[
                    "aws_lambda_function",
                    "aws_api_gateway_rest_api",
                    "aws_api_gateway_resource",
                    "aws_lambda_permission",
                ],
                validation_rules={
                    "has_lambda": True,
                    "runtime": "python",
                    "has_api_gateway": True,
                    "has_endpoint": True,
                },
                intent_criteria=[
                    "Lambda function created",
                    "Python runtime",
                    "API Gateway configured",
                    "/hello endpoint",
                ],
            ),
            DPIaCScenario(
                id="dpiac-051",
                name="Lambda with S3 Trigger",
                description="Lambda triggered by S3 events",
                natural_language_request="Create a Lambda function that is triggered when objects are created in an S3 bucket",
                category=ServiceCategory.SERVERLESS,
                difficulty=DifficultyLevel.MEDIUM,
                cloud_provider="aws",
                required_resources=[
                    "aws_lambda_function",
                    "aws_s3_bucket",
                    "aws_s3_bucket_notification",
                    "aws_lambda_permission",
                ],
                validation_rules={
                    "has_lambda": True,
                    "has_s3_trigger": True,
                    "event_type": "s3:ObjectCreated:*",
                },
                intent_criteria=[
                    "Lambda function created",
                    "S3 bucket created",
                    "S3 trigger configured",
                ],
            ),
            DPIaCScenario(
                id="dpiac-052",
                name="Step Functions Workflow",
                description="Step Functions state machine",
                natural_language_request="Create a Step Functions state machine that orchestrates 3 Lambda functions sequentially",
                category=ServiceCategory.SERVERLESS,
                difficulty=DifficultyLevel.HARD,
                cloud_provider="aws",
                required_resources=[
                    "aws_sfn_state_machine",
                    "aws_lambda_function",
                    "aws_iam_role",
                ],
                validation_rules={
                    "has_state_machine": True,
                    "lambda_count": 3,
                    "sequential_execution": True,
                },
                intent_criteria=[
                    "State machine created",
                    "3 Lambda functions",
                    "Sequential execution",
                ],
            ),
        ]

    def _multi_service_scenarios(self) -> List[DPIaCScenario]:
        return [
            DPIaCScenario(
                id="dpiac-100",
                name="Three-Tier Web Application",
                description="Complete three-tier architecture",
                natural_language_request="Create a three-tier web application with ALB, EC2 Auto Scaling for the app tier, and RDS PostgreSQL for the database tier",
                category=ServiceCategory.COMPUTE,
                difficulty=DifficultyLevel.HARD,
                cloud_provider="aws",
                required_resources=[
                    "aws_lb",
                    "aws_autoscaling_group",
                    "aws_db_instance",
                    "aws_vpc",
                    "aws_security_group",
                ],
                validation_rules={
                    "has_alb": True,
                    "has_asg": True,
                    "has_rds": True,
                    "has_vpc": True,
                    "three_tier": True,
                },
                intent_criteria=[
                    "ALB for load balancing",
                    "ASG for app tier",
                    "RDS for database",
                    "VPC networking",
                ],
                security_requirements=[
                    "Web tier in public subnet",
                    "App tier in private subnet",
                    "DB tier in private subnet",
                ],
            ),
            DPIaCScenario(
                id="dpiac-101",
                name="Microservices on EKS",
                description="EKS-based microservices deployment",
                natural_language_request="Create an EKS cluster with ALB Ingress Controller and deploy 3 microservices with service discovery",
                category=ServiceCategory.CONTAINER,
                difficulty=DifficultyLevel.HARD,
                cloud_provider="aws",
                required_resources=[
                    "aws_eks_cluster",
                    "aws_eks_node_group",
                    "kubernetes_deployment",
                    "kubernetes_service",
                ],
                validation_rules={
                    "has_eks": True,
                    "has_ingress": True,
                    "microservices_count": 3,
                    "service_discovery": True,
                },
                intent_criteria=[
                    "EKS cluster created",
                    "ALB Ingress",
                    "3 microservices",
                    "Service discovery",
                ],
            ),
            DPIaCScenario(
                id="dpiac-102",
                name="Data Pipeline",
                description="Data processing pipeline",
                natural_language_request="Create a data pipeline with S3 for raw data, Lambda for processing, and DynamoDB for results",
                category=ServiceCategory.SERVERLESS,
                difficulty=DifficultyLevel.HARD,
                cloud_provider="aws",
                required_resources=[
                    "aws_s3_bucket",
                    "aws_lambda_function",
                    "aws_dynamodb_table",
                ],
                validation_rules={
                    "has_s3": True,
                    "has_lambda": True,
                    "has_dynamodb": True,
                    "pipeline_connected": True,
                },
                intent_criteria=[
                    "S3 for raw data",
                    "Lambda processing",
                    "DynamoDB results",
                    "Event-driven",
                ],
            ),
        ]

    def run_benchmark(
        self,
        generator_fn,
        scenarios: Optional[List[DPIaCScenario]] = None,
        verbose: bool = False,
    ) -> BenchmarkResults:
        scenarios = scenarios or self.scenarios
        results = []

        for i, scenario in enumerate(scenarios):
            if verbose:
                print(f"[{i + 1}/{len(scenarios)}] Running: {scenario.name}")

            result = self._evaluate_scenario(scenario, generator_fn)
            results.append(result)

            if verbose:
                status = "✅" if result.success else "❌"
                print(
                    f"  {status} Iterations: {result.iterations}, Deployable: {result.deployable}"
                )

        self.results = results
        return self._aggregate_results(results, scenarios)

    def _evaluate_scenario(
        self,
        scenario: DPIaCScenario,
        generator_fn,
    ) -> EvaluationResult:
        start_time = time.time()

        feedback = []
        best_code = ""
        intent_aligned = False
        security_compliant = False

        for iteration in range(1, self.max_iterations + 1):
            code = generator_fn(
                scenario.natural_language_request,
                iteration,
                feedback,
            )
            best_code = code

            validation = self._validate_code(code, scenario)

            if validation["deployable"]:
                intent_aligned = validation["intent_aligned"]
                security_compliant = validation["security_compliant"]

                return EvaluationResult(
                    scenario_id=scenario.id,
                    success=True,
                    deployable=True,
                    intent_aligned=intent_aligned,
                    security_compliant=security_compliant,
                    iterations=iteration,
                    time_ms=(time.time() - start_time) * 1000,
                    generated_code=code,
                    scores=validation.get("scores", {}),
                )

            feedback = validation.get("errors", [])

        return EvaluationResult(
            scenario_id=scenario.id,
            success=False,
            deployable=False,
            intent_aligned=False,
            security_compliant=False,
            iterations=self.max_iterations,
            time_ms=(time.time() - start_time) * 1000,
            generated_code=best_code,
            errors=feedback,
        )

    def _validate_code(
        self,
        code: str,
        scenario: DPIaCScenario,
    ) -> Dict[str, Any]:
        errors = []

        if not code or len(code.strip()) < 20:
            return {
                "deployable": False,
                "errors": ["Generated code is empty or too short"],
            }

        resources_found = 0
        for resource in scenario.required_resources:
            if resource in code:
                resources_found += 1
            else:
                errors.append(f"Missing required resource: {resource}")

        resource_coverage = (
            resources_found / len(scenario.required_resources)
            if scenario.required_resources
            else 1.0
        )
        rules_passed = 0
        for rule, expected in scenario.validation_rules.items():
            if self._check_rule(code, rule, expected):
                rules_passed += 1

        rule_coverage = (
            rules_passed / len(scenario.validation_rules)
            if scenario.validation_rules
            else 1.0
        )
        intent_score = self._check_intent(code, scenario.intent_criteria)
        security_score = self._check_security(code, scenario.security_requirements)
        deployable = resource_coverage >= 0.7 and rule_coverage >= 0.5

        return {
            "deployable": deployable,
            "intent_aligned": intent_score >= 0.7,
            "security_compliant": security_score >= 0.5,
            "errors": errors,
            "scores": {
                "resource_coverage": resource_coverage,
                "rule_coverage": rule_coverage,
                "intent_score": intent_score,
                "security_score": security_score,
            },
        }

    def _check_rule(self, code: str, rule: str, expected: Any) -> bool:
        code_lower = code.lower()

        if rule.startswith("has_"):
            resource_type = rule[4:]
            return resource_type in code_lower

        if rule == "instance_type":
            return expected in code

        if rule == "engine":
            return (
                f'engine.*=.*"{expected}"' in code
                or f"engine.*{expected}" in code_lower
            )

        if rule == "multi_az":
            return "multi_az" in code_lower and (
                "true" in code_lower or "= true" in code
            )

        return True

    def _check_intent(self, code: str, criteria: List[str]) -> float:
        if not criteria:
            return 1.0

        matches = 0
        code_lower = code.lower()

        for criterion in criteria:
            keywords = criterion.lower().split()
            if any(kw in code_lower for kw in keywords if len(kw) > 3):
                matches += 1

        return matches / len(criteria)

    def _check_security(self, code: str, requirements: List[str]) -> float:
        if not requirements:
            return 1.0

        matches = 0
        code_lower = code.lower()

        for req in requirements:
            keywords = req.lower().split()
            if any(kw in code_lower for kw in keywords if len(kw) > 3):
                matches += 1

        return matches / len(requirements)

    def _aggregate_results(
        self,
        results: List[EvaluationResult],
        scenarios: List[DPIaCScenario],
    ) -> BenchmarkResults:
        total = len(results)
        successful = sum(1 for r in results if r.success)
        first_attempt = sum(1 for r in results if r.success and r.iterations == 1)

        pass_at_1 = sum(1 for r in results if r.success and r.iterations <= 1) / total
        pass_at_5 = sum(1 for r in results if r.success and r.iterations <= 5) / total
        pass_at_10 = sum(1 for r in results if r.success and r.iterations <= 10) / total
        pass_at_25 = sum(1 for r in results if r.success and r.iterations <= 25) / total

        avg_iterations = sum(r.iterations for r in results) / total
        avg_time = sum(r.time_ms for r in results) / total

        intent_rate = sum(1 for r in results if r.intent_aligned) / total
        security_rate = sum(1 for r in results if r.security_compliant) / total

        scenario_map = {s.id: s for s in scenarios}
        by_category = {}
        for result in results:
            scenario = scenario_map.get(result.scenario_id)
            if scenario:
                cat = scenario.category.value
                if cat not in by_category:
                    by_category[cat] = {"total": 0, "success": 0}
                by_category[cat]["total"] += 1
                if result.success:
                    by_category[cat]["success"] += 1

        for cat in by_category:
            by_category[cat]["rate"] = (
                by_category[cat]["success"] / by_category[cat]["total"]
            )

        by_difficulty = {}
        for result in results:
            scenario = scenario_map.get(result.scenario_id)
            if scenario:
                diff = scenario.difficulty.value
                if diff not in by_difficulty:
                    by_difficulty[diff] = {"total": 0, "success": 0}
                by_difficulty[diff]["total"] += 1
                if result.success:
                    by_difficulty[diff]["success"] += 1

        for diff in by_difficulty:
            by_difficulty[diff]["rate"] = (
                by_difficulty[diff]["success"] / by_difficulty[diff]["total"]
            )

        return BenchmarkResults(
            total_scenarios=total,
            successful=successful,
            first_attempt_success=first_attempt,
            pass_at_1=pass_at_1,
            pass_at_5=pass_at_5,
            pass_at_10=pass_at_10,
            pass_at_25=pass_at_25,
            avg_iterations=avg_iterations,
            avg_time_ms=avg_time,
            intent_alignment_rate=intent_rate,
            security_compliance_rate=security_rate,
            by_category=by_category,
            by_difficulty=by_difficulty,
            individual_results=results,
        )


def run_dpiac_eval(generator_fn=None, verbose: bool = True) -> BenchmarkResults:
    benchmark = DPIaCEvalBenchmark(max_iterations=10)

    def mock_generator(request: str, iteration: int, feedback: List[str]) -> str:
        return f"""
# Generated for: {request}
# Iteration: {iteration}

terraform {{
  required_providers {{
    aws = {{
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }}
  }}
}}

provider "aws" {{
  region = "us-west-2"
}}

resource "aws_instance" "main" {{
  ami           = "ami-12345678"
  instance_type = "t2.micro"
}}

resource "aws_security_group" "main" {{
  name = "main-sg"
  
  ingress {{
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }}
}}
"""

    if generator_fn is None:
        generator_fn = mock_generator

    results = benchmark.run_benchmark(generator_fn, verbose=verbose)

    if verbose:
        print("\n" + "=" * 60)
        print("DPIaC-Eval Benchmark Results")
        print("=" * 60)
        print(f"Total Scenarios: {results.total_scenarios}")
        print(
            f"Successful: {results.successful} ({results.successful / results.total_scenarios * 100:.1f}%)"
        )
        print(f"Pass@1: {results.pass_at_1 * 100:.1f}%")
        print(f"Pass@5: {results.pass_at_5 * 100:.1f}%")
        print(f"Pass@10: {results.pass_at_10 * 100:.1f}%")
        print(f"Avg Iterations: {results.avg_iterations:.2f}")
        print(f"Intent Alignment: {results.intent_alignment_rate * 100:.1f}%")
        print(f"Security Compliance: {results.security_compliance_rate * 100:.1f}%")
        print("\nBy Difficulty:")
        for diff, stats in results.by_difficulty.items():
            print(
                f"  {diff}: {stats['success']}/{stats['total']} ({stats['rate'] * 100:.1f}%)"
            )

    return results


if __name__ == "__main__":
    run_dpiac_eval()
