import hre from "hardhat";
import fs from "fs";

async function main() {
    console.log("Sources path:", hre.config.paths.sources);
    if (fs.existsSync(hre.config.paths.sources)) {
        console.log("Files in sources:", fs.readdirSync(hre.config.paths.sources));
    } else {
        console.log("Sources path does not exist!");
    }
}

main();
