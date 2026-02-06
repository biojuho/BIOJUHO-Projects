"""
BioLinker - Web3 Service
이더리움 블록체인 연동 및 토큰 보상
"""
import os
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

try:
    from web3 import Web3
    from eth_account import Account
    WEB3_AVAILABLE = True
except ImportError:
    WEB3_AVAILABLE = False


# DeSciToken ABI (핵심 함수만)
DESCI_TOKEN_ABI = [
    {
        "inputs": [{"name": "user", "type": "address"}],
        "name": "rewardPaperUpload",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{"name": "user", "type": "address"}],
        "name": "rewardPeerReview",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{"name": "user", "type": "address"}],
        "name": "rewardDataShare",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"name": "user", "type": "address"},
            {"name": "amount", "type": "uint256"},
            {"name": "reason", "type": "string"}
        ],
        "name": "distributeReward",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{"name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "totalSupply",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "getRewardAmounts",
        "outputs": [
            {"name": "paperUpload", "type": "uint256"},
            {"name": "peerReview", "type": "uint256"},
            {"name": "dataShare", "type": "uint256"},
            {"name": "researchParticipation", "type": "uint256"}
        ],
        "stateMutability": "view",
        "type": "function"
    }
]


class Web3Service:
    """Web3 블록체인 서비스"""
    
    def __init__(self):
        self.rpc_url = os.getenv("WEB3_RPC_URL", "https://sepolia.infura.io/v3/YOUR_KEY")
        self.contract_address = os.getenv("DSCI_CONTRACT_ADDRESS")
        self.private_key = os.getenv("DISTRIBUTOR_PRIVATE_KEY")
        
        self.w3 = None
        self.contract = None
        self.account = None
        
        if WEB3_AVAILABLE:
            self._initialize()
    
    def _initialize(self):
        """Web3 초기화"""
        try:
            self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))
            
            if self.contract_address:
                self.contract = self.w3.eth.contract(
                    address=Web3.to_checksum_address(self.contract_address),
                    abi=DESCI_TOKEN_ABI
                )
            
            if self.private_key:
                self.account = Account.from_key(self.private_key)
                
        except Exception as e:
            print(f"[Web3] Initialization error: {e}")
    
    @property
    def is_connected(self) -> bool:
        """블록체인 연결 상태"""
        if self.w3:
            try:
                return self.w3.is_connected()
            except:
                pass
        return False
    
    @property
    def is_configured(self) -> bool:
        """설정 완료 여부"""
        return bool(self.contract_address and self.private_key)
    
    async def get_balance(self, address: str) -> dict:
        """
        사용자 DSCI 토큰 잔액 조회
        
        Args:
            address: 지갑 주소
            
        Returns:
            {'balance': '100.0', 'balance_wei': '100000000...'}
        """
        if not WEB3_AVAILABLE:
            return self._mock_balance(address)
        
        if not self.contract:
            return self._mock_balance(address)
        
        try:
            checksum_addr = Web3.to_checksum_address(address)
            balance_wei = self.contract.functions.balanceOf(checksum_addr).call()
            balance = Web3.from_wei(balance_wei, 'ether')
            
            return {
                'address': address,
                'balance': str(balance),
                'balance_wei': str(balance_wei),
                'symbol': 'DSCI'
            }
        except Exception as e:
            print(f"[Web3] Balance error: {e}")
            return self._mock_balance(address)
    
    async def reward_paper_upload(self, user_address: str) -> dict:
        """논문 업로드 보상 지급 (100 DSCI)"""
        return await self._send_reward_tx("rewardPaperUpload", user_address)
    
    async def reward_peer_review(self, user_address: str) -> dict:
        """피어 리뷰 보상 지급 (50 DSCI)"""
        return await self._send_reward_tx("rewardPeerReview", user_address)
    
    async def reward_data_share(self, user_address: str) -> dict:
        """데이터 공유 보상 지급 (200 DSCI)"""
        return await self._send_reward_tx("rewardDataShare", user_address)
    
    async def distribute_custom_reward(
        self, 
        user_address: str, 
        amount: int, 
        reason: str
    ) -> dict:
        """커스텀 보상 지급"""
        if not self.is_configured or not self.contract:
            return self._mock_reward(user_address, amount, reason)
        
        try:
            checksum_addr = Web3.to_checksum_address(user_address)
            amount_wei = Web3.to_wei(amount, 'ether')
            
            tx = self.contract.functions.distributeReward(
                checksum_addr, amount_wei, reason
            ).build_transaction({
                'from': self.account.address,
                'nonce': self.w3.eth.get_transaction_count(self.account.address),
                'gas': 100000,
                'gasPrice': self.w3.eth.gas_price
            })
            
            signed_tx = self.w3.eth.account.sign_transaction(tx, self.private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            
            return {
                'success': True,
                'tx_hash': tx_hash.hex(),
                'user': user_address,
                'amount': amount,
                'reason': reason
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    async def _send_reward_tx(self, function_name: str, user_address: str) -> dict:
        """보상 트랜잭션 전송"""
        if not self.is_configured or not self.contract:
            return self._mock_reward(user_address, 100, function_name)
        
        try:
            checksum_addr = Web3.to_checksum_address(user_address)
            func = getattr(self.contract.functions, function_name)
            
            tx = func(checksum_addr).build_transaction({
                'from': self.account.address,
                'nonce': self.w3.eth.get_transaction_count(self.account.address),
                'gas': 100000,
                'gasPrice': self.w3.eth.gas_price
            })
            
            signed_tx = self.w3.eth.account.sign_transaction(tx, self.private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            
            return {
                'success': True,
                'tx_hash': tx_hash.hex(),
                'user': user_address,
                'reward_type': function_name
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    async def get_reward_amounts(self) -> dict:
        """보상 금액 조회"""
        if not self.contract:
            return {
                'paper_upload': '100',
                'peer_review': '50',
                'data_share': '200',
                'research_participation': '300',
                '_mock': True
            }
        
        try:
            amounts = self.contract.functions.getRewardAmounts().call()
            return {
                'paper_upload': str(Web3.from_wei(amounts[0], 'ether')),
                'peer_review': str(Web3.from_wei(amounts[1], 'ether')),
                'data_share': str(Web3.from_wei(amounts[2], 'ether')),
                'research_participation': str(Web3.from_wei(amounts[3], 'ether'))
            }
        except Exception as e:
            return {'error': str(e)}
    
    def _mock_balance(self, address: str) -> dict:
        """개발용 Mock 잔액"""
        import hashlib
        hash_val = int(hashlib.md5(address.encode()).hexdigest()[:8], 16)
        mock_balance = (hash_val % 1000) + 100
        
        return {
            'address': address,
            'balance': str(mock_balance),
            'balance_wei': str(mock_balance * 10**18),
            'symbol': 'DSCI',
            '_mock': True,
            '_note': 'Web3 설정 후 실제 잔액이 표시됩니다'
        }
    
    def _mock_reward(self, user: str, amount: int, reason: str) -> dict:
        """개발용 Mock 보상"""
        import uuid
        return {
            'success': True,
            'tx_hash': f"0x{uuid.uuid4().hex}",
            'user': user,
            'amount': amount,
            'reason': reason,
            '_mock': True,
            '_note': 'Web3 설정 후 실제 토큰이 지급됩니다'
        }


# Singleton
_web3_service: Optional[Web3Service] = None

def get_web3_service() -> Web3Service:
    global _web3_service
    if _web3_service is None:
        _web3_service = Web3Service()
    return _web3_service
