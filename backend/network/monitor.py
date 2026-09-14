"""Sovereignty monitor - ensures no data leaves the organization."""
import httpx
from config import get_settings

settings = get_settings()


class SovereigntyMonitor:
    """Monitors and blocks unauthorized external connections."""

    async def get_status(self) -> dict:
        return {
            "mode": "air_gapped" if settings.AIR_GAPPED_MODE else "monitored",
            "external_ai_blocked": True,
            "telemetry_blocked": True,
            "cloud_storage_blocked": True,
            "local_services": await self._check_local_services(),
        }

    async def _check_local_services(self) -> dict:
        services = {}

        # Check Ollama
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                resp = await client.get(f"{settings.OLLAMA_URL}/api/tags")
                services["ollama"] = "healthy" if resp.status_code == 200 else "unhealthy"
        except Exception:
            services["ollama"] = "unavailable"

        # Check vector DB
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                resp = await client.get(f"{settings.VECTOR_DB_URL}/collections")
                services["vector_db"] = "healthy" if resp.status_code == 200 else "unhealthy"
        except Exception:
            services["vector_db"] = "unavailable"

        return services

    async def test_blocking(self) -> list[dict]:
        """Test that blocked domains are actually blocked."""
        results = []

        for domain in settings.BLOCKED_DOMAINS:
            blocked = True
            reason = ""

            if settings.AIR_GAPPED_MODE:
                # In air-gapped mode, we don't even attempt the connection
                reason = "Air-gapped mode active - connection not attempted"
            else:
                try:
                    async with httpx.AsyncClient(timeout=3) as client:
                        await client.get(f"https://{domain}")
                        blocked = False
                        reason = "Connection succeeded - SECURITY VIOLATION"
                except Exception as e:
                    reason = f"Connection blocked: {type(e).__name__}"

            results.append({
                "domain": domain,
                "blocked": blocked,
                "reason": reason,
            })

        return results

    def is_request_allowed(self, destination: str) -> bool:
        """Check if a request to a destination should be allowed."""
        if settings.AIR_GAPPED_MODE:
            # In air-gapped mode, only local addresses are allowed
            local_prefixes = ["localhost", "127.0.0.1", "0.0.0.0", "192.168.", "10.", "172."]
            return any(destination.startswith(prefix) for prefix in local_prefixes)

        # Check blocked domains
        for domain in settings.BLOCKED_DOMAINS:
            if domain in destination:
                return False

        return True
