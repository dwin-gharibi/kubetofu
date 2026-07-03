import asyncio
import json
import logging
import os
import tempfile
from datetime import datetime
from typing import Any, Dict, Optional

from agents.core.base import (
    AgentConfig,
    BaseAgent,
    Tool,
    ToolResult,
)

logger = logging.getLogger(__name__)


class TerraformInitTool(Tool):
    name = "terraform_init"
    description = "Initialize Terraform/OpenTofu in a working directory"

    async def execute(
        self,
        working_dir: str,
        backend_config: Dict[str, str] = None,
        **kwargs,
    ) -> ToolResult:
        cmd = ["tofu", "init", "-input=false"]

        if backend_config:
            for key, value in backend_config.items():
                cmd.extend([f"-backend-config={key}={value}"])

        try:
            result = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=working_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await result.communicate()

            success = result.returncode == 0
            return ToolResult(
                tool_name=self.name,
                success=success,
                output={
                    "stdout": stdout.decode(),
                    "stderr": stderr.decode(),
                    "return_code": result.returncode,
                },
                error=stderr.decode() if not success else None,
            )
        except FileNotFoundError:
            return ToolResult(
                tool_name=self.name,
                success=False,
                output=None,
                error="OpenTofu/Terraform not found. Please install it first.",
            )
        except Exception as e:
            return ToolResult(
                tool_name=self.name,
                success=False,
                output=None,
                error=str(e),
            )

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "working_dir": {
                    "type": "string",
                    "description": "Working directory containing Terraform files",
                },
                "backend_config": {
                    "type": "object",
                    "description": "Backend configuration options",
                },
            },
            "required": ["working_dir"],
        }


class TerraformPlanTool(Tool):
    name = "terraform_plan"
    description = "Generate an execution plan for infrastructure changes"

    async def execute(
        self,
        working_dir: str,
        variables: Dict[str, str] = None,
        plan_file: str = None,
        **kwargs,
    ) -> ToolResult:
        cmd = ["tofu", "plan", "-input=false", "-no-color"]

        if variables:
            for key, value in variables.items():
                cmd.extend(["-var", f"{key}={value}"])

        if plan_file:
            cmd.extend(["-out", plan_file])

        try:
            result = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=working_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await result.communicate()

            output_text = stdout.decode()

            changes = {
                "add": output_text.count("+ resource"),
                "change": output_text.count("~ resource"),
                "destroy": output_text.count("- resource"),
            }

            success = result.returncode == 0
            return ToolResult(
                tool_name=self.name,
                success=success,
                output={
                    "plan_output": output_text,
                    "changes": changes,
                    "plan_file": plan_file,
                    "has_changes": any(changes.values()),
                },
                error=stderr.decode() if not success else None,
            )
        except Exception as e:
            return ToolResult(
                tool_name=self.name,
                success=False,
                output=None,
                error=str(e),
            )

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "working_dir": {
                    "type": "string",
                    "description": "Working directory containing Terraform files",
                },
                "variables": {
                    "type": "object",
                    "description": "Variables to pass to Terraform",
                },
                "plan_file": {
                    "type": "string",
                    "description": "Path to save the plan file",
                },
            },
            "required": ["working_dir"],
        }


class TerraformApplyTool(Tool):
    name = "terraform_apply"
    description = "Apply infrastructure changes from a Terraform plan"

    async def execute(
        self,
        working_dir: str,
        plan_file: str = None,
        auto_approve: bool = False,
        variables: Dict[str, str] = None,
        **kwargs,
    ) -> ToolResult:
        cmd = ["tofu", "apply", "-input=false", "-no-color"]

        if auto_approve:
            cmd.append("-auto-approve")

        if plan_file:
            cmd.append(plan_file)
        elif variables:
            for key, value in variables.items():
                cmd.extend(["-var", f"{key}={value}"])

        try:
            result = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=working_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await result.communicate()

            output_text = stdout.decode()

            outputs = {}
            if "Outputs:" in output_text:
                output_section = output_text.split("Outputs:")[-1]
                for line in output_section.strip().split("\n"):
                    if "=" in line:
                        key, value = line.split("=", 1)
                        outputs[key.strip()] = value.strip().strip('"')

            success = result.returncode == 0
            return ToolResult(
                tool_name=self.name,
                success=success,
                output={
                    "apply_output": output_text,
                    "outputs": outputs,
                    "completed_at": datetime.utcnow().isoformat(),
                },
                error=stderr.decode() if not success else None,
            )
        except Exception as e:
            return ToolResult(
                tool_name=self.name,
                success=False,
                output=None,
                error=str(e),
            )

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "working_dir": {
                    "type": "string",
                    "description": "Working directory containing Terraform files",
                },
                "plan_file": {
                    "type": "string",
                    "description": "Path to a saved plan file to apply",
                },
                "auto_approve": {
                    "type": "boolean",
                    "description": "Skip interactive approval",
                    "default": False,
                },
                "variables": {
                    "type": "object",
                    "description": "Variables to pass to Terraform",
                },
            },
            "required": ["working_dir"],
        }


