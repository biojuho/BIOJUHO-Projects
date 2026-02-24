// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/token/ERC20/extensions/ERC20Burnable.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

/**
 * @title DeSciToken (DSCI)
 * @dev DSCI-DecentBio 플랫폼 토큰
 * 
 * 보상 시나리오:
 * - 논문 업로드: +100 DSCI
 * - 피어 리뷰: +50 DSCI
 * - 데이터 공유: +200 DSCI
 * - 연구 참여: +300 DSCI
 */
contract DeSciToken is ERC20, ERC20Burnable, Ownable {
    
    // 보상 금액 (wei 단위)
    uint256 public constant REWARD_PAPER_UPLOAD = 100 * 10**18;
    uint256 public constant REWARD_PEER_REVIEW = 50 * 10**18;
    uint256 public constant REWARD_DATA_SHARE = 200 * 10**18;
    uint256 public constant REWARD_RESEARCH_PARTICIPATION = 300 * 10**18;
    
    // 최대 발행량 (1억 DSCI)
    uint256 public constant MAX_SUPPLY = 100_000_000 * 10**18;
    
    // 보상 지급자 (백엔드 서버)
    mapping(address => bool) public rewardDistributors;
    
    // 이벤트
    event RewardDistributed(address indexed user, uint256 amount, string reason);
    event DistributorAdded(address indexed distributor);
    event DistributorRemoved(address indexed distributor);
    
    constructor() ERC20("DeSci Token", "DSCI") Ownable(msg.sender) {
        // 초기 발행: 1000만 DSCI (팀 + 초기 유동성)
        _mint(msg.sender, 10_000_000 * 10**18);
    }
    
    // 보상 지급자 추가
    function addDistributor(address distributor) external onlyOwner {
        rewardDistributors[distributor] = true;
        emit DistributorAdded(distributor);
    }
    
    // 보상 지급자 제거
    function removeDistributor(address distributor) external onlyOwner {
        rewardDistributors[distributor] = false;
        emit DistributorRemoved(distributor);
    }
    
    // 보상 지급 (지급자만 호출 가능)
    modifier onlyDistributor() {
        require(
            rewardDistributors[msg.sender] || msg.sender == owner(),
            "Not authorized to distribute rewards"
        );
        _;
    }
    
    /**
     * @dev 사용자에게 보상 지급
     * @param user 보상 받을 주소
     * @param amount 보상 금액 (wei)
     * @param reason 보상 사유
     */
    function distributeReward(
        address user, 
        uint256 amount, 
        string calldata reason
    ) external onlyDistributor {
        require(totalSupply() + amount <= MAX_SUPPLY, "Max supply exceeded");
        _mint(user, amount);
        emit RewardDistributed(user, amount, reason);
    }
    
    /**
     * @dev 논문 업로드 보상
     */
    function rewardPaperUpload(address user) external onlyDistributor {
        require(totalSupply() + REWARD_PAPER_UPLOAD <= MAX_SUPPLY, "Max supply exceeded");
        _mint(user, REWARD_PAPER_UPLOAD);
        emit RewardDistributed(user, REWARD_PAPER_UPLOAD, "Paper Upload");
    }
    
    /**
     * @dev 피어 리뷰 보상
     */
    function rewardPeerReview(address user) external onlyDistributor {
        require(totalSupply() + REWARD_PEER_REVIEW <= MAX_SUPPLY, "Max supply exceeded");
        _mint(user, REWARD_PEER_REVIEW);
        emit RewardDistributed(user, REWARD_PEER_REVIEW, "Peer Review");
    }
    
    /**
     * @dev 데이터 공유 보상
     */
    function rewardDataShare(address user) external onlyDistributor {
        require(totalSupply() + REWARD_DATA_SHARE <= MAX_SUPPLY, "Max supply exceeded");
        _mint(user, REWARD_DATA_SHARE);
        emit RewardDistributed(user, REWARD_DATA_SHARE, "Data Share");
    }
    
    // 토큰 정보 조회
    function getRewardAmounts() external pure returns (
        uint256 paperUpload,
        uint256 peerReview,
        uint256 dataShare,
        uint256 researchParticipation
    ) {
        return (
            REWARD_PAPER_UPLOAD,
            REWARD_PEER_REVIEW,
            REWARD_DATA_SHARE,
            REWARD_RESEARCH_PARTICIPATION
        );
    }
}
