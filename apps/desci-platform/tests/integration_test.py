import json
import os
import sys

import pytest
import requests
from dotenv import load_dotenv

# Env Setup
load_dotenv(dotenv_path="../biolinker/.env")

BASE_URL = os.getenv("BIOLINKER_API_URL", "http://127.0.0.1:8001")
NFT_CONTRACT = os.getenv("NFT_CONTRACT_ADDRESS")


def _ensure_utf8_streams() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


_ensure_utf8_streams()


@pytest.mark.integration
@pytest.mark.external
def test_minting() -> None:
    print(f"Starting Integration Test: Minting on {NFT_CONTRACT}")

    try:
        health = requests.get(f"{BASE_URL}/health", timeout=5)
        if health.status_code >= 500:
            pytest.skip(f"BioLinker service unhealthy at {BASE_URL}: {health.status_code}")
    except requests.RequestException as exc:
        pytest.skip(f"BioLinker service is not reachable at {BASE_URL}: {exc}")

    payload = {
        "user_address": "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",  # Hardhat Account #0
        "token_uri": "ipfs://QmTestHash1234",
    }

    response = requests.post(f"{BASE_URL}/nft/mint", json=payload, timeout=15)
    if response.status_code == 404:
        pytest.skip(f"/nft/mint endpoint is not available at {BASE_URL}")
    response.raise_for_status()
    data = response.json()

    print("API Response:", json.dumps(data, indent=2))

    assert data.get("success") is True
    assert isinstance(data.get("tx_hash"), str)
    assert data["tx_hash"]


if __name__ == "__main__":
    test_minting()