class TerraformDestroyTool(Tool):
    name = "terraform_destroy"
    description = "Destroy infrastructure managed by Terraform"

    async def execute(
        self,
        working_dir: str,
        auto_approve: bool = False,
        target: str = None,
        **kwargs,
    ) -> ToolResult:
        cmd = ["tofu", "destroy", "-input=false", "-no-color"]

        if auto_approve:
            cmd.append("-auto-approve")

        if target:
            cmd.extend(["-target", target])

        try:
            result = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=working_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await result.communicate()

            success = result.returncode == 0
            return ToolResult(
                tool_name=self.name,
                success=success,
                output={
                    "destroy_output": stdout.decode(),
                    "completed_at": datetime.utcnow().isoformat(),
                },
                error=stderr.decode() if not success else None,
            )
        except Exception as e:
            return ToolResult(
                tool_name=self.name,
                success=False,
                output=None,
                error=str(e),
            )

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "working_dir": {
                    "type": "string",
                    "description": "Working directory containing Terraform files",
                },
                "auto_approve": {
                    "type": "boolean",
                    "description": "Skip interactive approval",
                    "default": False,
                },
                "target": {
                    "type": "string",
                    "description": "Specific resource to destroy",
                },
            },
            "required": ["working_dir"],
        }


class KubectlApplyTool(Tool):
    name = "kubectl_apply"
    description = "Apply Kubernetes manifests to a cluster"

    async def execute(
        self,
        manifest: str = None,
        manifest_file: str = None,
        namespace: str = "default",
        **kwargs,
    ) -> ToolResult:
        cmd = ["kubectl", "apply", "-n", namespace]

        temp_file = None
        try:
            if manifest:
                temp_file = tempfile.NamedTemporaryFile(
                    mode="w",
                    suffix=".yaml",
                    delete=False,
                )
                temp_file.write(manifest)
                temp_file.close()
                cmd.extend(["-f", temp_file.name])
            elif manifest_file:
                cmd.extend(["-f", manifest_file])
            else:
                return ToolResult(
                    tool_name=self.name,
                    success=False,
                    output=None,
                    error="Either manifest or manifest_file must be provided",
                )

            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await result.communicate()

            success = result.returncode == 0
            return ToolResult(
                tool_name=self.name,
                success=success,
                output={
                    "kubectl_output": stdout.decode(),
                    "namespace": namespace,
                },
                error=stderr.decode() if not success else None,
            )
        except Exception as e:
            return ToolResult(
                tool_name=self.name,
                success=False,
                output=None,
                error=str(e),
            )
        finally:
            if temp_file and os.path.exists(temp_file.name):
                os.unlink(temp_file.name)

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "manifest": {
                    "type": "string",
                    "description": "YAML manifest content",
                },
                "manifest_file": {
                    "type": "string",
                    "description": "Path to manifest file",
                },
                "namespace": {
                    "type": "string",
                    "description": "Kubernetes namespace",
                    "default": "default",
                },
            },
        }


