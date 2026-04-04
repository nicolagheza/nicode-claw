from __future__ import annotations

import logging
import shutil
import subprocess

from agno.tools.toolkit import Toolkit

logger = logging.getLogger(__name__)


class InstallTools(Toolkit):

    def __init__(self):
        super().__init__(name="install_tools")
        self.register(self.install_package)

    def install_package(self, package_name: str) -> str:
        """Install a Python package using uv. Use this when a package is missing.

        Args:
            package_name: The name of the package to install (e.g. "openpyxl", "requests").

        Returns:
            A success or error message.
        """
        uv_path = shutil.which("uv")
        if not uv_path:
            return "Error: uv not found in PATH."

        try:
            result = subprocess.run(
                [uv_path, "add", package_name],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode == 0:
                return f"Package '{package_name}' installed successfully."
            return f"Error installing {package_name}: {result.stderr}"
        except Exception as e:
            logger.exception("Error installing package %s", package_name)
            return f"Error installing {package_name}: {e}"
