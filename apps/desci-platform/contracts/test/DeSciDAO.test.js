import { anyValue } from "@nomicfoundation/hardhat-ethers-chai-matchers/withArgs";
import { expect } from "chai";
import { network } from "hardhat";

const { ethers, networkHelpers } = await network.create();

describe("DeSciDAO", function () {
    let DeSciToken;
    let DeSciDAO;
    let token;
    let dao;
    let owner;
    let voter1;
    let voter2;
    let voter3;
    let poorUser;

    const VOTING_PERIOD = 3 * 24 * 60 * 60;
    const EXECUTION_DELAY = 2 * 24 * 60 * 60;
    const MIN_PROPOSAL_TOKENS = ethers.parseEther("100");

    async function selfDelegate(signers) {
        for (const signer of signers) {
            await token.connect(signer).delegate(signer.address);
        }
    }

    beforeEach(async function () {
        [owner, voter1, voter2, voter3, poorUser] = await ethers.getSigners();

        DeSciToken = await ethers.getContractFactory("DeSciToken");
        token = await DeSciToken.deploy();
        await token.waitForDeployment();

        await token.transfer(voter1.address, ethers.parseEther("200000"));
        await token.transfer(voter2.address, ethers.parseEther("150000"));
        await token.transfer(voter3.address, ethers.parseEther("100000"));

        await selfDelegate([owner, voter1, voter2, voter3, poorUser]);

        DeSciDAO = await ethers.getContractFactory("DeSciDAO");
        dao = await DeSciDAO.deploy(await token.getAddress());
        await dao.waitForDeployment();
    });

    describe("Deployment", function () {
        it("Should set the correct DSCI token address", async function () {
            expect(await dao.dsciToken()).to.equal(await token.getAddress());
        });

        it("Should initialize with zero proposals", async function () {
            expect(await dao.proposalCount()).to.equal(0);
        });

        it("Should reject a zero token address", async function () {
            await expect(DeSciDAO.deploy(ethers.ZeroAddress)).to.be.revertedWith(
                "DSCI token address required"
            );
        });

        it("Should have correct constants", async function () {
            expect(await dao.VOTING_PERIOD()).to.equal(VOTING_PERIOD);
            expect(await dao.EXECUTION_DELAY()).to.equal(EXECUTION_DELAY);
            expect(await dao.MIN_PROPOSAL_TOKENS()).to.equal(MIN_PROPOSAL_TOKENS);
            expect(await dao.QUORUM_PERCENTAGE()).to.equal(10);
        });
    });

    describe("Proposal Creation", function () {
        it("Should allow token holder with sufficient voting power to create proposal", async function () {
            await expect(
                dao.connect(voter1).createProposal("Fund Research", "Allocate 10K DSCI to research")
            )
                .to.emit(dao, "ProposalCreated")
                .withArgs(1, voter1.address, "Fund Research", anyValue, anyValue);

            expect(await dao.proposalCount()).to.equal(1);
        });

        it("Should not allow user with insufficient tokens to create proposal", async function () {
            await expect(
                dao.connect(poorUser).createProposal("Bad Proposal", "Should fail")
            ).to.be.revertedWith("Insufficient voting power");
        });

        it("Should set correct proposal fields", async function () {
            const tx = await dao.connect(voter1).createProposal("Test Title", "Test Description");
            const receipt = await tx.wait();
            const proposal = await dao.proposals(1);

            expect(proposal.id).to.equal(1);
            expect(proposal.proposer).to.equal(voter1.address);
            expect(proposal.title).to.equal("Test Title");
            expect(proposal.description).to.equal("Test Description");
            expect(proposal.forVotes).to.equal(0);
            expect(proposal.againstVotes).to.equal(0);
            expect(proposal.executed).to.equal(false);
            expect(proposal.snapshotBlock).to.equal(receipt.blockNumber);
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

    describe("Voting", function () {
        beforeEach(async function () {
            await dao.connect(voter1).createProposal("Vote Test", "Testing votes");
            await networkHelpers.mine();
        });

        it("Should allow token holder to vote for", async function () {
            const weight = await token.getPastVotes(voter1.address, (await dao.proposals(1)).snapshotBlock);

            await expect(dao.connect(voter1).vote(1, true))
                .to.emit(dao, "Voted")
                .withArgs(1, voter1.address, true, weight);

            const [forVotes] = await dao.getVotes(1);
            expect(forVotes).to.equal(weight);
        });

        it("Should allow token holder to vote against", async function () {
            const weight = await token.getPastVotes(voter2.address, (await dao.proposals(1)).snapshotBlock);

            await expect(dao.connect(voter2).vote(1, false))
                .to.emit(dao, "Voted")
                .withArgs(1, voter2.address, false, weight);

            const [, againstVotes] = await dao.getVotes(1);
            expect(againstVotes).to.equal(weight);
        });

        it("Should not allow double voting", async function () {
            await dao.connect(voter1).vote(1, true);
            await expect(dao.connect(voter1).vote(1, false)).to.be.revertedWith("Already voted");
        });

        it("Should not allow voting on non-existent proposal", async function () {
            await expect(dao.connect(voter1).vote(999, true)).to.be.revertedWith(
                "Proposal does not exist"
            );
        });

        it("Should not allow voting after period ends", async function () {
            await networkHelpers.time.increase(VOTING_PERIOD + 1);

            await expect(dao.connect(voter1).vote(1, true)).to.be.revertedWith(
                "Voting period ended"
            );
        });

        it("Should not allow voting with zero snapshot voting power", async function () {
            await token.transfer(poorUser.address, ethers.parseEther("1000"));
            await token.connect(poorUser).delegate(poorUser.address);

            await expect(dao.connect(poorUser).vote(1, true)).to.be.revertedWith("No voting power");
        });

        it("Should track hasVoted correctly", async function () {
            expect(await dao.hasVoted(1, voter1.address)).to.equal(false);
            await dao.connect(voter1).vote(1, true);
            expect(await dao.hasVoted(1, voter1.address)).to.equal(true);
        });

        it("Should use snapshotted voting weight", async function () {
            const proposal = await dao.proposals(1);
            const expected =
                (await token.getPastVotes(voter1.address, proposal.snapshotBlock)) +
                (await token.getPastVotes(voter2.address, proposal.snapshotBlock));

            await dao.connect(voter1).vote(1, true);
            await token.connect(voter1).transfer(poorUser.address, ethers.parseEther("200000"));
            await token.connect(poorUser).delegate(poorUser.address);
            await dao.connect(voter2).vote(1, true);

            const [forVotes] = await dao.getVotes(1);
            expect(forVotes).to.equal(expected);
        });

        it("Should prevent reusing transferred tokens across a second voter", async function () {
            await dao.connect(voter1).vote(1, true);
            await token.connect(voter1).transfer(poorUser.address, ethers.parseEther("200000"));
            await token.connect(poorUser).delegate(poorUser.address);

            await expect(dao.connect(poorUser).vote(1, true)).to.be.revertedWith("No voting power");
        });
    });

    describe("Execution", function () {
        beforeEach(async function () {
            await dao.connect(voter1).createProposal("Execute Test", "Testing execution");
            await networkHelpers.mine();
        });

        it("Should execute a passed proposal after voting period and timelock", async function () {
            await dao.connect(owner).vote(1, true);
            await dao.connect(voter1).vote(1, true);

            await networkHelpers.time.increase(VOTING_PERIOD + EXECUTION_DELAY + 1);

            await expect(dao.executeProposal(1)).to.emit(dao, "ProposalExecuted").withArgs(1);

            const proposal = await dao.proposals(1);
            expect(proposal.executed).to.equal(true);
        });

        it("Should not execute during voting period", async function () {
            await dao.connect(owner).vote(1, true);

            await expect(dao.executeProposal(1)).to.be.revertedWith("Voting period not ended");
        });

        it("Should not execute during timelock delay", async function () {
            await dao.connect(owner).vote(1, true);
            await dao.connect(voter1).vote(1, true);
            await networkHelpers.time.increase(VOTING_PERIOD + 1);

            await expect(dao.executeProposal(1)).to.be.revertedWith(
                "Timelock: execution delay not met"
            );
        });

        it("Should not execute a rejected proposal", async function () {
            await dao.connect(owner).vote(1, false);
            await dao.connect(voter1).vote(1, false);
            await networkHelpers.time.increase(VOTING_PERIOD + EXECUTION_DELAY + 1);

            await expect(dao.executeProposal(1)).to.be.revertedWith("Proposal did not pass");
        });

        it("Should not execute twice", async function () {
            await dao.connect(owner).vote(1, true);
            await dao.connect(voter1).vote(1, true);
            await networkHelpers.time.increase(VOTING_PERIOD + EXECUTION_DELAY + 1);
            await dao.executeProposal(1);

            await expect(dao.executeProposal(1)).to.be.revertedWith("Already executed");
        });

        it("Should not execute non-existent proposal", async function () {
            await expect(dao.executeProposal(999)).to.be.revertedWith("Proposal does not exist");
        });
    });

    describe("Quorum Requirements", function () {
        beforeEach(async function () {
            await dao.connect(voter1).createProposal("Quorum Test", "Testing quorum");
            await networkHelpers.mine();
        });

        it("Should reject execution if quorum not reached", async function () {
            await dao.connect(voter3).vote(1, true);
            await networkHelpers.time.increase(VOTING_PERIOD + EXECUTION_DELAY + 1);

            await expect(dao.executeProposal(1)).to.be.revertedWith("Quorum not reached");
        });

        it("Should allow execution when quorum is reached", async function () {
            await dao.connect(owner).vote(1, true);
            await networkHelpers.time.increase(VOTING_PERIOD + EXECUTION_DELAY + 1);

            await expect(dao.executeProposal(1)).to.not.revert(ethers);
        });

        it("Should count both for and against votes toward quorum", async function () {
            await dao.connect(owner).vote(1, false);
            await dao.connect(voter1).vote(1, true);
            await dao.connect(voter2).vote(1, true);
            await networkHelpers.time.increase(VOTING_PERIOD + EXECUTION_DELAY + 1);

            await expect(dao.executeProposal(1)).to.be.revertedWith("Proposal did not pass");
        });
    });

    describe("Proposal State", function () {
        beforeEach(async function () {
            await dao.connect(voter1).createProposal("State Test", "Testing state machine");
            await networkHelpers.mine();
        });

        it("Should return Active during voting period", async function () {
            expect(await dao.getProposalState(1)).to.equal(1);
        });

        it("Should return Queued after voting period with passing vote but before delay", async function () {
            await dao.connect(owner).vote(1, true);
            await networkHelpers.time.increase(VOTING_PERIOD + 1);

            expect(await dao.getProposalState(1)).to.equal(4);
        });

        it("Should return Passed after voting period and execution delay", async function () {
            await dao.connect(owner).vote(1, true);
            await networkHelpers.time.increase(VOTING_PERIOD + EXECUTION_DELAY + 1);

            expect(await dao.getProposalState(1)).to.equal(2);
        });

        it("Should return Rejected if against votes win", async function () {
            await dao.connect(owner).vote(1, false);
            await networkHelpers.time.increase(VOTING_PERIOD + 1);

            expect(await dao.getProposalState(1)).to.equal(3);
        });

        it("Should return Rejected if quorum is not reached", async function () {
            await dao.connect(voter3).vote(1, true);
            await networkHelpers.time.increase(VOTING_PERIOD + 1);

            expect(await dao.getProposalState(1)).to.equal(3);
        });

        it("Should return Rejected if no votes cast", async function () {
            await networkHelpers.time.increase(VOTING_PERIOD + 1);

            expect(await dao.getProposalState(1)).to.equal(3);
        });

        it("Should return Executed after execution", async function () {
            await dao.connect(owner).vote(1, true);
            await networkHelpers.time.increase(VOTING_PERIOD + EXECUTION_DELAY + 1);
            await dao.executeProposal(1);

            expect(await dao.getProposalState(1)).to.equal(5);
        });

        it("Should expose the quorum computed from the proposal snapshot", async function () {
            const proposal = await dao.proposals(1);
            const expectedQuorum = (await token.getPastTotalSupply(proposal.snapshotBlock)) / 10n;

            expect(await dao.getProposalQuorum(1)).to.equal(expectedQuorum);
        });

        it("Should revert for non-existent proposal", async function () {
            await expect(dao.getProposalState(999)).to.be.revertedWith("Proposal does not exist");
        });
    });

    describe("View Functions", function () {
        beforeEach(async function () {
            await dao.connect(voter1).createProposal("View Test", "Testing views");
            await networkHelpers.mine();
        });

        it("Should return correct vote counts via getVotes", async function () {
            const proposal = await dao.proposals(1);
            await dao.connect(voter1).vote(1, true);
            await dao.connect(voter2).vote(1, false);

            const [forVotes, againstVotes] = await dao.getVotes(1);
            expect(forVotes).to.equal(await token.getPastVotes(voter1.address, proposal.snapshotBlock));
            expect(againstVotes).to.equal(await token.getPastVotes(voter2.address, proposal.snapshotBlock));
        });
    });
});
