import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Optional, Union

from qwen_agent.tools.base import BaseTool, register_tool

DEFAULT_PYTHON_HOME = r"D:\AnacondaInstall\envs\py3.9-torch"
DEFAULT_TIMEOUT_SECONDS = int(os.getenv("PYTHON_TOOL_TIMEOUT", "30"))
_ENV_NAME_RE = re.compile(r"^[A-Z_][A-Z0-9_]*$")


def _looks_like_env_name(text: str) -> bool:
    return bool(_ENV_NAME_RE.match(text or ""))


def _resolve_python_executable(path_or_home: str) -> str:
    path = Path(path_or_home)
    name = path.name.lower()
    if name in {"python", "python.exe"}:
        return str(path)
    return str(path / "python.exe")


@register_tool("PythonInterpreter", allow_overwrite=True)
class PythonInterpreter(BaseTool):
    name = "PythonInterpreter"
    description = (
        "Execute Python code with a local interpreter. "
        "Use print() to output results."
    )
    parameters = {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Python code to execute.",
            },
            "timeout": {
                "type": "integer",
                "description": "Execution timeout in seconds. Default 30.",
            },
        },
        "required": ["code"],
    }

    def __init__(self, cfg: Optional[Dict] = None):
        super().__init__(cfg)
        self.cfg = cfg or {}

        configured_path = (
            self.cfg.get("python_path")
            or self._resolve_cfg_env_or_value("python_path_env")
            or os.getenv("MEMFIN_PYTHON_PATH")
            or self.cfg.get("python_path_default")
            or DEFAULT_PYTHON_HOME
        )
        self.python_executable = _resolve_python_executable(str(configured_path))
        self.default_timeout_seconds = self._resolve_timeout()

    def _resolve_cfg_env_or_value(self, key: str) -> str:
        raw = str(self.cfg.get(key, "")).strip()
        if not raw:
            return ""

        env_val = os.getenv(raw, "")
        if env_val:
            return env_val

        if _looks_like_env_name(raw):
            return ""

        return raw

    def _resolve_timeout(self) -> int:
        raw = str(self.cfg.get("timeout_seconds_env", "")).strip()
        if raw:
            env_val = os.getenv(raw, "")
            candidate = env_val or raw
            try:
                if not _looks_like_env_name(candidate):
                    return int(candidate)
            except ValueError:
                pass

        try:
            return int(self.cfg.get("timeout_seconds_default", DEFAULT_TIMEOUT_SECONDS))
        except (TypeError, ValueError):
            return DEFAULT_TIMEOUT_SECONDS

    def _parse_params(self, params: Union[str, dict]) -> Dict:
        if isinstance(params, dict):
            return params
        if isinstance(params, str):
            raw = params.strip()
            if not raw:
                return {}
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass
            return {"code": raw}
        return {}

    def _extract_code(self, code_text: str) -> str:
        text = code_text.strip()
        match = re.search(r"```(?:python)?\s*(.*?)```", text, flags=re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1).strip()
        return text

    def call(self, params: Union[str, dict], **kwargs) -> str:
        parsed = self._parse_params(params)
        raw_code = str(parsed.get("code", "")).strip()
        if not raw_code:
            return "[PythonInterpreter] invalid params: missing 'code'."

        code = self._extract_code(raw_code)
        if not code:
            return "[PythonInterpreter] empty code after parsing."

        if not os.path.exists(self.python_executable):
            return (
                f"[PythonInterpreter] python executable not found: "
                f"{self.python_executable}"
            )

        timeout_seconds = int(parsed.get("timeout", self.default_timeout_seconds))

        temp_file_path = ""
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".py",
                delete=False,
                encoding="utf-8",
            ) as temp_file:
                temp_file.write(code)
                temp_file_path = temp_file.name

            completed = subprocess.run(
                [self.python_executable, "-X", "utf8", temp_file_path],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_seconds,
                env={
                    **os.environ,
                    "PYTHONIOENCODING": "utf-8",
                    "PYTHONUTF8": "1",
                },
            )

            output_parts = []
            if completed.stdout:
                output_parts.append(f"stdout:\n{completed.stdout.strip()}")
            if completed.stderr:
                output_parts.append(f"stderr:\n{completed.stderr.strip()}")
            if completed.returncode != 0:
                output_parts.append(f"exit_code: {completed.returncode}")

            return "\n\n".join(output_parts) if output_parts else "Finished execution."

        except subprocess.TimeoutExpired:
            return f"[PythonInterpreter] TimeoutError: exceeded {timeout_seconds} seconds."
        except Exception as exc:
            return f"[PythonInterpreter] execution failed: {exc}"
        finally:
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                except OSError:
                    pass
