// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title DeSciDAO - Decentralized Science Governance
 * @notice DSCI token holders can create proposals, vote, and execute governance decisions.
 * @dev Minimal on-chain governance: propose → vote (3 days) → execute
 */

interface IERC20 {
    function balanceOf(address account) external view returns (uint256);
    function totalSupply() external view returns (uint256);
}

contract DeSciDAO {
    // ── Types ──────────────────────────────────
    enum ProposalState { Pending, Active, Passed, Rejected, Executed }

    struct Proposal {
        uint256 id;
        address proposer;
        string title;
        string description;
        uint256 forVotes;
        uint256 againstVotes;
        uint256 startTime;
        uint256 endTime;
        bool executed;
        mapping(address => bool) hasVoted;
    }

    // ── State ──────────────────────────────────
    IERC20 public dsciToken;
    uint256 public proposalCount;
    uint256 public constant VOTING_PERIOD = 3 days;
    uint256 public constant MIN_PROPOSAL_TOKENS = 100 * 1e18; // 100 DSCI
    uint256 public constant QUORUM_PERCENTAGE = 10; // 10% of total supply

    mapping(uint256 => Proposal) public proposals;

    // ── Events ─────────────────────────────────
    event ProposalCreated(uint256 indexed id, address proposer, string title, uint256 endTime);
    event Voted(uint256 indexed proposalId, address voter, bool support, uint256 weight);
    event ProposalExecuted(uint256 indexed id);

    // ── Constructor ────────────────────────────
    constructor(address _dsciToken) {
        dsciToken = IERC20(_dsciToken);
    }

    // ── Modifiers ──────────────────────────────
    modifier onlyTokenHolder(uint256 minBalance) {
        require(dsciToken.balanceOf(msg.sender) >= minBalance, "Insufficient DSCI tokens");
        _;
    }

    // ── Create Proposal ────────────────────────
    function createProposal(
        string calldata _title,
        string calldata _description
    ) external onlyTokenHolder(MIN_PROPOSAL_TOKENS) returns (uint256) {
        proposalCount++;
        Proposal storage p = proposals[proposalCount];
        p.id = proposalCount;
        p.proposer = msg.sender;
        p.title = _title;
        p.description = _description;
        p.startTime = block.timestamp;
        p.endTime = block.timestamp + VOTING_PERIOD;

        emit ProposalCreated(proposalCount, msg.sender, _title, p.endTime);
        return proposalCount;
    }

    // ── Vote ───────────────────────────────────
    function vote(uint256 _proposalId, bool _support) external {
        Proposal storage p = proposals[_proposalId];
        require(p.id != 0, "Proposal does not exist");
        require(block.timestamp <= p.endTime, "Voting period ended");
        require(!p.hasVoted[msg.sender], "Already voted");

        uint256 weight = dsciToken.balanceOf(msg.sender);
        require(weight > 0, "No voting power");

        p.hasVoted[msg.sender] = true;

        if (_support) {
            p.forVotes += weight;
        } else {
            p.againstVotes += weight;
        }

        emit Voted(_proposalId, msg.sender, _support, weight);
    }

    // ── Execute ────────────────────────────────
    function executeProposal(uint256 _proposalId) external {
        Proposal storage p = proposals[_proposalId];
        require(p.id != 0, "Proposal does not exist");
        require(block.timestamp > p.endTime, "Voting period not ended");
        require(!p.executed, "Already executed");
        require(p.forVotes > p.againstVotes, "Proposal did not pass");

        uint256 quorum = (dsciToken.totalSupply() * QUORUM_PERCENTAGE) / 100;
        require(p.forVotes + p.againstVotes >= quorum, "Quorum not reached");

        p.executed = true;
        emit ProposalExecuted(_proposalId);
    }

    // ── View Functions ─────────────────────────
    function getProposalState(uint256 _proposalId) external view returns (ProposalState) {
        Proposal storage p = proposals[_proposalId];
        if (p.id == 0) revert("Proposal does not exist");
        if (p.executed) return ProposalState.Executed;
        if (block.timestamp <= p.endTime) return ProposalState.Active;
        if (p.forVotes > p.againstVotes) return ProposalState.Passed;
        return ProposalState.Rejected;
    }

    function getVotes(uint256 _proposalId) external view returns (uint256 forVotes, uint256 againstVotes) {
        Proposal storage p = proposals[_proposalId];
        return (p.forVotes, p.againstVotes);
    }

    function hasVoted(uint256 _proposalId, address _voter) external view returns (bool) {
        return proposals[_proposalId].hasVoted[_voter];
    }
}
