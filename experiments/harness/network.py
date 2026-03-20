from __future__ import annotations
import asyncio
import logging
from .config import NetworkProfile, NETWORK_PROFILES, Network

log = logging.getLogger(__name__)
EDGE_CLOUD_INTERFACE = "eth0"


async def apply_network_profile(profile: NetworkProfile, interface: str = EDGE_CLOUD_INTERFACE) -> None:
    await _run_cmd(profile.tc_netem_clear(interface), ignore_errors=True)
    await _run_cmd(profile.tc_netem_args(interface))
    log.info("Applied network profile %s: RTT=%dms BW=%dMbps jitter=%dms",
             profile.name, profile.rtt_ms, profile.bandwidth_mbps, profile.jitter_ms)


async def clear_network_profile(interface: str = EDGE_CLOUD_INTERFACE) -> None:
    try:
        proc = await asyncio.create_subprocess_shell(
            f"tc qdisc del dev {interface} root",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
    except Exception as e:
        log.warning("Failed to clear network profile: %s", e)


async def _run_cmd(cmd: str, ignore_errors: bool = False) -> str:
    proc = await asyncio.create_subprocess_shell(
        cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0 and not ignore_errors:
        raise RuntimeError(f"Command failed [{cmd}]: {stderr.decode()}")
    return stdout.decode()


async def validate_rtt(target_host: str, expected_rtt_ms: int, tolerance_ms: int = 10) -> bool:
    try:
        result = await _run_cmd(f"ping -c 10 -q {target_host}")
        for line in result.splitlines():
            if "avg" in line or "rtt" in line:
                parts = line.split("/")
                if len(parts) >= 5:
                    avg_rtt = float(parts[4])
                    ok = abs(avg_rtt - expected_rtt_ms) <= tolerance_ms
                    log.info("RTT validation: measured=%.1fms expected=%dms ok=%s", avg_rtt, expected_rtt_ms, ok)
                    return ok
    except Exception as e:
        log.error("RTT validation failed: %s", e)
    return False
