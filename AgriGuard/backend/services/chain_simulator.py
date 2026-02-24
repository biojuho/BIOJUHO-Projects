import os
import hashlib
from datetime import datetime
from web3 import Web3

# local dev private key (Hardhat account #0)
LOCAL_PRIVATE_KEY = os.getenv("PRIVATE_KEY", "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80")

class ChainSimulator:
    """
    Connects to Hardhat local node for Web3 transactions.
    If Web3 is not available, falls back to memory simulator (for resilience).
    """
    def __init__(self):
        self.chain = []
        provider_url = os.getenv("WEB3_PROVIDER_URI", "http://127.0.0.1:8545")
        self.w3 = Web3(Web3.HTTPProvider(provider_url))
        
        # Deployer address from previous result
        # Assuming typical hardhat first address
        self.contract_address = os.getenv("CONTRACT_ADDRESS", "0x5FbDB2315678afecb367f032d93F642f64180aa3")
        self.account = self.w3.eth.account.from_key(LOCAL_PRIVATE_KEY)

        self.contract_abi = [
            {
                "inputs": [
                    { "internalType": "string", "name": "_productId", "type": "string" },
                    { "internalType": "string", "name": "_dataHash", "type": "string" }
                ],
                "name": "logEvent",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function"
            },
            {
                "inputs": [
                    { "internalType": "string", "name": "_productId", "type": "string" }
                ],
                "name": "getProduct",
                "outputs": [
                    {
                        "components": [
                            { "internalType": "string", "name": "productId", "type": "string" },
                            { "internalType": "address", "name": "owner", "type": "address" },
                            { "internalType": "string", "name": "dataHash", "type": "string" },
                            { "internalType": "uint256", "name": "timestamp", "type": "uint256" }
                        ],
                        "internalType": "struct AgriGuard.Product",
                        "name": "",
                        "type": "tuple"
                    }
                ],
                "stateMutability": "view",
                "type": "function"
            },
            {
                "anonymous": False,
                "inputs": [
                    { "indexed": False, "internalType": "string", "name": "productId", "type": "string" },
                    { "indexed": False, "internalType": "address", "name": "owner", "type": "address" },
                    { "indexed": False, "internalType": "string", "name": "dataHash", "type": "string" },
                    { "indexed": False, "internalType": "uint256", "name": "timestamp", "type": "uint256" }
                ],
                "name": "ProductVerified",
                "type": "event"
            }
        ]

        self.is_web3_active = self.w3.is_connected()
        if self.is_web3_active:
            # required for POA chains if used, though local node usually doesn't need it
            self.contract = self.w3.eth.contract(address=self.contract_address, abi=self.contract_abi)

    def log_event(self, product_id: str, event_data: dict) -> str:
        """
        Writes a transaction to the blockchain.
        Returns transaction hash.
        """
        payload = f"{product_id}-{event_data}-{datetime.now().isoformat()}"
        data_hash = hashlib.sha256(payload.encode()).hexdigest()

        if self.is_web3_active:
            try:
                nonce = self.w3.eth.get_transaction_count(self.account.address)
                tx = self.contract.functions.logEvent(product_id, data_hash).build_transaction({
                    'chainId': 31337,
                    'gas': 300000,
                    'gasPrice': self.w3.eth.gas_price,
                    'nonce': nonce,
                })
                signed_tx = self.w3.eth.account.sign_transaction(tx, private_key=LOCAL_PRIVATE_KEY)
                tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction) # Use raw_transaction instead of rawTransaction for Web3 v6
                
                # We also append to local memory for easy retrieve in mock API endpoints if not fully converted
                self.chain.append({
                    "tx_hash": tx_hash.hex(),
                    "product_id": product_id,
                    "data": event_data,
                    "timestamp": datetime.now().isoformat(),
                    "block": "web3"
                })
                return tx_hash.hex()
            except Exception as e:
                print(f"Web3 log_event error: {e}")

        # Simulator fallback
        tx_hash = data_hash
        self.chain.append({
            "tx_hash": tx_hash,
            "product_id": product_id,
            "data": event_data,
            "timestamp": datetime.now().isoformat(),
            "block": len(self.chain) + 1
        })
        return f"0x{tx_hash}"

    def verify_product(self, product_id: str) -> bool:
        if self.is_web3_active:
            try:
                prod = self.contract.functions.getProduct(product_id).call()
                # prod = (productId, owner, dataHash, timestamp)
                # If timestamp > 0, we consider it verified
                return prod[3] > 0
            except Exception as e:
                print(f"Web3 getProduct error: {e}")
                
        history = self.get_product_history(product_id)
        return len(history) > 0

    def get_product_history(self, product_id: str) -> list:
        # For MVP we keep mixed Web3/Memory, normally we would fetch events from Web3 
        # using self.contract.events.ProductVerified.create_filter(...)
        return [block for block in self.chain if block.get("product_id") == product_id]

# Singleton
_chain = ChainSimulator()

def get_chain():
    return _chain
