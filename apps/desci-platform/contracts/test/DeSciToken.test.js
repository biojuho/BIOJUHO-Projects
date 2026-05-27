import { expect } from "chai";
import { network } from "hardhat";

const { ethers } = await network.create();

describe("DeSciToken", function () {
    let DeSciToken;
    let token;
    let owner;
    let distributor;
    let user1;
    let user2;

    const INITIAL_SUPPLY = ethers.parseEther("10000000");
    const MAX_SUPPLY = ethers.parseEther("100000000");
    const REWARD_PAPER_UPLOAD = ethers.parseEther("100");
    const REWARD_PEER_REVIEW = ethers.parseEther("50");
    const REWARD_DATA_SHARE = ethers.parseEther("200");
    const REWARD_RESEARCH_PARTICIPATION = ethers.parseEther("300");
    const ZERO_ADDRESS = ethers.ZeroAddress;

    beforeEach(async function () {
        [owner, distributor, user1, user2] = await ethers.getSigners();
        DeSciToken = await ethers.getContractFactory("DeSciToken");
        token = await DeSciToken.deploy();
        await token.waitForDeployment();
    });

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

        it("Should reject the zero address as a distributor", async function () {
            await expect(token.addDistributor(ZERO_ADDRESS)).to.be.revertedWith(
                "Distributor address required"
            );
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

        it("Should reject rewarding the zero address", async function () {
            await expect(
                token.connect(distributor).rewardPaperUpload(ZERO_ADDRESS)
            ).to.be.revertedWith("Reward recipient required");
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

    describe("Max Supply Cap", function () {
        beforeEach(async function () {
            await token.addDistributor(distributor.address);
        });

        it("Should enforce max supply on distributeReward", async function () {
            const remaining = MAX_SUPPLY - INITIAL_SUPPLY;
            const overAmount = remaining + ethers.parseEther("1");

            await expect(
                token.connect(distributor).distributeReward(user1.address, overAmount, "Too much")
            ).to.be.revertedWith("Max supply exceeded");
        });

        it("Should enforce max supply on rewardPaperUpload", async function () {
            const remaining = MAX_SUPPLY - INITIAL_SUPPLY;
            const almostAll = remaining - ethers.parseEther("50");
            await token.connect(distributor).distributeReward(user1.address, almostAll, "Fill up");

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

    describe("Voting Extensions", function () {
        it("Should require delegation before votes are active", async function () {
            expect(await token.getVotes(owner.address)).to.equal(0);

            await token.delegate(owner.address);

            expect(await token.getVotes(owner.address)).to.equal(INITIAL_SUPPLY);
        });

        it("Should move delegated voting power on transfers", async function () {
            const amount = ethers.parseEther("1000");

            await token.delegate(owner.address);
            await token.transfer(user1.address, amount);

            expect(await token.getVotes(owner.address)).to.equal(INITIAL_SUPPLY - amount);
            expect(await token.getVotes(user1.address)).to.equal(0);

            await token.connect(user1).delegate(user1.address);
            expect(await token.getVotes(user1.address)).to.equal(amount);
        });

        it("Should preserve historical voting power snapshots", async function () {
            const amount = ethers.parseEther("1000");

            await token.delegate(owner.address);
            const snapshotBlock = await ethers.provider.getBlockNumber();

            await token.transfer(user1.address, amount);

            expect(await token.getPastVotes(owner.address, snapshotBlock)).to.equal(INITIAL_SUPPLY);
            expect(await token.getVotes(owner.address)).to.equal(INITIAL_SUPPLY - amount);
        });
    });
});
