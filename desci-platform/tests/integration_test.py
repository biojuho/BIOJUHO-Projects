import requests
import json
import os
from dotenv import load_dotenv

# Env Setup
load_dotenv(dotenv_path="../biolinker/.env")

BASE_URL = "http://127.0.0.1:8000"
NFT_CONTRACT = os.getenv("NFT_CONTRACT_ADDRESS")

import sys
import io

# Fix Unicode Output
sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.detach(), encoding='utf-8')

def test_minting():
    print(f"🚀 Starting Integration Test: Minting on {NFT_CONTRACT}")
    
    # 1. Setup Data
    payload = {
        "user_address": "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266", # Hardhat Account #0
        "token_uri": "ipfs://QmTestHash1234"
    }
    
    # 2. Call API
    try:
        response = requests.post(f"{BASE_URL}/nft/mint", json=payload)
        response.raise_for_status()
        data = response.json()
        
        print("✅ API Response:", json.dumps(data, indent=2))
        
        if data.get("success"):
            print(f"🎉 Mint Successful! TX: {data['tx_hash']}")
            return True
        else:
            print("❌ Mint Failed (Logic Error)")
            return False
            
    except Exception as e:
        print(f"❌ API Request Failed: {e}")
        return False

if __name__ == "__main__":
    test_minting()