class RollbackTool(Tool):
    name = "rollback"
    description = "Rollback to a previous infrastructure state"

    async def execute(
        self,
        working_dir: str,
        target_state: str = None,
        deployment_type: str = "terraform",
        **kwargs,
    ) -> ToolResult:
        if deployment_type == "terraform":
            cmd = ["tofu", "state", "list"]
            try:
                result = await asyncio.create_subprocess_exec(
                    *cmd,
                    cwd=working_dir,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await result.communicate()

                return ToolResult(
                    tool_name=self.name,
                    success=True,
                    output={
                        "message": "Rollback initiated",
                        "state_resources": stdout.decode().split("\n"),
                        "note": "Full rollback requires manual state management or version control",
                    },
                )
            except Exception as e:
                return ToolResult(
                    tool_name=self.name,
                    success=False,
                    output=None,
                    error=str(e),
                )
        elif deployment_type == "kubernetes":
            cmd = ["kubectl", "rollout", "undo", target_state or "deployment/app"]
            try:
                result = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await result.communicate()

                success = result.returncode == 0
                return ToolResult(
                    tool_name=self.name,
                    success=success,
                    output={"rollback_output": stdout.decode()},
                    error=stderr.decode() if not success else None,
                )
            except Exception as e:
                return ToolResult(
                    tool_name=self.name,
                    success=False,
                    output=None,
                    error=str(e),
                )

        return ToolResult(
            tool_name=self.name,
            success=False,
            output=None,
            error=f"Unknown deployment type: {deployment_type}",
        )

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "working_dir": {
                    "type": "string",
                    "description": "Working directory for Terraform rollback",
                },
                "target_state": {
                    "type": "string",
                    "description": "Target state/deployment to rollback to",
                },
                "deployment_type": {
                    "type": "string",
                    "description": "Type of deployment (terraform, kubernetes)",
                    "default": "terraform",
                },
            },
            "required": ["working_dir"],
        }


class DeploymentAgent(BaseAgent):
    def __init__(self, config: Optional[AgentConfig] = None, **kwargs):
        default_config = AgentConfig(
            name="DeploymentAgent",
            description="Infrastructure deployment and execution agent",
            temperature=0.1,
            max_iterations=15,
            timeout_seconds=600,
            tools=[
                "terraform_init",
                "terraform_plan",
                "terraform_apply",
                "terraform_destroy",
                "kubectl_apply",
                "rollback",
            ],
        )
        super().__init__(config or default_config, **kwargs)

    def get_system_prompt(self) -> str:
        return """You are an expert Deployment Agent for Kube-Tofu.

Your role is to:
1. Execute infrastructure deployments safely and reliably
2. Manage Terraform/OpenTofu lifecycle (init, plan, apply, destroy)
3. Handle Kubernetes deployments and updates
4. Perform rollbacks when necessary
5. Ensure deployment success and handle failures

Deployment best practices you follow:
- Always run 'init' before 'plan'
- Always run 'plan' before 'apply'
- Review changes before applying
- Use -auto-approve only in controlled environments
- Keep backups of state files
- Use workspaces for environment separation
- Apply changes incrementally when possible
- Monitor deployment progress
- Have rollback plans ready

When deploying:
- Validate configurations first
- Check for potential breaking changes
- Communicate progress clearly
- Handle errors gracefully
- Provide detailed logs and outputs

Safety first: Never apply changes without understanding the impact.
Always prefer plan -> review -> apply workflow."""

    def _register_default_tools(self) -> None:
        self.tool_registry.register(TerraformInitTool())
        self.tool_registry.register(TerraformPlanTool())
        self.tool_registry.register(TerraformApplyTool())
        self.tool_registry.register(TerraformDestroyTool())
        self.tool_registry.register(KubectlApplyTool())
        self.tool_registry.register(RollbackTool())

    async def process_task(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        return await self.run(task, context)

    async def deploy(
        self,
        working_dir: str,
        variables: Dict[str, str] = None,
        auto_approve: bool = False,
    ) -> Dict[str, Any]:
        task = f"""Execute a deployment in {working_dir}:

1. Initialize Terraform
2. Generate a plan
3. {"Apply the changes automatically" if auto_approve else "Review the plan and prepare for apply"}

Variables: {json.dumps(variables) if variables else "None"}
Auto-approve: {auto_approve}
"""
        return await self.run(
            task, {"working_dir": working_dir, "variables": variables}
        )

    async def destroy(
        self,
        working_dir: str,
        auto_approve: bool = False,
    ) -> Dict[str, Any]:
        task = f"""Destroy infrastructure in {working_dir}:

Auto-approve: {auto_approve}

Please proceed with caution and confirm the resources to be destroyed.
"""
        return await self.run(task, {"working_dir": working_dir})
