import { expect } from "chai";
import { network } from "hardhat";

const { ethers } = await network.create();
const { ZeroAddress } = ethers;

describe("ResearchPaperNFT", function () {
    let ResearchPaperNFT;
    let nft;
    let owner;
    let addr1;
    let addr2;

    beforeEach(async function () {
        [owner, addr1, addr2] = await ethers.getSigners();
        ResearchPaperNFT = await ethers.getContractFactory("ResearchPaperNFT");
        nft = await ResearchPaperNFT.deploy(owner.address);
        await nft.waitForDeployment();
    });

    it("Should set the right owner", async function () {
        expect(await nft.owner()).to.equal(owner.address);
    });

    it("Should mint a paper NFT to recipient", async function () {
        const tokenURI = "ipfs://QmTest123";

        // Mint to addr1
        await nft.mintPaper(addr1.address, tokenURI);

        // Check balance
        expect(await nft.balanceOf(addr1.address)).to.equal(1);

        // Check owner of token 0
        expect(await nft.ownerOf(0)).to.equal(addr1.address);

        // Check token URI
        expect(await nft.tokenURI(0)).to.equal(tokenURI);
    });

    it("Should only allow owner to mint", async function () {
        const tokenURI = "ipfs://QmTest123";

        // Try to mint from addr1 (should fail)
        await expect(
            nft.connect(addr1).mintPaper(addr1.address, tokenURI)
        ).to.be.revertedWithCustomError(nft, "OwnableUnauthorizedAccount");
    });

    it("Should reject an empty token URI", async function () {
        await expect(nft.mintPaper(addr1.address, "")).to.be.revertedWith("Token URI required");
    });

    it("Should configure a default 5% royalty", async function () {
        const salePrice = ethers.parseEther("1");
        const [receiver, royaltyAmount] = await nft.royaltyInfo(0, salePrice);

        expect(receiver).to.equal(owner.address);
        expect(royaltyAmount).to.equal(ethers.parseEther("0.05"));
    });

    it("Should allow the owner to update default royalty", async function () {
        await nft.setDefaultRoyalty(addr2.address, 750);

        const [receiver, royaltyAmount] = await nft.royaltyInfo(0, ethers.parseEther("2"));
        expect(receiver).to.equal(addr2.address);
        expect(royaltyAmount).to.equal(ethers.parseEther("0.15"));
    });

    it("Should allow token-level royalty overrides", async function () {
        await nft.mintPaper(addr1.address, "ipfs://QmRoyaltyTest");
        await nft.setTokenRoyalty(0, addr2.address, 1000);

        const [receiver, royaltyAmount] = await nft.royaltyInfo(0, ethers.parseEther("3"));
        expect(receiver).to.equal(addr2.address);
        expect(royaltyAmount).to.equal(ethers.parseEther("0.3"));
    });

    it("Should reject zero-address initial owner", async function () {
        await expect(ResearchPaperNFT.deploy(ZeroAddress)).to.be.revertedWithCustomError(
            ResearchPaperNFT,
            "OwnableInvalidOwner"
        );
    });
});
