const { expect } = require("chai");
const { ethers } = require("hardhat");
const { time } = require("@nomicfoundation/hardhat-network-helpers");
const { anyValue } = require("@nomicfoundation/hardhat-chai-matchers/withArgs");

describe("DeSciDAO", function () {
    let DeSciToken, DeSciDAO;
    let token, dao;
    let owner, voter1, voter2, voter3, poorUser;

    const VOTING_PERIOD = 3 * 24 * 60 * 60; // 3 days in seconds
    const EXECUTION_DELAY = 2 * 24 * 60 * 60; // 2 days in seconds
    const MIN_PROPOSAL_TOKENS = ethers.parseEther("100");

    beforeEach(async function () {
        [owner, voter1, voter2, voter3, poorUser] = await ethers.getSigners();

        // Deploy DeSciToken
        DeSciToken = await ethers.getContractFactory("DeSciToken");
        token = await DeSciToken.deploy();
        await token.waitForDeployment();

        // Deploy DeSciDAO with token address
        DeSciDAO = await ethers.getContractFactory("DeSciDAO");
        dao = await DeSciDAO.deploy(await token.getAddress());
        await dao.waitForDeployment();

        // Distribute tokens to voters for governance
        // Owner has 10M DSCI from initial mint
        await token.transfer(voter1.address, ethers.parseEther("200000")); // 200K DSCI
        await token.transfer(voter2.address, ethers.parseEther("150000")); // 150K DSCI
        await token.transfer(voter3.address, ethers.parseEther("100000")); // 100K DSCI
        // poorUser gets nothing
    });

    // ── Deployment ──────────────────────────────

    describe("Deployment", function () {
        it("Should set the correct DSCI token address", async function () {
            expect(await dao.dsciToken()).to.equal(await token.getAddress());
        });

        it("Should initialize with zero proposals", async function () {
            expect(await dao.proposalCount()).to.equal(0);
        });

        it("Should have correct constants", async function () {
            expect(await dao.VOTING_PERIOD()).to.equal(VOTING_PERIOD);
            expect(await dao.EXECUTION_DELAY()).to.equal(EXECUTION_DELAY);
            expect(await dao.MIN_PROPOSAL_TOKENS()).to.equal(MIN_PROPOSAL_TOKENS);
            expect(await dao.QUORUM_PERCENTAGE()).to.equal(10);
        });
    });

    // ── Proposal Creation ───────────────────────

    describe("Proposal Creation", function () {
        it("Should allow token holder with sufficient tokens to create proposal", async function () {
            await expect(
                dao.connect(voter1).createProposal("Fund Research", "Allocate 10K DSCI to research")
            )
                .to.emit(dao, "ProposalCreated")
                .withArgs(1, voter1.address, "Fund Research", anyValue);

            expect(await dao.proposalCount()).to.equal(1);
        });

        it("Should not allow user with insufficient tokens to create proposal", async function () {
            await expect(
                dao.connect(poorUser).createProposal("Bad Proposal", "Should fail")
            ).to.be.revertedWith("Insufficient DSCI tokens");
        });

        it("Should not allow user with zero tokens to create proposal", async function () {
            await expect(
                dao.connect(poorUser).createProposal("No Tokens", "Should fail")
            ).to.be.revertedWith("Insufficient DSCI tokens");
        });

        it("Should set correct proposal fields", async function () {
            await dao.connect(voter1).createProposal("Test Title", "Test Description");

            const proposal = await dao.proposals(1);
            expect(proposal.id).to.equal(1);
            expect(proposal.proposer).to.equal(voter1.address);
            expect(proposal.title).to.equal("Test Title");
            expect(proposal.description).to.equal("Test Description");
            expect(proposal.forVotes).to.equal(0);
            expect(proposal.againstVotes).to.equal(0);
            expect(proposal.executed).to.equal(false);
        });

        it("Should set correct voting period end time", async function () {
            const tx = await dao.connect(voter1).createProposal("Timed", "Check time");
            const block = await ethers.provider.getBlock(tx.blockNumber);

            const proposal = await dao.proposals(1);
            expect(proposal.endTime).to.equal(BigInt(block.timestamp) + BigInt(VOTING_PERIOD));
        });

        it("Should increment proposal count for multiple proposals", async function () {
            await dao.connect(voter1).createProposal("First", "Desc 1");
            await dao.connect(voter2).createProposal("Second", "Desc 2");

            expect(await dao.proposalCount()).to.equal(2);
        });
    });

    // ── Voting ──────────────────────────────────

    describe("Voting", function () {
        beforeEach(async function () {
            await dao.connect(voter1).createProposal("Vote Test", "Testing votes");
        });

        it("Should allow token holder to vote for", async function () {
            const weight = await token.balanceOf(voter1.address);

            await expect(dao.connect(voter1).vote(1, true))
                .to.emit(dao, "Voted")
                .withArgs(1, voter1.address, true, weight);

            const [forVotes] = await dao.getVotes(1);
            expect(forVotes).to.equal(weight);
        });

        it("Should allow token holder to vote against", async function () {
            const weight = await token.balanceOf(voter2.address);

            await expect(dao.connect(voter2).vote(1, false))
                .to.emit(dao, "Voted")
                .withArgs(1, voter2.address, false, weight);

            const [, againstVotes] = await dao.getVotes(1);
            expect(againstVotes).to.equal(weight);
        });

        it("Should not allow double voting", async function () {
            await dao.connect(voter1).vote(1, true);
            await expect(
                dao.connect(voter1).vote(1, false)
            ).to.be.revertedWith("Already voted");
        });

        it("Should not allow voting on non-existent proposal", async function () {
            await expect(
                dao.connect(voter1).vote(999, true)
            ).to.be.revertedWith("Proposal does not exist");
        });

        it("Should not allow voting after period ends", async function () {
            await time.increase(VOTING_PERIOD + 1);

            await expect(
                dao.connect(voter1).vote(1, true)
            ).to.be.revertedWith("Voting period ended");
        });

        it("Should not allow voting with zero tokens", async function () {
            await expect(
                dao.connect(poorUser).vote(1, true)
            ).to.be.revertedWith("No voting power");
        });

        it("Should track hasVoted correctly", async function () {
            expect(await dao.hasVoted(1, voter1.address)).to.equal(false);
            await dao.connect(voter1).vote(1, true);
            expect(await dao.hasVoted(1, voter1.address)).to.equal(true);
        });

        it("Should use token balance as voting weight", async function () {
            await dao.connect(voter1).vote(1, true); // 200K
            await dao.connect(voter2).vote(1, true); // 150K

            const [forVotes] = await dao.getVotes(1);
            const expected =
                (await token.balanceOf(voter1.address)) +
                (await token.balanceOf(voter2.address));
            expect(forVotes).to.equal(expected);
        });
    });

    // ── Execution ───────────────────────────────

    describe("Execution", function () {
        beforeEach(async function () {
            await dao.connect(voter1).createProposal("Execute Test", "Testing execution");
        });

        it("Should execute a passed proposal after voting period + timelock", async function () {
            // Vote with large token holders (enough for quorum)
            await dao.connect(owner).vote(1, true); // Owner has most tokens
            await dao.connect(voter1).vote(1, true);

            // Advance past voting period + execution delay
            await time.increase(VOTING_PERIOD + EXECUTION_DELAY + 1);

            await expect(dao.executeProposal(1))
                .to.emit(dao, "ProposalExecuted")
                .withArgs(1);

            const proposal = await dao.proposals(1);
            expect(proposal.executed).to.equal(true);
        });

        it("Should not execute during voting period", async function () {
            await dao.connect(owner).vote(1, true);

            await expect(
                dao.executeProposal(1)
            ).to.be.revertedWith("Timelock: execution delay not met");
        });

        it("Should not execute during timelock delay (after voting, before delay)", async function () {
            await dao.connect(owner).vote(1, true);
            await dao.connect(voter1).vote(1, true);

            // Advance past voting period but not past execution delay
            await time.increase(VOTING_PERIOD + 1);

            await expect(
                dao.executeProposal(1)
            ).to.be.revertedWith("Timelock: execution delay not met");
        });

        it("Should not execute a rejected proposal", async function () {
            // Vote against
            await dao.connect(owner).vote(1, false);
            await dao.connect(voter1).vote(1, false);

            await time.increase(VOTING_PERIOD + EXECUTION_DELAY + 1);

            await expect(
                dao.executeProposal(1)
            ).to.be.revertedWith("Proposal did not pass");
        });

        it("Should not execute twice", async function () {
            await dao.connect(owner).vote(1, true);
            await dao.connect(voter1).vote(1, true);

            await time.increase(VOTING_PERIOD + EXECUTION_DELAY + 1);
            await dao.executeProposal(1);

            await expect(
                dao.executeProposal(1)
            ).to.be.revertedWith("Already executed");
        });

        it("Should not execute non-existent proposal", async function () {
            await time.increase(VOTING_PERIOD + EXECUTION_DELAY + 1);

            await expect(
                dao.executeProposal(999)
            ).to.be.revertedWith("Proposal does not exist");
        });
    });

    // ── Quorum ──────────────────────────────────

    describe("Quorum Requirements", function () {
        beforeEach(async function () {
            await dao.connect(voter1).createProposal("Quorum Test", "Testing quorum");
        });

        it("Should reject execution if quorum not reached", async function () {
            // Only voter3 votes (100K = 1% of 10M supply, below 10% quorum)
            await dao.connect(voter3).vote(1, true);

            await time.increase(VOTING_PERIOD + EXECUTION_DELAY + 1);

            await expect(
                dao.executeProposal(1)
            ).to.be.revertedWith("Quorum not reached");
        });

        it("Should allow execution when quorum is reached", async function () {
            // Owner votes with ~9.55M tokens (95.5% of supply — well above 10% quorum)
            await dao.connect(owner).vote(1, true);

            await time.increase(VOTING_PERIOD + EXECUTION_DELAY + 1);
            await expect(dao.executeProposal(1)).to.not.be.reverted;
        });

        it("Should count both for and against votes toward quorum", async function () {
            // Owner votes against, voter1 + voter2 vote for
            // Combined is well above 10% quorum
            await dao.connect(owner).vote(1, false);
            await dao.connect(voter1).vote(1, true);
            await dao.connect(voter2).vote(1, true);

            await time.increase(VOTING_PERIOD + EXECUTION_DELAY + 1);

            // Should fail because against > for (owner has ~9.55M vs voter1+voter2 = 350K)
            await expect(
                dao.executeProposal(1)
            ).to.be.revertedWith("Proposal did not pass");
        });
    });

    // ── Proposal State ──────────────────────────

    describe("Proposal State", function () {
        beforeEach(async function () {
            await dao.connect(voter1).createProposal("State Test", "Testing state machine");
        });

        it("Should return Active during voting period", async function () {
            expect(await dao.getProposalState(1)).to.equal(1); // Active
        });

        it("Should return Queued after voting period with passing vote but before delay", async function () {
            await dao.connect(owner).vote(1, true);
            await time.increase(VOTING_PERIOD + 1);

            expect(await dao.getProposalState(1)).to.equal(4); // Queued
        });

        it("Should return Passed after voting period + execution delay", async function () {
            await dao.connect(owner).vote(1, true);
            await time.increase(VOTING_PERIOD + EXECUTION_DELAY + 1);

            expect(await dao.getProposalState(1)).to.equal(2); // Passed
        });

        it("Should return Rejected if against votes win", async function () {
            await dao.connect(owner).vote(1, false);
            await time.increase(VOTING_PERIOD + 1);

            expect(await dao.getProposalState(1)).to.equal(3); // Rejected
        });

        it("Should return Rejected if no votes cast (0 for, 0 against)", async function () {
            await time.increase(VOTING_PERIOD + 1);

            expect(await dao.getProposalState(1)).to.equal(3); // Rejected (0 <= 0)
        });

        it("Should return Executed after execution", async function () {
            await dao.connect(owner).vote(1, true);
            await time.increase(VOTING_PERIOD + EXECUTION_DELAY + 1);
            await dao.executeProposal(1);

            expect(await dao.getProposalState(1)).to.equal(5); // Executed
        });

        it("Should revert for non-existent proposal", async function () {
            await expect(dao.getProposalState(999)).to.be.revertedWith(
                "Proposal does not exist"
            );
        });
    });

    // ── View Functions ──────────────────────────

    describe("View Functions", function () {
        beforeEach(async function () {
            await dao.connect(voter1).createProposal("View Test", "Testing views");
        });

        it("Should return correct vote counts via getVotes", async function () {
            await dao.connect(voter1).vote(1, true);
            await dao.connect(voter2).vote(1, false);

            const [forVotes, againstVotes] = await dao.getVotes(1);
            expect(forVotes).to.equal(await token.balanceOf(voter1.address));
            expect(againstVotes).to.equal(await token.balanceOf(voter2.address));
        });
    });
});
