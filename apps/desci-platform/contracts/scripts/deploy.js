import hre from "hardhat";

import {
    deployCoreContracts,
    printDeploymentSummary,
} from "./lib/deploy-contracts.js";

async function main() {
    const deployment = await deployCoreContracts(hre);
    printDeploymentSummary(deployment);
}

main().catch((error) => {
    console.error(error);
    process.exitCode = 1;
});
