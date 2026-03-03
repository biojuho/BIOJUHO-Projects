// SPDX-License-Identifier: MIT
/**
 * AgriGuard — Sepolia Testnet Deployment Script
 * 
 * Usage:
 *   npx hardhat run scripts/deploy_sepolia.js --network sepolia
 * 
 * Prerequisites:
 *   - SEPOLIA_RPC_URL in .env (Alchemy/Infura)
 *   - PRIVATE_KEY in .env (deployer wallet with Sepolia ETH)
 *   - ETHERSCAN_API_KEY in .env (for verification)
 */

const hre = require("hardhat");

async function main() {
  const [deployer] = await hre.ethers.getSigners();
  console.log("Deploying AgriGuard contracts with:", deployer.address);
  console.log("Balance:", hre.ethers.formatEther(await hre.ethers.provider.getBalance(deployer.address)), "ETH");

  // Deploy AgriGuard main contract
  const AgriGuard = await hre.ethers.getContractFactory("AgriGuard");
  const agriGuard = await AgriGuard.deploy();
  await agriGuard.waitForDeployment();
  const contractAddress = await agriGuard.getAddress();
  console.log("AgriGuard deployed to:", contractAddress);

  // Verify on Etherscan (wait for propagation)
  if (hre.network.name === "sepolia") {
    console.log("Waiting 30s for Etherscan indexing...");
    await new Promise((r) => setTimeout(r, 30000));
    try {
      await hre.run("verify:verify", {
        address: contractAddress,
        constructorArguments: [],
      });
      console.log("Contract verified on Etherscan!");
    } catch (e) {
      console.log("Verification failed (may already be verified):", e.message);
    }
  }

  console.log("\n=== Deployment Summary ===");
  console.log(`Network:  ${hre.network.name}`);
  console.log(`Contract: ${contractAddress}`);
  console.log(`Deployer: ${deployer.address}`);
  console.log("========================\n");
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
