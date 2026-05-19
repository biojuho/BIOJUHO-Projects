import hre from "hardhat";
import { verifyContract } from "@nomicfoundation/hardhat-verify/verify";

function getExplorerApiKey(networkName) {
    if (networkName === "amoy") {
        return process.env.POLYGONSCAN_API_KEY || process.env.ETHERSCAN_API_KEY;
    }

    if (networkName === "sepolia") {
        return process.env.ETHERSCAN_API_KEY || process.env.POLYGONSCAN_API_KEY;
    }

    return process.env.ETHERSCAN_API_KEY || process.env.POLYGONSCAN_API_KEY;
}

async function main() {
    const connection = await hre.network.create();
    const { ethers } = connection;
    const [deployer] = await ethers.getSigners();

    console.log(`Deploying ResearchPaperNFT on ${connection.networkName} with account:`, deployer.address);
    console.log("Balance:", ethers.formatEther(await ethers.provider.getBalance(deployer.address)));

    const ResearchPaperNFT = await ethers.getContractFactory("ResearchPaperNFT");
    const nft = await ResearchPaperNFT.deploy(deployer.address);

    await nft.waitForDeployment();

    const address = await nft.getAddress();

    console.log("ResearchPaperNFT deployed to:", address);

    const explorerApiKey = getExplorerApiKey(connection.networkName);
    if (explorerApiKey && !["localhost", "default"].includes(connection.networkName)) {
        console.log("Waiting 30s for explorer indexing...");
        await new Promise((resolve) => setTimeout(resolve, 30000));

        try {
            await verifyContract(
                {
                    address,
                    constructorArgs: [deployer.address],
                    provider: "etherscan",
                },
                hre,
            );
            console.log("ResearchPaperNFT verified on explorer!");
        } catch (error) {
            console.log("ResearchPaperNFT verification failed:", error.message);
        }
    }

    console.log("\n=== NFT Deployment Summary ===");
    console.log(`Network:              ${connection.networkName}`);
    console.log(`Deployer:             ${deployer.address}`);
    console.log(`ResearchPaperNFT:     ${address}`);
    console.log("================================");
    console.log(`NFT_CONTRACT_ADDRESS=${address}`);
    console.log();
}

main().catch((error) => {
    console.error(error);
    process.exitCode = 1;
});
