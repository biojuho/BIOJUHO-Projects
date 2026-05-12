// SPDX-License-Identifier: MIT
/**
 * DeSci Platform — Polygon Amoy Testnet Deployment Script
 * Deploys BioLinker (IP-NFT) + DSCIToken contracts.
 *
 * Usage:
 *   npx hardhat run scripts/deploy_amoy.js --network amoy
 *
 * Prerequisites:
 *   - AMOY_RPC_URL in .env (or uses default public RPC)
 *   - PRIVATE_KEY in .env (deployer wallet with Amoy MATIC)
 *   - POLYGONSCAN_API_KEY in .env (for verification, optional)
 */

const hre = require("hardhat");

async function main() {
  const [deployer] = await hre.ethers.getSigners();
  console.log("Deploying DeSci contracts to Polygon Amoy with:", deployer.address);
  console.log("Balance:", hre.ethers.formatEther(await hre.ethers.provider.getBalance(deployer.address)), "POL (MATIC)");

  // 1. Deploy DSCI Token
  const DSCIToken = await hre.ethers.getContractFactory("DSCIToken");
  const dsciToken = await DSCIToken.deploy();
  await dsciToken.waitForDeployment();
  const tokenAddress = await dsciToken.getAddress();
  console.log("DSCIToken deployed to:", tokenAddress);

  // 2. Deploy BioLinker (IP-NFT)
  const BioLinker = await hre.ethers.getContractFactory("BioLinker");
  const bioLinker = await BioLinker.deploy();
  await bioLinker.waitForDeployment();
  const nftAddress = await bioLinker.getAddress();
  console.log("BioLinker IP-NFT deployed to:", nftAddress);

  // 3. Verification (Optional, if PolyScan API Key is configured)
  if (hre.network.name === "amoy" && process.env.POLYGONSCAN_API_KEY) {
    console.log("Waiting 30s for Polygonscan indexing...");
    await new Promise((r) => setTimeout(r, 30000));

    for (const [name, addr] of [["DSCIToken", tokenAddress], ["BioLinker", nftAddress]]) {
      try {
        await hre.run("verify:verify", { address: addr, constructorArguments: [] });
        console.log(`${name} verified on Polygonscan!`);
      } catch (e) {
        console.log(`${name} verification failed:`, e.message);
      }
    }
  }

  console.log("\n=== Polygon Amoy Deployment Summary ===");
  console.log(`Network:     ${hre.network.name}`);
  console.log(`DSCIToken:   ${tokenAddress}`);
  console.log(`BioLinker:   ${nftAddress}`);
  console.log(`Deployer:    ${deployer.address}`);
  console.log("================================\n");
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
