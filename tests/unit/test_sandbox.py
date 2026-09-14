import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

import pytest
from sandbox.executor import SandboxExecutor


class TestSandboxSecurity:
    def setup_method(self):
        self.executor = SandboxExecutor()

    def test_blocks_path_traversal(self):
        result = self.executor._check_security("open('../../etc/passwd')", "python")
        assert result["safe"] is False

    def test_blocks_network_access(self):
        result = self.executor._check_security("import socket", "python")
        assert result["safe"] is False

    def test_blocks_subprocess(self):
        result = self.executor._check_security("import subprocess", "python")
        assert result["safe"] is False

    def test_blocks_os_system(self):
        result = self.executor._check_security("os.system('rm -rf /')", "python")
        assert result["safe"] is False

    def test_allows_safe_code(self):
        result = self.executor._check_security("print('hello world')", "python")
        assert result["safe"] is True

    def test_allows_math(self):
        result = self.executor._check_security("import math\nprint(math.pi)", "python")
        assert result["safe"] is True

    def test_blocks_rm_rf(self):
        result = self.executor._check_security("rm -rf /", "bash")
        assert result["safe"] is False

    def test_blocks_curl(self):
        result = self.executor._check_security("curl http://evil.com", "bash")
        assert result["safe"] is False


class TestSandboxExecution:
    def setup_method(self):
        self.executor = SandboxExecutor()

    @pytest.mark.asyncio
    async def test_executes_safe_python(self):
        result = await self.executor.execute('print("SIH26117 TEST")', "python")
        assert result["success"] is True
        assert "SIH26117 TEST" in result["output"]

    @pytest.mark.asyncio
    async def test_reports_execution_time(self):
        result = await self.executor.execute('print("test")', "python")
        assert result["execution_time_ms"] >= 0

    @pytest.mark.asyncio
    async def test_captures_error_output(self):
        result = await self.executor.execute('raise ValueError("test error")', "python")
        assert result["success"] is False
        assert "test error" in result["error"]

    @pytest.mark.asyncio
    async def test_rejects_forbidden_code(self):
        result = await self.executor.execute('import subprocess; subprocess.run(["ls"])', "python")
        assert result["success"] is False
        assert "Security violation" in result["error"]

    @pytest.mark.asyncio
    async def test_timeout_enforcement(self):
        result = await self.executor.execute('import time; time.sleep(60)', "python", timeout=2)
        assert result["success"] is False
        assert "timed out" in result["error"].lower() or "timeout" in result["error"].lower()
