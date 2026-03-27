const { expect } = require("chai");
const { ethers } = require("hardhat");

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
});
