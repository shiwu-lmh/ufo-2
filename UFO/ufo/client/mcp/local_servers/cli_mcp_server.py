#!/usr/bin/env python3
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
CLI MCP Server
Provides MCP server for command line operations:
- Application launching via command execution
"""

import logging
import re
import shlex
import subprocess
import time
from typing import Dict, FrozenSet, List

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from ufo.client.mcp.mcp_registry import MCPRegistry
from ufo.config import get_config

logger = logging.getLogger(__name__)

# Get config
configs = get_config()

# Locally installed applications may be exposed through a short, trusted alias.
# The launcher always resolves the alias to this exact executable; user-provided
# file paths and arguments remain disallowed.
TRUSTED_APPLICATION_PATHS: Dict[str, str] = {
    "netease": r"D:\liminghao\software\CloudMusic\cloudmusic.exe",
    "cloudmusic": r"D:\liminghao\software\CloudMusic\cloudmusic.exe",
    "cloudmusic.exe": r"D:\liminghao\software\CloudMusic\cloudmusic.exe",
    "msedge": r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "msedge.exe": r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "wps": r"C:\Users\Administrator\AppData\Local\Kingsoft\WPS Office\12.1.0.28505\office6\wps.exe",
    "wps.exe": r"C:\Users\Administrator\AppData\Local\Kingsoft\WPS Office\12.1.0.28505\office6\wps.exe",
}

# ---------------------------------------------------------------------------
# Security: only these base commands / executables may be launched.
# Extend as needed for legitimate application-launching use cases.
# ---------------------------------------------------------------------------
ALLOWED_CLI_COMMANDS: FrozenSet[str] = frozenset(
    {
        # Windows applications
        "notepad",
        "notepad.exe",
        "calc",
        "calc.exe",
        "mspaint",
        "mspaint.exe",
        "wordpad",
        "wordpad.exe",
        "msedge",
        "msedge.exe",
        "chrome",
        "chrome.exe",
        "firefox",
        "firefox.exe",
        # Trusted locally installed applications (resolved to fixed executables)
        *TRUSTED_APPLICATION_PATHS,
        # Microsoft Office
        "winword",
        "winword.exe",
        "excel",
        "excel.exe",
        "powerpnt",
        "powerpnt.exe",
        "outlook",
        "outlook.exe",
        "onenote",
        "onenote.exe",
        # Common utilities
        "code",
        "code.exe",
    }
)

# Patterns that indicate malicious or dangerous intent regardless of command
_DANGEROUS_PATTERNS: List[re.Pattern] = [
    re.compile(r"Invoke-Expression|IEX\b", re.IGNORECASE),
    re.compile(r"Invoke-WebRequest|IWR\b|Invoke-RestMethod|IRM\b", re.IGNORECASE),
    re.compile(r"Start-Process\b", re.IGNORECASE),
    re.compile(r"New-Object\s+.*Net\.WebClient", re.IGNORECASE),
    re.compile(r"DownloadString|DownloadFile", re.IGNORECASE),
    re.compile(r"\bAdd-Type\b", re.IGNORECASE),
    re.compile(r"\b(cmd|powershell|pwsh)(\.exe)?\s+[/-]", re.IGNORECASE),
    re.compile(r"[|;&`]\s*(bash|sh|cmd|powershell|pwsh)", re.IGNORECASE),
    re.compile(r"\bNew-Service\b|\bsc\.exe\b", re.IGNORECASE),
    re.compile(r"\breg(\.exe)?\s+(add|delete|import)", re.IGNORECASE),
    re.compile(r"\bschtasks(\.exe)?\b", re.IGNORECASE),
    re.compile(r"\bnet\s+(user|localgroup)\b", re.IGNORECASE),
    re.compile(r"\bSet-ExecutionPolicy\b", re.IGNORECASE),
    re.compile(r"\bRemove-Item\b.*-Recurse", re.IGNORECASE),
    re.compile(r"\brm\s+-rf\b", re.IGNORECASE),
    re.compile(r"[`$]\(", re.IGNORECASE),  # sub-expression / command substitution
    re.compile(r"\bcurl\b|\bwget\b", re.IGNORECASE),
    re.compile(r"\brdp\b|\bmstsc\b", re.IGNORECASE),
    re.compile(r">{1,2}\s*[/\\]", re.IGNORECASE),  # output redirection to paths
]


def _is_trusted_start_alias(tokens: List[str]) -> bool:
    """Allow ``start`` only for a trusted local application alias."""
    return (
        len(tokens) == 2
        and tokens[0].strip().lower() == "start"
        and tokens[1].strip().lower() in TRUSTED_APPLICATION_PATHS
    )


def _launch_arguments(command_str: str) -> List[str]:
    """Resolve an approved command to one executable without shell processing."""
    tokens = shlex.split(command_str)
    if _is_trusted_start_alias(tokens):
        return [TRUSTED_APPLICATION_PATHS[tokens[1].lower()]]

    return [TRUSTED_APPLICATION_PATHS.get(tokens[0].lower(), tokens[0])]


def _is_cli_command_allowed(command_str: str) -> bool:
    """
    Allow only a bare application name from the allow-list, without arguments.
    Reject commands matching dangerous patterns as an additional safeguard.
    """
    if not command_str or not command_str.strip():
        return False

    try:
        tokens = shlex.split(command_str)
    except ValueError:
        return False

    if len(tokens) != 1 and not _is_trusted_start_alias(tokens):
        logger.warning("Blocked CLI command: expected an application name without arguments.")
        return False

    base = tokens[-1].strip().lower()

    # Check base command against allow-list (case-insensitive)
    if not any(base == allowed.lower() for allowed in ALLOWED_CLI_COMMANDS):
        logger.warning("Blocked CLI command not in allow-list: %s", base)
        return False

    # Check for dangerous patterns in the full command string
    for pattern in _DANGEROUS_PATTERNS:
        if pattern.search(command_str):
            logger.warning(
                "Blocked CLI command matching dangerous pattern %s: %s",
                pattern.pattern,
                command_str[:200],
            )
            return False

    return True


@MCPRegistry.register_factory_decorator("CommandLineExecutor")
def create_cli_mcp_server(*args, **kwargs) -> FastMCP:
    """
    Create and return the CLI MCP server instance.
    :return: FastMCP instance for CLI operations.
    """

    cli_mcp = FastMCP("UFO CLI MCP Server")

    @cli_mcp.tool()
    def run_shell(
        bash_command: str,
    ) -> None:
        """
        Launch an allow-listed application by name only, without arguments.
        Trusted local application aliases may also be prefixed with ``start``;
        that spelling is normalized to the same fixed executable. File paths,
        URLs, switches, and Explorer launches are not permitted.
        :param bash_command: A bare allow-listed application name, e.g. notepad.exe.
        :return: None
        """

        if not bash_command:
            raise ToolError("Bash command cannot be empty.")

        if not _is_cli_command_allowed(bash_command):
            raise ToolError(
                "Command blocked by security policy. "
                "Only allow-listed applications may be launched, without arguments."
            )

        try:
            # Parse into argument list and launch without shell=True
            # to prevent shell injection.
            subprocess.Popen(_launch_arguments(bash_command), shell=False)
            time.sleep(5)  # Wait for the application to launch
        except Exception as e:
            raise ToolError(f"Failed to launch application: {str(e)}")

    return cli_mcp
