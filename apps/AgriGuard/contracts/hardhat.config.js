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
  selectNetworkAccounts,
} from "./config/runtime-config.js";

const SEPOLIA_RPC_URL = process.env.SEPOLIA_RPC_URL;
const ETHERSCAN_API_KEY = process.env.ETHERSCAN_API_KEY;
const SELECTED_NETWORK = getCliOptionValue("--network");
const INVOKED_TASK = getInvokedTask();
const PRIVATE_KEY = normalizePrivateKey(process.env.PRIVATE_KEY);
const REMOTE_NETWORK_ACCOUNTS = selectNetworkAccounts(
  INVOKED_TASK,
  SELECTED_NETWORK,
  PRIVATE_KEY
);

assertRuntimeConfig({
  taskName: INVOKED_TASK,
  networkName: SELECTED_NETWORK,
  privateKey: PRIVATE_KEY,
  explorerApiKey: ETHERSCAN_API_KEY,
});

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
      default: {
        version: "0.8.28",
        settings: {
          optimizer: {
            enabled: true,
            runs: 200,
          },
        },
      },
    },
  },
  networks: {
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
    etherscan: ETHERSCAN_API_KEY
      ? {
          apiKey: ETHERSCAN_API_KEY,
        }
      : {
          enabled: false,
        },
  },
});
