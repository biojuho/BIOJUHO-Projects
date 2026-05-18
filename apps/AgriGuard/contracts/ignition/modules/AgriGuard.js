import { buildModule } from "@nomicfoundation/hardhat-ignition/modules";

export default buildModule("AgriGuardModule", (m) => {
  const agriGuard = m.contract("AgriGuard");

  return { agriGuard };
});
