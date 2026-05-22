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

function getExplorerLabel(networkName) {
    if (networkName === "amoy") {
        return "Polygonscan";
    }

    if (networkName === "sepolia") {
        return "Etherscan";
    }

    return "block explorer";
}

function sleep(milliseconds) {
    return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

export async function deployCoreContracts(hre, options = {}) {
    const { deployDao = true } = options;
    const connection = await hre.network.create();
    const { ethers } = connection;
    const [deployer] = await ethers.getSigners();

    console.log(`Deploying DeSci contracts on ${connection.networkName} with:`, deployer.address);
    console.log("Balance:", ethers.formatEther(await ethers.provider.getBalance(deployer.address)));

    const DeSciToken = await ethers.getContractFactory("DeSciToken");
    const dsciToken = await DeSciToken.deploy();
    await dsciToken.waitForDeployment();
    const tokenAddress = await dsciToken.getAddress();
    console.log("DeSciToken deployed to:", tokenAddress);

    const ResearchPaperNFT = await ethers.getContractFactory("ResearchPaperNFT");
    const researchPaperNft = await ResearchPaperNFT.deploy(deployer.address);
    await researchPaperNft.waitForDeployment();
    const nftAddress = await researchPaperNft.getAddress();
    console.log("ResearchPaperNFT deployed to:", nftAddress);

    let daoAddress;
    if (deployDao) {
        const DeSciDAO = await ethers.getContractFactory("DeSciDAO");
        const dsciDao = await DeSciDAO.deploy(tokenAddress);
        await dsciDao.waitForDeployment();
        daoAddress = await dsciDao.getAddress();
        console.log("DeSciDAO deployed to:", daoAddress);
    }

    return {
        connection,
        deployer,
        contracts: [
            {
                name: "DeSciToken",
                address: tokenAddress,
                constructorArgs: [],
            },
            {
                name: "ResearchPaperNFT",
                address: nftAddress,
                constructorArgs: [deployer.address],
            },
            ...(daoAddress
                ? [
                      {
                          name: "DeSciDAO",
                          address: daoAddress,
                          constructorArgs: [tokenAddress],
                      },
                  ]
                : []),
        ],
    };
}

export async function verifyCoreContracts(hre, deployment) {
    const { connection, contracts } = deployment;
    const explorerApiKey = getExplorerApiKey(connection.networkName);

    if (!explorerApiKey || connection.networkName === "localhost") {
        return;
    }

    console.log(`Waiting 30s for ${getExplorerLabel(connection.networkName)} indexing...`);
    await sleep(30000);

    for (const contract of contracts) {
        try {
            await verifyContract(
                {
                    address: contract.address,
                    constructorArgs: contract.constructorArgs,
                    provider: "etherscan",
                },
                hre,
            );
            console.log(`${contract.name} verified on ${getExplorerLabel(connection.networkName)}!`);
        } catch (error) {
            console.log(`${contract.name} verification failed:`, error.message);
        }
    }
}

export function printDeploymentSummary(deployment) {
    const { connection, deployer, contracts } = deployment;

    console.log("\n=== DeSci Deployment Summary ===");
    console.log(`Network:          ${connection.networkName}`);
    console.log(`Deployer:         ${deployer.address}`);

    for (const contract of contracts) {
        console.log(`${`${contract.name}:`.padEnd(18)} ${contract.address}`);
    }

    const token = contracts.find((contract) => contract.name === "DeSciToken");
    const nft = contracts.find((contract) => contract.name === "ResearchPaperNFT");
    const dao = contracts.find((contract) => contract.name === "DeSciDAO");

    console.log("================================");
    console.log("Backend env:");
    if (token) {
        console.log(`DSCI_CONTRACT_ADDRESS=${token.address}`);
    }
    if (nft) {
        console.log(`NFT_CONTRACT_ADDRESS=${nft.address}`);
    }
    if (dao) {
        console.log(`# Optional governance contract`);
        console.log(`DESCI_DAO_CONTRACT_ADDRESS=${dao.address}`);
    }
    console.log();
}
