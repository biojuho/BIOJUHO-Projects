const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("DeSciToken", function () {
    let DeSciToken;
    let token;
    let owner;
    let distributor;
    let user1;
    let user2;

    const INITIAL_SUPPLY = ethers.parseEther("10000000"); // 10M DSCI
    const MAX_SUPPLY = ethers.parseEther("100000000"); // 100M DSCI
    const REWARD_PAPER_UPLOAD = ethers.parseEther("100");
    const REWARD_PEER_REVIEW = ethers.parseEther("50");
    const REWARD_DATA_SHARE = ethers.parseEther("200");
    const REWARD_RESEARCH_PARTICIPATION = ethers.parseEther("300");

    beforeEach(async function () {
        [owner, distributor, user1, user2] = await ethers.getSigners();
        DeSciToken = await ethers.getContractFactory("DeSciToken");
        token = await DeSciToken.deploy();
        await token.waitForDeployment();
    });

    // ── Deployment ──────────────────────────────

    describe("Deployment", function () {
        it("Should have correct name and symbol", async function () {
            expect(await token.name()).to.equal("DeSci Token");
            expect(await token.symbol()).to.equal("DSCI");
        });

        it("Should mint initial supply to deployer", async function () {
            expect(await token.balanceOf(owner.address)).to.equal(INITIAL_SUPPLY);
        });

        it("Should set correct total supply", async function () {
            expect(await token.totalSupply()).to.equal(INITIAL_SUPPLY);
        });

        it("Should set deployer as owner", async function () {
            expect(await token.owner()).to.equal(owner.address);
        });

        it("Should have 18 decimals", async function () {
            expect(await token.decimals()).to.equal(18);
        });

        it("Should have correct MAX_SUPPLY constant", async function () {
            expect(await token.MAX_SUPPLY()).to.equal(MAX_SUPPLY);
        });
    });

    // ── Reward Constants ────────────────────────

    describe("Reward Constants", function () {
        it("Should return correct reward amounts via getRewardAmounts()", async function () {
            const [paperUpload, peerReview, dataShare, researchParticipation] =
                await token.getRewardAmounts();

            expect(paperUpload).to.equal(REWARD_PAPER_UPLOAD);
            expect(peerReview).to.equal(REWARD_PEER_REVIEW);
            expect(dataShare).to.equal(REWARD_DATA_SHARE);
            expect(researchParticipation).to.equal(REWARD_RESEARCH_PARTICIPATION);
        });
    });

    // ── Distributor Management ──────────────────

    describe("Distributor Management", function () {
        it("Should allow owner to add a distributor", async function () {
            await expect(token.addDistributor(distributor.address))
                .to.emit(token, "DistributorAdded")
                .withArgs(distributor.address);

            expect(await token.rewardDistributors(distributor.address)).to.equal(true);
        });

        it("Should allow owner to remove a distributor", async function () {
            await token.addDistributor(distributor.address);

            await expect(token.removeDistributor(distributor.address))
                .to.emit(token, "DistributorRemoved")
                .withArgs(distributor.address);

            expect(await token.rewardDistributors(distributor.address)).to.equal(false);
        });

        it("Should not allow non-owner to add a distributor", async function () {
            await expect(
                token.connect(user1).addDistributor(distributor.address)
            ).to.be.revertedWithCustomError(token, "OwnableUnauthorizedAccount");
        });

        it("Should not allow non-owner to remove a distributor", async function () {
            await token.addDistributor(distributor.address);
            await expect(
                token.connect(user1).removeDistributor(distributor.address)
            ).to.be.revertedWithCustomError(token, "OwnableUnauthorizedAccount");
        });
    });

    // ── Reward Distribution ─────────────────────

    describe("Reward Distribution", function () {
        beforeEach(async function () {
            await token.addDistributor(distributor.address);
        });

        it("Should reward paper upload (100 DSCI)", async function () {
            await expect(token.connect(distributor).rewardPaperUpload(user1.address))
                .to.emit(token, "RewardDistributed")
                .withArgs(user1.address, REWARD_PAPER_UPLOAD, "Paper Upload");

            expect(await token.balanceOf(user1.address)).to.equal(REWARD_PAPER_UPLOAD);
        });

        it("Should reward peer review (50 DSCI)", async function () {
            await expect(token.connect(distributor).rewardPeerReview(user1.address))
                .to.emit(token, "RewardDistributed")
                .withArgs(user1.address, REWARD_PEER_REVIEW, "Peer Review");

            expect(await token.balanceOf(user1.address)).to.equal(REWARD_PEER_REVIEW);
        });

        it("Should reward data share (200 DSCI)", async function () {
            await expect(token.connect(distributor).rewardDataShare(user1.address))
                .to.emit(token, "RewardDistributed")
                .withArgs(user1.address, REWARD_DATA_SHARE, "Data Share");

            expect(await token.balanceOf(user1.address)).to.equal(REWARD_DATA_SHARE);
        });

        it("Should distribute custom reward amount", async function () {
            const customAmount = ethers.parseEther("500");
            await expect(
                token.connect(distributor).distributeReward(user1.address, customAmount, "Custom Reward")
            )
                .to.emit(token, "RewardDistributed")
                .withArgs(user1.address, customAmount, "Custom Reward");

            expect(await token.balanceOf(user1.address)).to.equal(customAmount);
        });

        it("Should allow owner to distribute rewards directly", async function () {
            await expect(token.rewardPaperUpload(user1.address))
                .to.emit(token, "RewardDistributed")
                .withArgs(user1.address, REWARD_PAPER_UPLOAD, "Paper Upload");
        });

        it("Should not allow unauthorized address to distribute rewards", async function () {
            await expect(
                token.connect(user1).rewardPaperUpload(user2.address)
            ).to.be.revertedWith("Not authorized to distribute rewards");
        });

        it("Should not allow unauthorized address to call distributeReward", async function () {
            await expect(
                token.connect(user1).distributeReward(user2.address, ethers.parseEther("100"), "Hack")
            ).to.be.revertedWith("Not authorized to distribute rewards");
        });

        it("Should accumulate multiple rewards", async function () {
            await token.connect(distributor).rewardPaperUpload(user1.address);
            await token.connect(distributor).rewardPeerReview(user1.address);

            const expectedBalance = REWARD_PAPER_UPLOAD + REWARD_PEER_REVIEW;
            expect(await token.balanceOf(user1.address)).to.equal(expectedBalance);
        });
    });

    // ── Max Supply Cap ──────────────────────────

    describe("Max Supply Cap", function () {
        beforeEach(async function () {
            await token.addDistributor(distributor.address);
        });

        it("Should enforce max supply on distributeReward", async function () {
            // Try to mint more than MAX_SUPPLY - INITIAL_SUPPLY
            const remaining = MAX_SUPPLY - INITIAL_SUPPLY;
            const overAmount = remaining + ethers.parseEther("1");

            await expect(
                token.connect(distributor).distributeReward(user1.address, overAmount, "Too much")
            ).to.be.revertedWith("Max supply exceeded");
        });

        it("Should enforce max supply on rewardPaperUpload", async function () {
            // First mint up to near max supply
            const remaining = MAX_SUPPLY - INITIAL_SUPPLY;
            // Mint all but 50 tokens (less than REWARD_PAPER_UPLOAD = 100)
            const almostAll = remaining - ethers.parseEther("50");
            await token.connect(distributor).distributeReward(user1.address, almostAll, "Fill up");

            // Now paper upload (100 DSCI) should fail
            await expect(
                token.connect(distributor).rewardPaperUpload(user2.address)
            ).to.be.revertedWith("Max supply exceeded");
        });

        it("Should enforce max supply on rewardPeerReview", async function () {
            const remaining = MAX_SUPPLY - INITIAL_SUPPLY;
            const almostAll = remaining - ethers.parseEther("10");
            await token.connect(distributor).distributeReward(user1.address, almostAll, "Fill up");

            await expect(
                token.connect(distributor).rewardPeerReview(user2.address)
            ).to.be.revertedWith("Max supply exceeded");
        });

        it("Should enforce max supply on rewardDataShare", async function () {
            const remaining = MAX_SUPPLY - INITIAL_SUPPLY;
            const almostAll = remaining - ethers.parseEther("10");
            await token.connect(distributor).distributeReward(user1.address, almostAll, "Fill up");

            await expect(
                token.connect(distributor).rewardDataShare(user2.address)
            ).to.be.revertedWith("Max supply exceeded");
        });

        it("Should allow minting up to exactly max supply", async function () {
            const remaining = MAX_SUPPLY - INITIAL_SUPPLY;
            await token.connect(distributor).distributeReward(user1.address, remaining, "Exact max");

            expect(await token.totalSupply()).to.equal(MAX_SUPPLY);
        });
    });

    // ── ERC20 Standard Functions ────────────────

    describe("ERC20 Standard", function () {
        it("Should transfer tokens between accounts", async function () {
            const amount = ethers.parseEther("1000");
            await token.transfer(user1.address, amount);
            expect(await token.balanceOf(user1.address)).to.equal(amount);
        });

        it("Should approve and transferFrom", async function () {
            const amount = ethers.parseEther("1000");
            await token.approve(user1.address, amount);
            await token.connect(user1).transferFrom(owner.address, user2.address, amount);
            expect(await token.balanceOf(user2.address)).to.equal(amount);
        });

        it("Should support burning (ERC20Burnable)", async function () {
            const burnAmount = ethers.parseEther("1000");
            const initialBalance = await token.balanceOf(owner.address);
            await token.burn(burnAmount);
            expect(await token.balanceOf(owner.address)).to.equal(initialBalance - burnAmount);
        });
    });
});
