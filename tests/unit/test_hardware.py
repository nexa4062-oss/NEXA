import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

import pytest
from hardware.detector import HardwareDetector


class TestHardwareDetection:
    def setup_method(self):
        self.detector = HardwareDetector()

    @pytest.mark.asyncio
    async def test_detects_cpu(self):
        cpu = await self.detector.detect_cpu()
        assert "name" in cpu
        assert "cores_physical" in cpu
        assert "cores_logical" in cpu
        assert cpu["cores_physical"] > 0
        assert cpu["cores_logical"] > 0

    @pytest.mark.asyncio
    async def test_detects_memory(self):
        mem = await self.detector.detect_memory()
        assert "total_gb" in mem
        assert "available_gb" in mem
        assert "usage_percent" in mem
        assert mem["total_gb"] > 0
        assert 0 <= mem["usage_percent"] <= 100

    @pytest.mark.asyncio
    async def test_detects_gpu(self):
        gpu = await self.detector.detect_gpu()
        assert "gpus" in gpu
        assert "cuda_available" in gpu
        assert "total_vram_mb" in gpu
        assert "gpu_count" in gpu
        assert isinstance(gpu["gpus"], list)

    @pytest.mark.asyncio
    async def test_detects_disk(self):
        disk = await self.detector.detect_disk()
        assert "partitions" in disk
        assert len(disk["partitions"]) > 0
        for p in disk["partitions"]:
            assert "total_gb" in p
            assert "free_gb" in p

    @pytest.mark.asyncio
    async def test_full_detection(self):
        hw = await self.detector.detect_all()
        assert "cpu" in hw
        assert "memory" in hw
        assert "gpu" in hw
        assert "disk" in hw
        assert "platform" in hw

    def test_model_compatibility_assessment(self):
        hw = {
            "memory": {"total_gb": 8},
            "gpu": {"total_vram_mb": 4096, "cuda_available": True},
        }
        compat = self.detector.assess_model_compatibility(hw)
        assert "recommendations" in compat
        assert "max_model_size" in compat
        assert compat["vram_gb"] == 4.0
        assert compat["cuda_available"] is True
