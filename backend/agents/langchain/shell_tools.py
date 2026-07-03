import logging
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class CommandSafetyChecker:
    BLOCKED_COMMANDS = [
        "rm -rf /",
        "rm -rf /*",
        "mkfs",
        "dd if=/dev/zero",
        ":(){ :|:& };:",
        "> /dev/sda",
        "mv /* /dev/null",
        "wget.*\\|.*sh",
        "curl.*\\|.*bash",
    ]

    DANGEROUS_PATTERNS = [
        r"rm\s+-rf",
        r"rm\s+-r",
        r"sudo\s+",
        r"chmod\s+777",
        r"chown\s+",
        r">\s*/etc/",
        r">\s*/var/",
        r"kill\s+-9",
        r"pkill",
        r"systemctl\s+(stop|restart|disable)",
    ]

    ALLOWED_PREFIXES = [
        "terraform",
        "tofu",
        "kubectl",
        "helm",
        "docker",
        "git",
        "aws",
        "gcloud",
        "az",
        "arvan",
        "cat",
        "grep",
        "find",
        "ls",
        "pwd",
        "echo",
        "head",
        "tail",
        "wc",
        "jq",
        "yq",
        "curl",
        "wget",
    ]

    @classmethod
    def is_blocked(cls, command: str) -> bool:
        command_lower = command.lower().strip()

        for blocked in cls.BLOCKED_COMMANDS:
            if blocked in command_lower:
                return True

        return False

    @classmethod
    def needs_approval(cls, command: str) -> bool:
        for pattern in cls.DANGEROUS_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                return True
        return False

    @classmethod
    def is_allowed_prefix(cls, command: str) -> bool:
        command_lower = command.lower().strip()

        for prefix in cls.ALLOWED_PREFIXES:
            if command_lower.startswith(prefix):
                return True

        return False

    @classmethod
    def validate(cls, command: str, allow_dangerous: bool = False) -> Dict[str, Any]:
        if cls.is_blocked(command):
            return {
                "allowed": False,
                "reason": "Command is blocked for security reasons",
                "needs_approval": False,
            }

        if cls.needs_approval(command) and not allow_dangerous:
            return {
                "allowed": False,
                "reason": "Command requires human approval",
                "needs_approval": True,
            }

        if not cls.is_allowed_prefix(command):
            return {
                "allowed": False,
                "reason": f"Command prefix not in allowed list. Allowed: {', '.join(cls.ALLOWED_PREFIXES[:10])}...",
                "needs_approval": False,
            }

        return {
            "allowed": True,
            "reason": "Command passed safety checks",
            "needs_approval": False,
        }


class ShellCommandInput(BaseModel):
    command: str = Field(description="The shell command to execute")
    working_dir: Optional[str] = Field(default=None, description="Working directory")
    timeout: int = Field(default=60, description="Timeout in seconds")
    env_vars: Optional[Dict[str, str]] = Field(
        default=None, description="Environment variables"
    )


class ShellCommandTool(BaseTool):
    name: str = "shell_command"
    description: str = """Execute a shell command. Use for infrastructure operations like:
- terraform/tofu commands
- kubectl commands
- git operations
- File inspection (cat, ls, grep)
Commands are validated for safety before execution."""
    args_schema: Type[BaseModel] = ShellCommandInput

    allow_dangerous: bool = False
    max_output_length: int = 10000

    def _run(
        self,
        command: str,
        working_dir: Optional[str] = None,
        timeout: int = 60,
        env_vars: Optional[Dict[str, str]] = None,
    ) -> str:
        validation = CommandSafetyChecker.validate(command, self.allow_dangerous)

        if not validation["allowed"]:
            if validation["needs_approval"]:
                return f"⚠️ APPROVAL REQUIRED: This command needs human approval:\n{command}\n\nReason: {validation['reason']}"
            return f"❌ BLOCKED: {validation['reason']}\nCommand: {command}"

        env = os.environ.copy()
        if env_vars:
            env.update(env_vars)

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=working_dir,
                env=env,
            )

            output = ""

            if result.stdout:
                output += f"STDOUT:\n{result.stdout}"

            if result.stderr:
                output += f"\nSTDERR:\n{result.stderr}"

            if len(output) > self.max_output_length:
                output = output[: self.max_output_length] + "\n... (output truncated)"

            if result.returncode != 0:
                output = f"Exit code: {result.returncode}\n{output}"

            return output or "Command executed successfully (no output)"

        except subprocess.TimeoutExpired:
            return f"❌ Command timed out after {timeout} seconds"
        except Exception as e:
            return f"❌ Error executing command: {e}"


