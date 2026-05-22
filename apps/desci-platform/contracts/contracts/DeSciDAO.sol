// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title DeSciDAO
 * @notice DSCI holders can create proposals, vote with snapshotted power, and execute passed proposals.
 * @dev Votes are read from ERC20Votes checkpoints to prevent balance transfers from being reused across accounts.
 */
interface IDeSciVotesToken {
    function getVotes(address account) external view returns (uint256);
    function getPastVotes(address account, uint256 timepoint) external view returns (uint256);
    function getPastTotalSupply(uint256 timepoint) external view returns (uint256);
}

contract DeSciDAO {
    enum ProposalState {
        Pending,
        Active,
        Passed,
        Rejected,
        Queued,
        Executed
    }

    struct Proposal {
        uint256 id;
        address proposer;
        string title;
        string description;
        uint256 forVotes;
        uint256 againstVotes;
        uint256 startTime;
        uint256 endTime;
        uint256 snapshotBlock;
        bool executed;
        mapping(address => bool) hasVoted;
    }

    IDeSciVotesToken public dsciToken;
    uint256 public proposalCount;

    uint256 public constant VOTING_PERIOD = 3 days;
    uint256 public constant EXECUTION_DELAY = 2 days;
    uint256 public constant MIN_PROPOSAL_TOKENS = 100 * 1e18;
    uint256 public constant QUORUM_PERCENTAGE = 10;

    mapping(uint256 => Proposal) public proposals;

    event ProposalCreated(
        uint256 indexed id,
        address proposer,
        string title,
        uint256 endTime,
        uint256 snapshotBlock
    );
    event Voted(uint256 indexed proposalId, address voter, bool support, uint256 weight);
    event ProposalExecuted(uint256 indexed id);

    constructor(address tokenAddress) {
        require(tokenAddress != address(0), "DSCI token address required");
        dsciToken = IDeSciVotesToken(tokenAddress);
    }

    function createProposal(
        string calldata title,
        string calldata description
    ) external onlyTokenHolder(MIN_PROPOSAL_TOKENS) returns (uint256) {
        proposalCount++;

        Proposal storage proposal = proposals[proposalCount];
        proposal.id = proposalCount;
        proposal.proposer = msg.sender;
        proposal.title = title;
        proposal.description = description;
        proposal.startTime = block.timestamp;
        proposal.endTime = block.timestamp + VOTING_PERIOD;
        proposal.snapshotBlock = block.number;

        emit ProposalCreated(proposalCount, msg.sender, title, proposal.endTime, proposal.snapshotBlock);
        return proposalCount;
    }

    function vote(uint256 proposalId, bool support) external {
        Proposal storage proposal = proposals[proposalId];
        require(proposal.id != 0, "Proposal does not exist");
        require(block.number > proposal.snapshotBlock, "Voting snapshot not reached");
        require(block.timestamp <= proposal.endTime, "Voting period ended");
        require(!proposal.hasVoted[msg.sender], "Already voted");

        uint256 weight = dsciToken.getPastVotes(msg.sender, proposal.snapshotBlock);
        require(weight > 0, "No voting power");

        proposal.hasVoted[msg.sender] = true;

        if (support) {
            proposal.forVotes += weight;
        } else {
            proposal.againstVotes += weight;
        }

        emit Voted(proposalId, msg.sender, support, weight);
    }

    function executeProposal(uint256 proposalId) external {
        Proposal storage proposal = proposals[proposalId];
        require(proposal.id != 0, "Proposal does not exist");
        require(block.timestamp > proposal.endTime, "Voting period not ended");
        require(block.timestamp >= proposal.endTime + EXECUTION_DELAY, "Timelock: execution delay not met");
        require(!proposal.executed, "Already executed");
        require(proposal.forVotes > proposal.againstVotes, "Proposal did not pass");
        require(_quorumReached(proposal), "Quorum not reached");

        proposal.executed = true;
        emit ProposalExecuted(proposalId);
    }

    function getProposalState(uint256 proposalId) external view returns (ProposalState) {
        Proposal storage proposal = proposals[proposalId];
        if (proposal.id == 0) revert("Proposal does not exist");
        if (proposal.executed) return ProposalState.Executed;
        if (block.timestamp <= proposal.endTime) return ProposalState.Active;
        if (proposal.forVotes <= proposal.againstVotes || !_quorumReached(proposal)) {
            return ProposalState.Rejected;
        }
        if (block.timestamp < proposal.endTime + EXECUTION_DELAY) return ProposalState.Queued;
        return ProposalState.Passed;
    }

    function getProposalQuorum(uint256 proposalId) external view returns (uint256) {
        Proposal storage proposal = proposals[proposalId];
        require(proposal.id != 0, "Proposal does not exist");
        return _getQuorum(proposal.snapshotBlock);
    }

    function getVotes(uint256 proposalId) external view returns (uint256 forVotes, uint256 againstVotes) {
        Proposal storage proposal = proposals[proposalId];
        return (proposal.forVotes, proposal.againstVotes);
    }

    function hasVoted(uint256 proposalId, address voter) external view returns (bool) {
        return proposals[proposalId].hasVoted[voter];
    }

    function _getQuorum(uint256 snapshotBlock) internal view returns (uint256) {
        return (dsciToken.getPastTotalSupply(snapshotBlock) * QUORUM_PERCENTAGE) / 100;
    }

    function _quorumReached(Proposal storage proposal) internal view returns (bool) {
        return proposal.forVotes + proposal.againstVotes >= _getQuorum(proposal.snapshotBlock);
    }

    modifier onlyTokenHolder(uint256 minBalance) {
        require(dsciToken.getVotes(msg.sender) >= minBalance, "Insufficient voting power");
        _;
    }
}
