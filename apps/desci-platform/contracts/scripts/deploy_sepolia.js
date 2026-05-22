// SPDX-License-Identifier: MIT
/**
 * DeSci Platform Sepolia testnet deployment script.
 * Deploys DeSciToken, ResearchPaperNFT, and DeSciDAO.
 *
 * Usage:
 *   npx hardhat run scripts/deploy_sepolia.js --network sepolia
 */

import hre from "hardhat";

import {
    deployCoreContracts,
    printDeploymentSummary,
    verifyCoreContracts,
} from "./lib/deploy-contracts.js";

async function main() {
    const deployment = await deployCoreContracts(hre);
    await verifyCoreContracts(hre, deployment);
    printDeploymentSummary(deployment);
}

main()
    .then(() => process.exit(0))
    .catch((error) => {
        console.error(error);
        process.exit(1);
    });
