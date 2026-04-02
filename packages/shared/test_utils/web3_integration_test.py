import asyncio
import os
import sys
from pathlib import Path

# Add both projects to path
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT / "apps" / "AgriGuard" / "backend"))
sys.path.insert(0, str(WORKSPACE_ROOT / "apps" / "desci-platform" / "biolinker"))

# Set correct env variables for both to use localhost hardhat node
os.environ["WEB3_PROVIDER_URI"] = "http://127.0.0.1:8545"
os.environ["WEB3_RPC_URL"] = "http://127.0.0.1:8545"

# Independent Private Keys for Microservice Separation (Prevents RPC Nonce Collision)
TEST_KEY_AGRI = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80" # Account #0
TEST_KEY_DESCI = "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d" # Account #1

os.environ["PRIVATE_KEY"] = TEST_KEY_AGRI
os.environ["DISTRIBUTOR_PRIVATE_KEY"] = TEST_KEY_DESCI

# Mocks for addresses to bypass unit checks (Assuming already deployed)
os.environ["CONTRACT_ADDRESS"] = "0x5FbDB2315678afecb367f032d93F642f64180aa3"
os.environ["DSCI_CONTRACT_ADDRESS"] = "0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512"
os.environ["NFT_CONTRACT_ADDRESS"] = "0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0"
os.environ["MOCK_MODE"] = "false"

import importlib.util

def load_module_from_path(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

agri_sim_path = WORKSPACE_ROOT / "apps" / "AgriGuard" / "backend" / "services" / "chain_simulator.py"
chain_simulator = load_module_from_path("chain_simulator", str(agri_sim_path))
get_chain = chain_simulator.get_chain

desci_w3_path = WORKSPACE_ROOT / "apps" / "desci-platform" / "biolinker" / "services" / "web3_service.py"
web3_service = load_module_from_path("web3_service", str(desci_w3_path))
get_web3_service = web3_service.get_web3_service

async def run_agnostic_stress_test():
    chain = get_chain()
    w3_service = get_web3_service()
    
    # 50 requests total
    # If they share the SAME account and SAME Python process, the locks MIGHT save them if they use the same lock. 
    # But wait, one uses threading.Lock(), the other uses asyncio.Lock().

    async def fire_agri(i):
        try:
            tx = await asyncio.to_thread(chain.log_event, f"PROD-{i}", {"status": "ok"})
            if len(tx) > 60: # Fallback returns long data_hash mock tx, Web3 returns shorter one
                 return False, f"Fallback invoked for PROD-{i} due to internal web3 error"
            return True, tx
        except Exception as e:
            return False, str(e)

    async def fire_desci(i):
        try:
            res = await w3_service.reward_paper_upload("0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266")
            if res.get("success"):
                return True, res["tx_hash"]
            return False, res.get("error", "Unknown")
        except Exception as e:
            return False, str(e)

    print("\n[Firing 50 Concurrent Transactions using distinct cross-project locks...]")
    tasks = []
    for i in range(5):
        tasks.append(asyncio.create_task(fire_agri(i)))
        tasks.append(asyncio.create_task(fire_desci(i)))

    results = await asyncio.gather(*tasks)
    
    success_count = 0
    fail_count = 0
    errors = set()
    for success, msg in results:
        if success:
            success_count += 1
        else:
            fail_count += 1
            errors.add(msg)
            
    with open("web3_errors.txt", "w") as f:
        f.write(f"Success: {success_count}\nFailed: {fail_count}\n")
        for err in errors:
            f.write(f"- {err}\n")
            
    print(f"Success: {success_count}")
    print(f"Failed: {fail_count}")
    print(f"Errors encountered: {errors}")
    
    if fail_count > 0:
        print("\n=> [CONCLUSION] Architecture vulnerability detected: Nonce Collision across independent backend services sharing the same EOA.")
        sys.exit(1)
    else:
        print("\n=> All transactions succeeded! Locks were miraculously sufficient or sequential execution happened.")
        sys.exit(0)

if __name__ == "__main__":
    asyncio.run(run_agnostic_stress_test())
