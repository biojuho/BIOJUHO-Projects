const hre = require("hardhat");

async function main() {
    const [deployer] = await hre.ethers.getSigners();

    console.log("🚀 Deploying ResearchPaperNFT with account:", deployer.address);

    const ResearchPaperNFT = await hre.ethers.getContractFactory("ResearchPaperNFT");
    const nft = await ResearchPaperNFT.deploy(deployer.address);

    await nft.waitForDeployment();

    const address = await nft.getAddress();

    console.log("✅ ResearchPaperNFT deployed to:", address);
    console.log("👉 Add this address to your backend .env file as NFT_CONTRACT_ADDRESS");
}

main().catch((error) => {
    console.error(error);
    process.exitCode = 1;
});
