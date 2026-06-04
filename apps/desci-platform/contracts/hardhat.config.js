import hardhatEthers from "@nomicfoundation/hardhat-ethers";
import hardhatEthersChaiMatchers from "@nomicfoundation/hardhat-ethers-chai-matchers";
import hardhatMocha from "@nomicfoundation/hardhat-mocha";
import hardhatNetworkHelpers from "@nomicfoundation/hardhat-network-helpers";
import { configVariable, defineConfig } from "hardhat/config";
import dotenv from "dotenv";

dotenv.config();

const AMOY_RPC_URL = process.env.AMOY_RPC_URL || "https://rpc-amoy.polygon.technology";
const SEPOLIA_RPC_URL = process.env.SEPOLIA_RPC_URL;
const PRIVATE_KEY = process.env.PRIVATE_KEY;

if (!PRIVATE_KEY && (process.argv.includes("--network") && !process.argv.includes("localhost"))) {
    console.error("ERROR: PRIVATE_KEY environment variable is required for non-local deployments.");
    console.error("Copy .env.example to .env and fill in your credentials.");
    process.exit(1);
}

/** @type import('hardhat/config').HardhatUserConfig */
const config = defineConfig({
    plugins: [
        hardhatEthers,
        hardhatEthersChaiMatchers,
        hardhatMocha,
        hardhatNetworkHelpers,
    ],
    solidity: {
        profiles: {
            default: {
                version: "0.8.24",
                settings: {
                    optimizer: {
                        enabled: true,
                        runs: 200,
                    },
                    viaIR: true,
                },
            },
        },
    },
    networks: {
        hardhatMainnet: {
            type: "edr-simulated",
            chainType: "l1",
        },
        amoy: {
            type: "http",
            chainType: "l1",
            url: AMOY_RPC_URL,
            accounts: PRIVATE_KEY ? [PRIVATE_KEY] : [],
            chainId: 80002,
        },
        sepolia: {
            type: "http",
            chainType: "l1",
            url: SEPOLIA_RPC_URL || configVariable("SEPOLIA_RPC_URL"),
            accounts: PRIVATE_KEY ? [PRIVATE_KEY] : [],
            chainId: 11155111,
        },
        localhost: {
            type: "http",
            chainType: "l1",
            url: "http://127.0.0.1:8545",
        },
    },
});

export default config;
