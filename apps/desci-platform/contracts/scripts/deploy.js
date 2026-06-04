import { network } from "hardhat";

const { ethers } = await network.create();

async function main() {
    console.log("🚀 Deploying DeSci Token...");

    const DeSciToken = await ethers.getContractFactory("DeSciToken");
    const token = await DeSciToken.deploy();

    await token.waitForDeployment();

    const address = await token.getAddress();

    console.log("✅ DeSci Token deployed to:", address);
    console.log("👉 Add this address to your backend .env file as DSCI_CONTRACT_ADDRESS");
}

main().catch((error) => {
    console.error(error);
    process.exitCode = 1;
});