class AsyncShellCommandInput(BaseModel):
    command: str = Field(description="Command to run in background")
    name: str = Field(description="Name for this background process")


class AsyncShellCommandTool(BaseTool):
    name: str = "async_shell_command"
    description: str = "Run a command in the background. Useful for long-running operations like deployments."
    args_schema: Type[BaseModel] = AsyncShellCommandInput

    _processes: Dict[str, subprocess.Popen] = {}

    def _run(self, command: str, name: str) -> str:
        validation = CommandSafetyChecker.validate(command)

        if not validation["allowed"]:
            return f"❌ BLOCKED: {validation['reason']}"

        try:
            process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self._processes[name] = process

            return f"✅ Started background process '{name}' (PID: {process.pid})"

        except Exception as e:
            return f"❌ Error starting process: {e}"


class FileReadInput(BaseModel):
    path: str = Field(description="Path to the file")
    start_line: Optional[int] = Field(
        default=None, description="Start line (1-indexed)"
    )
    end_line: Optional[int] = Field(default=None, description="End line (1-indexed)")


class FileReadTool(BaseTool):
    name: str = "file_read"
    description: str = (
        "Read the contents of a file. Can specify line range for large files."
    )
    args_schema: Type[BaseModel] = FileReadInput

    allowed_paths: List[str] = ["/tmp", "./", "/workspace", "/home"]
    max_file_size: int = 1_000_000

    def _is_path_allowed(self, path: str) -> bool:
        abs_path = os.path.abspath(path)

        for allowed in self.allowed_paths:
            if abs_path.startswith(os.path.abspath(allowed)):
                return True

        return False

    def _run(
        self,
        path: str,
        start_line: Optional[int] = None,
        end_line: Optional[int] = None,
    ) -> str:
        if not self._is_path_allowed(path):
            return "❌ Access denied: Path not in allowed directories"

        if not os.path.exists(path):
            return f"❌ File not found: {path}"

        if os.path.getsize(path) > self.max_file_size:
            return f"❌ File too large (>{self.max_file_size} bytes). Use line range."

        try:
            with open(path, "r") as f:
                if start_line or end_line:
                    lines = f.readlines()
                    start = (start_line or 1) - 1
                    end = end_line or len(lines)
                    content = "".join(lines[start:end])
                else:
                    content = f.read()

            return content

        except Exception as e:
            return f"❌ Error reading file: {e}"


class FileWriteInput(BaseModel):
    path: str = Field(description="Path to write to")
    content: str = Field(description="Content to write")
    append: bool = Field(default=False, description="Append instead of overwrite")


class FileWriteTool(BaseTool):
    name: str = "file_write"
    description: str = "Write content to a file. Can overwrite or append."
    args_schema: Type[BaseModel] = FileWriteInput

    allowed_paths: List[str] = ["/tmp", "./", "/workspace"]

    def _is_path_allowed(self, path: str) -> bool:
        abs_path = os.path.abspath(path)

        for allowed in self.allowed_paths:
            if abs_path.startswith(os.path.abspath(allowed)):
                return True

        return False

    def _run(
        self,
        path: str,
        content: str,
        append: bool = False,
    ) -> str:
        if not self._is_path_allowed(path):
            return "❌ Access denied: Path not in allowed directories"

        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

        try:
            mode = "a" if append else "w"
            with open(path, mode) as f:
                f.write(content)

            action = "Appended to" if append else "Wrote"
            return f"✅ {action} {path} ({len(content)} bytes)"

        except Exception as e:
            return f"❌ Error writing file: {e}"


