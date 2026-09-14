"""Hardware detection for model compatibility assessment."""
import platform
import psutil
import subprocess
import json
from typing import Optional


class HardwareDetector:
    """Detects system hardware capabilities."""

    async def detect_all(self) -> dict:
        cpu = await self.detect_cpu()
        memory = await self.detect_memory()
        gpu = await self.detect_gpu()
        disk = await self.detect_disk()

        return {
            "cpu": cpu,
            "memory": memory,
            "gpu": gpu,
            "disk": disk,
            "platform": {
                "system": platform.system(),
                "release": platform.release(),
                "machine": platform.machine(),
                "python_version": platform.python_version(),
            },
        }

    async def detect_cpu(self) -> dict:
        try:
            import cpuinfo
            info = cpuinfo.get_cpu_info()
            return {
                "name": info.get("brand_raw", "Unknown"),
                "cores_physical": psutil.cpu_count(logical=False) or 0,
                "cores_logical": psutil.cpu_count(logical=True) or 0,
                "frequency_mhz": psutil.cpu_freq().current if psutil.cpu_freq() else 0,
                "usage_percent": psutil.cpu_percent(interval=0.1),
                "arch": info.get("arch", platform.machine()),
            }
        except Exception:
            return {
                "name": platform.processor() or "Unknown",
                "cores_physical": psutil.cpu_count(logical=False) or 0,
                "cores_logical": psutil.cpu_count(logical=True) or 0,
                "frequency_mhz": 0,
                "usage_percent": psutil.cpu_percent(interval=0.1),
                "arch": platform.machine(),
            }

    async def detect_memory(self) -> dict:
        mem = psutil.virtual_memory()
        return {
            "total_gb": round(mem.total / (1024 ** 3), 2),
            "available_gb": round(mem.available / (1024 ** 3), 2),
            "used_gb": round(mem.used / (1024 ** 3), 2),
            "usage_percent": mem.percent,
        }

    async def detect_gpu(self) -> dict:
        gpus = []

        # Try nvidia-smi first
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total,memory.used,memory.free,utilization.gpu,driver_version",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) >= 6:
                        gpus.append({
                            "name": parts[0],
                            "vram_total_mb": int(float(parts[1])),
                            "vram_used_mb": int(float(parts[2])),
                            "vram_free_mb": int(float(parts[3])),
                            "utilization_percent": int(float(parts[4])),
                            "driver_version": parts[5],
                            "vendor": "NVIDIA",
                            "cuda_available": True,
                        })
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
            pass

        # Try GPUtil as fallback
        if not gpus:
            try:
                import GPUtil
                nvidia_gpus = GPUtil.getGPUs()
                for gpu in nvidia_gpus:
                    gpus.append({
                        "name": gpu.name,
                        "vram_total_mb": int(gpu.memoryTotal),
                        "vram_used_mb": int(gpu.memoryUsed),
                        "vram_free_mb": int(gpu.memoryFree),
                        "utilization_percent": int(gpu.load * 100),
                        "driver_version": gpu.driver,
                        "vendor": "NVIDIA",
                        "cuda_available": True,
                    })
            except Exception:
                pass

        cuda_available = len(gpus) > 0 and any(g.get("cuda_available") for g in gpus)
        total_vram = sum(g.get("vram_total_mb", 0) for g in gpus)

        return {
            "gpus": gpus,
            "cuda_available": cuda_available,
            "total_vram_mb": total_vram,
            "gpu_count": len(gpus),
        }

    async def detect_disk(self) -> dict:
        partitions = []
        for part in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(part.mountpoint)
                partitions.append({
                    "device": part.device,
                    "mountpoint": part.mountpoint,
                    "total_gb": round(usage.total / (1024 ** 3), 2),
                    "free_gb": round(usage.free / (1024 ** 3), 2),
                    "used_percent": usage.percent,
                })
            except Exception:
                continue

        return {"partitions": partitions}

    def assess_model_compatibility(self, hardware: dict) -> dict:
        """Assess which model sizes can run on this hardware."""
        ram_gb = hardware.get("memory", {}).get("total_gb", 0)
        vram_mb = hardware.get("gpu", {}).get("total_vram_mb", 0)
        vram_gb = vram_mb / 1024

        recommendations = []

        if vram_gb >= 24:
            recommendations.append({"size": "70B Q4", "feasible": True, "note": "Large models supported"})
        if vram_gb >= 8:
            recommendations.append({"size": "13B Q4", "feasible": True, "note": "Medium models supported"})
        if vram_gb >= 4:
            recommendations.append({"size": "7-8B Q4", "feasible": True, "note": "Standard models supported"})
        if vram_gb >= 2:
            recommendations.append({"size": "3B Q4", "feasible": True, "note": "Small models only"})
        if ram_gb >= 16:
            recommendations.append({"size": "7B CPU", "feasible": True, "note": "CPU inference available (slow)"})

        return {
            "ram_gb": ram_gb,
            "vram_gb": round(vram_gb, 1),
            "cuda_available": hardware.get("gpu", {}).get("cuda_available", False),
            "recommendations": recommendations,
            "max_model_size": "8B" if vram_gb >= 4 else "3B" if vram_gb >= 2 else "CPU only",
        }
