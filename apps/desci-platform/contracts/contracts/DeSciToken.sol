// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/token/ERC20/extensions/ERC20Burnable.sol";
import "@openzeppelin/contracts/token/ERC20/extensions/ERC20Permit.sol";
import "@openzeppelin/contracts/token/ERC20/extensions/ERC20Votes.sol";
import "@openzeppelin/contracts/utils/Nonces.sol";

/**
 * @title DeSciToken
 * @notice Reward and governance token for the DeSci platform.
 * @dev ERC20Votes is enabled so governance can use historical vote snapshots.
 * Holders must delegate to themselves before their balance becomes voting power.
 */
contract DeSciToken is ERC20, ERC20Burnable, Ownable, ERC20Permit, ERC20Votes {
    uint256 public constant INITIAL_SUPPLY = 10_000_000 * 10**18;
    uint256 public constant MAX_SUPPLY = 100_000_000 * 10**18;

    uint256 public constant REWARD_PAPER_UPLOAD = 100 * 10**18;
    uint256 public constant REWARD_PEER_REVIEW = 50 * 10**18;
    uint256 public constant REWARD_DATA_SHARE = 200 * 10**18;
    uint256 public constant REWARD_RESEARCH_PARTICIPATION = 300 * 10**18;

    mapping(address => bool) public rewardDistributors;

    event RewardDistributed(address indexed user, uint256 amount, string reason);
    event DistributorAdded(address indexed distributor);
    event DistributorRemoved(address indexed distributor);

    constructor()
        ERC20("DeSci Token", "DSCI")
        Ownable(msg.sender)
        ERC20Permit("DeSci Token")
    {
        _mint(msg.sender, INITIAL_SUPPLY);
    }

    function addDistributor(address distributor) external onlyOwner {
        require(distributor != address(0), "Distributor address required");
        rewardDistributors[distributor] = true;
        emit DistributorAdded(distributor);
    }

    function removeDistributor(address distributor) external onlyOwner {
        require(distributor != address(0), "Distributor address required");
        rewardDistributors[distributor] = false;
        emit DistributorRemoved(distributor);
    }

    function distributeReward(
        address user,
        uint256 amount,
        string calldata reason
    ) external onlyDistributor {
        _distributeReward(user, amount, reason);
    }

    function rewardPaperUpload(address user) external onlyDistributor {
        _distributeReward(user, REWARD_PAPER_UPLOAD, "Paper Upload");
    }

    function rewardPeerReview(address user) external onlyDistributor {
        _distributeReward(user, REWARD_PEER_REVIEW, "Peer Review");
    }

    function rewardDataShare(address user) external onlyDistributor {
        _distributeReward(user, REWARD_DATA_SHARE, "Data Share");
    }

    function getRewardAmounts()
        external
        pure
        returns (
            uint256 paperUpload,
            uint256 peerReview,
            uint256 dataShare,
            uint256 researchParticipation
        )
    {
        return (
            REWARD_PAPER_UPLOAD,
            REWARD_PEER_REVIEW,
            REWARD_DATA_SHARE,
            REWARD_RESEARCH_PARTICIPATION
        );
    }

    function _distributeReward(address user, uint256 amount, string memory reason) internal {
        require(user != address(0), "Reward recipient required");
        require(totalSupply() + amount <= MAX_SUPPLY, "Max supply exceeded");

        _mint(user, amount);
        emit RewardDistributed(user, amount, reason);
    }

    function _update(address from, address to, uint256 value) internal override(ERC20, ERC20Votes) {
        super._update(from, to, value);
    }

    function nonces(address owner) public view override(ERC20Permit, Nonces) returns (uint256) {
        return super.nonces(owner);
    }

    modifier onlyDistributor() {
        require(
            rewardDistributors[msg.sender] || msg.sender == owner(),
            "Not authorized to distribute rewards"
        );
        _;
    }
}
