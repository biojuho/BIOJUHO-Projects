import test from "node:test";
import assert from "node:assert/strict";

import {
    assertRuntimeConfig,
    getCliOptionValue,
    getInvokedTask,
    getRuntimeConfigErrors,
    normalizePrivateKey,
    selectExplorerApiKey,
    selectNetworkAccounts,
    shouldRequirePrivateKey,
} from "../config/runtime-config.js";

test("getCliOptionValue returns the matching option value", () => {
    const argv = ["node", "hardhat", "run", "scripts/deploy.js", "--network", "sepolia"];

    assert.equal(getCliOptionValue("--network", argv), "sepolia");
    assert.equal(getCliOptionValue("--missing", argv), undefined);
});

test("getInvokedTask returns the first known hardhat task", () => {
    const argv = ["node", "hardhat", "--network", "amoy", "run", "scripts/deploy.js"];

    assert.equal(getInvokedTask(argv), "run");
});

test("normalizePrivateKey trims whitespace and adds the 0x prefix when missing", () => {
    assert.equal(normalizePrivateKey("  abc123  "), "0xabc123");
    assert.equal(normalizePrivateKey("0xabc123"), "0xabc123");
    assert.equal(normalizePrivateKey("   "), undefined);
});

test("shouldRequirePrivateKey only requires a signer for remote run-like tasks", () => {
    assert.equal(shouldRequirePrivateKey("run", "sepolia"), true);
    assert.equal(shouldRequirePrivateKey("test", "amoy"), true);
    assert.equal(shouldRequirePrivateKey("verify", "sepolia"), false);
    assert.equal(shouldRequirePrivateKey("run", "localhost"), false);
    assert.equal(shouldRequirePrivateKey("compile", "sepolia"), false);
});

test("selectNetworkAccounts keeps verify flows signer-free", () => {
    const privateKey = `0x${"11".repeat(32)}`;

    assert.deepEqual(selectNetworkAccounts("verify", "sepolia", privateKey), []);
    assert.deepEqual(selectNetworkAccounts("run", "sepolia", privateKey), [privateKey]);
});

test("selectExplorerApiKey prefers the chain-appropriate key with cross-chain fallback", () => {
    assert.equal(
        selectExplorerApiKey("sepolia", {
            ETHERSCAN_API_KEY: "etherscan-key",
            POLYGONSCAN_API_KEY: "polygonscan-key",
        }),
        "etherscan-key"
    );
    assert.equal(
        selectExplorerApiKey("amoy", {
            ETHERSCAN_API_KEY: "etherscan-key",
        }),
        "etherscan-key"
    );
});

test("getRuntimeConfigErrors requires a private key for remote deployments", () => {
    assert.deepEqual(
        getRuntimeConfigErrors({
            taskName: "run",
            networkName: "sepolia",
            privateKey: undefined,
            explorerApiKey: undefined,
        }),
        ["PRIVATE_KEY environment variable is required for non-local deployments."]
    );
});

test("getRuntimeConfigErrors rejects malformed signer keys for remote deployments", () => {
    assert.deepEqual(
        getRuntimeConfigErrors({
            taskName: "run",
            networkName: "amoy",
            privateKey: "0xnot-hex",
            explorerApiKey: undefined,
        }),
        ["PRIVATE_KEY must be a 32-byte hex string. You can include or omit the 0x prefix."]
    );
});

test("getRuntimeConfigErrors requires an explorer API key for remote verification", () => {
    assert.deepEqual(
        getRuntimeConfigErrors({
            taskName: "verify",
            networkName: "sepolia",
            privateKey: undefined,
            explorerApiKey: undefined,
        }),
        [
            "Explorer API key is required for 'sepolia' verification. Set ETHERSCAN_API_KEY (or POLYGONSCAN_API_KEY as a fallback).",
        ]
    );
});

test("assertRuntimeConfig throws a grouped error message when validation fails", () => {
    assert.throws(
        () =>
            assertRuntimeConfig({
                taskName: "run",
                networkName: "sepolia",
                privateKey: undefined,
                explorerApiKey: undefined,
            }),
        /Hardhat runtime configuration is invalid:\n- PRIVATE_KEY environment variable is required/
    );
});
