const KNOWN_TASKS = new Set([
    "build",
    "clean",
    "compile",
    "console",
    "flatten",
    "node",
    "run",
    "telemetry",
    "test",
    "verify",
]);

const SIGNER_REQUIRED_TASKS = new Set(["console", "run", "test"]);
const LOCAL_NETWORKS = new Set(["hardhat", "localhost"]);

function isRemoteNetwork(networkName) {
    return Boolean(networkName) && !LOCAL_NETWORKS.has(networkName);
}

export function getCliOptionValue(optionName, argv = process.argv) {
    const optionIndex = argv.indexOf(optionName);
    return optionIndex === -1 ? undefined : argv[optionIndex + 1];
}

export function getInvokedTask(argv = process.argv) {
    return argv.slice(2).find((argument) => KNOWN_TASKS.has(argument));
}

export function normalizePrivateKey(value) {
    if (typeof value !== "string") {
        return undefined;
    }

    const trimmedValue = value.trim();

    if (trimmedValue === "") {
        return undefined;
    }

    return trimmedValue.startsWith("0x") ? trimmedValue : `0x${trimmedValue}`;
}

export function isHexPrivateKey(value) {
    return typeof value === "string" && /^0x[0-9a-fA-F]{64}$/.test(value);
}

export function shouldRequirePrivateKey(taskName, networkName) {
    return isRemoteNetwork(networkName) && SIGNER_REQUIRED_TASKS.has(taskName);
}

export function selectNetworkAccounts(taskName, networkName, privateKey) {
    if (!shouldRequirePrivateKey(taskName, networkName) || !privateKey) {
        return [];
    }

    return [privateKey];
}

export function selectExplorerApiKey(networkName, env = process.env) {
    if (networkName === "amoy") {
        return env.POLYGONSCAN_API_KEY || env.ETHERSCAN_API_KEY;
    }

    if (networkName === "sepolia") {
        return env.ETHERSCAN_API_KEY || env.POLYGONSCAN_API_KEY;
    }

    return env.ETHERSCAN_API_KEY || env.POLYGONSCAN_API_KEY;
}

function explorerApiKeyHint(networkName) {
    if (networkName === "amoy") {
        return "Set POLYGONSCAN_API_KEY (or ETHERSCAN_API_KEY as a fallback).";
    }

    if (networkName === "sepolia") {
        return "Set ETHERSCAN_API_KEY (or POLYGONSCAN_API_KEY as a fallback).";
    }

    return "Set ETHERSCAN_API_KEY or POLYGONSCAN_API_KEY.";
}

export function getRuntimeConfigErrors({ taskName, networkName, privateKey, explorerApiKey }) {
    const errors = [];
    const requiresSigner = shouldRequirePrivateKey(taskName, networkName);
    const requiresExplorerApiKey = taskName === "verify" && isRemoteNetwork(networkName);

    if (requiresSigner && !privateKey) {
        errors.push("PRIVATE_KEY environment variable is required for non-local deployments.");
    }

    if (requiresSigner && privateKey && !isHexPrivateKey(privateKey)) {
        errors.push("PRIVATE_KEY must be a 32-byte hex string. You can include or omit the 0x prefix.");
    }

    if (requiresExplorerApiKey && !explorerApiKey) {
        errors.push(`Explorer API key is required for '${networkName}' verification. ${explorerApiKeyHint(networkName)}`);
    }

    return errors;
}

export function assertRuntimeConfig(input) {
    const errors = getRuntimeConfigErrors(input);

    if (errors.length === 0) {
        return;
    }

    throw new Error(["Hardhat runtime configuration is invalid:", ...errors.map((error) => `- ${error}`)].join("\n"));
}
