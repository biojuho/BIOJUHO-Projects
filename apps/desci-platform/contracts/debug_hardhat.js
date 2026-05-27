import fs from "node:fs";
import hre from "hardhat";

async function main() {
    const sources = hre.config.paths.sources;
    const sourceDirectories =
        typeof sources === "string"
            ? [sources]
            : Array.isArray(sources?.solidity)
              ? sources.solidity
              : [];

    console.log("Sources path:", sources);

    for (const directory of sourceDirectories) {
        if (fs.existsSync(directory)) {
            console.log(`Files in ${directory}:`, fs.readdirSync(directory));
        } else {
            console.log(`Source path does not exist: ${directory}`);
        }
    }
}

main();