class FileListInput(BaseModel):
    path: str = Field(default=".", description="Directory path")
    pattern: Optional[str] = Field(default=None, description="Glob pattern")
    recursive: bool = Field(default=False, description="Recursive listing")


class FileListTool(BaseTool):
    name: str = "file_list"
    description: str = "List files and directories. Supports glob patterns."
    args_schema: Type[BaseModel] = FileListInput

    def _run(
        self,
        path: str = ".",
        pattern: Optional[str] = None,
        recursive: bool = False,
    ) -> str:
        try:
            p = Path(path)

            if not p.exists():
                return f"❌ Path not found: {path}"

            if pattern:
                if recursive:
                    files = list(p.rglob(pattern))
                else:
                    files = list(p.glob(pattern))
            else:
                if recursive:
                    files = list(p.rglob("*"))
                else:
                    files = list(p.iterdir())

            output = []
            for f in sorted(files)[:100]:
                if f.is_dir():
                    output.append(f"📁 {f}")
                else:
                    size = f.stat().st_size
                    output.append(f"📄 {f} ({size} bytes)")

            if len(files) > 100:
                output.append(f"... and {len(files) - 100} more files")

            return "\n".join(output) or "Directory is empty"

        except Exception as e:
            return f"❌ Error listing files: {e}"


class PythonCodeInput(BaseModel):
    code: str = Field(description="Python code to execute")
    timeout: int = Field(default=30, description="Timeout in seconds")


class PythonCodeTool(BaseTool):
    name: str = "python_execute"
    description: str = """Execute Python code for calculations, data processing, or testing.
Useful for:
- JSON/YAML parsing
- Data calculations
- API testing
- Script validation"""
    args_schema: Type[BaseModel] = PythonCodeInput

    BLOCKED_IMPORTS = [
        "os.system",
        "subprocess",
        "shutil.rmtree",
        "__import__",
        "eval",
        "exec",
        "compile",
    ]

    def _validate_code(self, code: str) -> bool:
        for blocked in self.BLOCKED_IMPORTS:
            if blocked in code:
                return False
        return True

    def _run(self, code: str, timeout: int = 30) -> str:
        if not self._validate_code(code):
            return "❌ Code contains blocked patterns for security"

        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".py",
            delete=False,
        ) as f:
            f.write(code)
            temp_path = f.name

        try:
            result = subprocess.run(
                ["python3", temp_path],
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            output = ""
            if result.stdout:
                output += result.stdout
            if result.stderr:
                output += f"\nSTDERR:\n{result.stderr}"

            if result.returncode != 0:
                output = f"Exit code: {result.returncode}\n{output}"

            return output or "Code executed successfully (no output)"

        except subprocess.TimeoutExpired:
            return f"❌ Code execution timed out after {timeout} seconds"
        except Exception as e:
            return f"❌ Error executing code: {e}"
        finally:
            os.unlink(temp_path)


def create_shell_tools(
    allow_dangerous: bool = False,
    allowed_paths: List[str] = None,
) -> List[BaseTool]:
    shell_tool = ShellCommandTool()
    shell_tool.allow_dangerous = allow_dangerous

    file_read = FileReadTool()
    file_write = FileWriteTool()

    if allowed_paths:
        file_read.allowed_paths = allowed_paths
        file_write.allowed_paths = allowed_paths

    return [
        shell_tool,
        AsyncShellCommandTool(),
        file_read,
        file_write,
        FileListTool(),
        PythonCodeTool(),
    ]
