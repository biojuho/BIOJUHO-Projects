// SPDX-License-Identifier: MIT
/**
 * DeSci Platform — Sepolia Testnet Deployment Script
 * Deploys BioLinker (IP-NFT) + DSCIToken contracts.
 *
 * Usage:
 *   npx hardhat run scripts/deploy_sepolia.js --network sepolia
 *
 * Prerequisites:
 *   - SEPOLIA_RPC_URL in .env
 *   - PRIVATE_KEY in .env (deployer wallet with Sepolia ETH)
 */

import { network } from "hardhat";

const connection = await network.create();
const { ethers } = connection;

async function main() {
  const [deployer] = await ethers.getSigners();
  console.log("Deploying DeSci contracts with:", deployer.address);
  console.log("Balance:", ethers.formatEther(await ethers.provider.getBalance(deployer.address)), "ETH");

  // 1. Deploy DSCI Token
  const DSCIToken = await ethers.getContractFactory("DSCIToken");
  const dsciToken = await DSCIToken.deploy();
  await dsciToken.waitForDeployment();
  const tokenAddress = await dsciToken.getAddress();
  console.log("DSCIToken deployed to:", tokenAddress);

  // 2. Deploy BioLinker (IP-NFT)
  const BioLinker = await ethers.getContractFactory("BioLinker");
  const bioLinker = await BioLinker.deploy();
  await bioLinker.waitForDeployment();
  const nftAddress = await bioLinker.getAddress();
  console.log("BioLinker IP-NFT deployed to:", nftAddress);

  // 3. Optional verification
  if (connection.networkName === "sepolia") {
    console.log("Etherscan verification skipped; hardhat-verify is not installed.");
  }

  console.log("\n=== DeSci Deployment Summary ===");
  console.log(`Network:     ${connection.networkName}`);
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
