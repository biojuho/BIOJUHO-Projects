const { buildModule } = require("@nomicfoundation/hardhat-ignition/modules");

module.exports = buildModule("AgriGuardModule", (m) => {
  const agriGuard = m.contract("AgriGuard");

  return { agriGuard };
});
