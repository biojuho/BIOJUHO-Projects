import hardhatEthers from "@nomicfoundation/hardhat-ethers";
import hardhatEthersChaiMatchers from "@nomicfoundation/hardhat-ethers-chai-matchers";
import hardhatMocha from "@nomicfoundation/hardhat-mocha";
import hardhatNetworkHelpers from "@nomicfoundation/hardhat-network-helpers";
import hardhatVerify from "@nomicfoundation/hardhat-verify";
import "dotenv/config";
import { configVariable, defineConfig } from "hardhat/config";
import {
    assertRuntimeConfig,
    getCliOptionValue,
    getInvokedTask,
    normalizePrivateKey,
    selectExplorerApiKey,
    selectNetworkAccounts,
} from "./config/runtime-config.js";

const AMOY_RPC_URL = process.env.AMOY_RPC_URL || "https://rpc-amoy.polygon.technology";
const SEPOLIA_RPC_URL = process.env.SEPOLIA_RPC_URL;
const SELECTED_NETWORK = getCliOptionValue("--network");
const INVOKED_TASK = getInvokedTask();
const PRIVATE_KEY = normalizePrivateKey(process.env.PRIVATE_KEY);
const EXPLORER_API_KEY = selectExplorerApiKey(SELECTED_NETWORK, process.env);
const REMOTE_NETWORK_ACCOUNTS = selectNetworkAccounts(INVOKED_TASK, SELECTED_NETWORK, PRIVATE_KEY);

assertRuntimeConfig({
    taskName: INVOKED_TASK,
    networkName: SELECTED_NETWORK,
    privateKey: PRIVATE_KEY,
    explorerApiKey: EXPLORER_API_KEY,
});

function createSolidityProfile() {
    return {
        version: "0.8.24",
        settings: {
            optimizer: {
                enabled: true,
                runs: 200,
            },
            viaIR: true,
            evmVersion: "cancun",
        },
    };
}

export default defineConfig({
    plugins: [
        hardhatEthers,
        hardhatEthersChaiMatchers,
        hardhatMocha,
        hardhatNetworkHelpers,
        hardhatVerify,
    ],
    solidity: {
        profiles: {
            default: createSolidityProfile(),
            // Keep explorer verification aligned with the same compiler settings
            // used by build and run tasks.
            production: createSolidityProfile(),
        },
    },
    networks: {
        amoy: {
            type: "http",
            chainType: "l1",
            url: AMOY_RPC_URL || configVariable("AMOY_RPC_URL"),
            // Leave accounts empty when no signer is needed, e.g. explorer verification.
            accounts: REMOTE_NETWORK_ACCOUNTS,
            chainId: 80002,
        },
        sepolia: {
            type: "http",
            chainType: "l1",
            url: SEPOLIA_RPC_URL || configVariable("SEPOLIA_RPC_URL"),
            accounts: REMOTE_NETWORK_ACCOUNTS,
            chainId: 11155111,
        },
        localhost: {
            type: "http",
            chainType: "l1",
            url: "http://127.0.0.1:8545",
        },
    },
    verify: {
        etherscan: EXPLORER_API_KEY
            ? {
                  apiKey: EXPLORER_API_KEY,
              }
            : {
                  enabled: false,
              },
    },
});
