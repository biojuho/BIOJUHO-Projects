const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("AgriGuard", function () {
  let agriGuard;
  let owner, farmer, distributor, unauthorized;

  // Role hashes (must match the contract)
  const FARMER_ROLE = ethers.keccak256(ethers.toUtf8Bytes("FARMER_ROLE"));
  const DISTRIBUTOR_ROLE = ethers.keccak256(
    ethers.toUtf8Bytes("DISTRIBUTOR_ROLE")
  );
  const ADMIN_ROLE = ethers.keccak256(ethers.toUtf8Bytes("ADMIN_ROLE"));

  beforeEach(async function () {
    [owner, farmer, distributor, unauthorized] = await ethers.getSigners();
    const AgriGuard = await ethers.getContractFactory("AgriGuard");
    agriGuard = await AgriGuard.deploy();
    await agriGuard.waitForDeployment();
  });

  // ─────────────────────────────────────────────
  //  Deployment
  // ─────────────────────────────────────────────

  describe("Deployment", function () {
    it("should grant DEFAULT_ADMIN_ROLE to deployer", async function () {
      const DEFAULT_ADMIN_ROLE = await agriGuard.DEFAULT_ADMIN_ROLE();
      expect(await agriGuard.hasRole(DEFAULT_ADMIN_ROLE, owner.address)).to.be
        .true;
    });

    it("should grant ADMIN_ROLE to deployer", async function () {
      expect(await agriGuard.hasRole(ADMIN_ROLE, owner.address)).to.be.true;
    });

    it("should grant FARMER_ROLE to deployer", async function () {
      expect(await agriGuard.hasRole(FARMER_ROLE, owner.address)).to.be.true;
    });

    it("should grant DISTRIBUTOR_ROLE to deployer", async function () {
      expect(await agriGuard.hasRole(DISTRIBUTOR_ROLE, owner.address)).to.be
        .true;
    });
  });

  // ─────────────────────────────────────────────
  //  Role Management
  // ─────────────────────────────────────────────

  describe("Role Management", function () {
    it("should allow admin to add a farmer", async function () {
      await agriGuard.addFarmer(farmer.address);
      expect(await agriGuard.hasRole(FARMER_ROLE, farmer.address)).to.be.true;
    });

    it("should allow admin to add a distributor", async function () {
      await agriGuard.addDistributor(distributor.address);
      expect(await agriGuard.hasRole(DISTRIBUTOR_ROLE, distributor.address)).to
        .be.true;
    });

    it("should allow admin to remove a farmer", async function () {
      await agriGuard.addFarmer(farmer.address);
      await agriGuard.removeFarmer(farmer.address);
      expect(await agriGuard.hasRole(FARMER_ROLE, farmer.address)).to.be.false;
    });

    it("should allow admin to remove a distributor", async function () {
      await agriGuard.addDistributor(distributor.address);
      await agriGuard.removeDistributor(distributor.address);
      expect(await agriGuard.hasRole(DISTRIBUTOR_ROLE, distributor.address)).to
        .be.false;
    });

    it("should NOT allow non-admin to add a farmer", async function () {
      await expect(
        agriGuard.connect(unauthorized).addFarmer(farmer.address)
      ).to.be.reverted;
    });

    it("should NOT allow non-admin to add a distributor", async function () {
      await expect(
        agriGuard.connect(unauthorized).addDistributor(distributor.address)
      ).to.be.reverted;
    });
  });

  // ─────────────────────────────────────────────
  //  logEvent (backward compatibility)
  // ─────────────────────────────────────────────

  describe("logEvent", function () {
    it("should log an event and store the product (owner has roles)", async function () {
      await agriGuard.logEvent("PROD-001", "hash123");
      const product = await agriGuard.getProduct("PROD-001");

      expect(product.productId).to.equal("PROD-001");
      expect(product.owner).to.equal(owner.address);
      expect(product.dataHash).to.equal("hash123");
      expect(product.timestamp).to.be.gt(0);
      expect(product.handler).to.equal(owner.address);
    });

    it("should emit ProductVerified event", async function () {
      await expect(agriGuard.logEvent("PROD-002", "hash456"))
        .to.emit(agriGuard, "ProductVerified")
        .withArgs(
          "PROD-002",
          owner.address,
          "hash456",
          (timestamp) => timestamp > 0
        );
    });

    it("should emit ProductTracked event", async function () {
      await expect(agriGuard.logEvent("PROD-003", "hash789")).to.emit(
        agriGuard,
        "ProductTracked"
      );
    });

    it("should allow a farmer to logEvent", async function () {
      await agriGuard.addFarmer(farmer.address);
      await agriGuard.connect(farmer).logEvent("PROD-F01", "farmhash");
      const product = await agriGuard.getProduct("PROD-F01");
      expect(product.owner).to.equal(farmer.address);
    });

    it("should allow a distributor to logEvent", async function () {
      await agriGuard.addDistributor(distributor.address);
      await agriGuard.connect(distributor).logEvent("PROD-D01", "disthash");
      const product = await agriGuard.getProduct("PROD-D01");
      expect(product.owner).to.equal(distributor.address);
    });

    it("should reject unauthorized callers", async function () {
      await expect(
        agriGuard.connect(unauthorized).logEvent("PROD-X", "badhash")
      ).to.be.revertedWith("AgriGuard: caller lacks authorized role");
    });
  });

  // ─────────────────────────────────────────────
  //  logEventWithHandler
  // ─────────────────────────────────────────────

  describe("logEventWithHandler", function () {
    it("should log an event with a specific handler address", async function () {
      await agriGuard.logEventWithHandler(
        "PROD-H01",
        "hashH",
        distributor.address
      );
      const product = await agriGuard.getProduct("PROD-H01");

      expect(product.owner).to.equal(owner.address);
      expect(product.handler).to.equal(distributor.address);
    });

    it("should reject unauthorized callers", async function () {
      await expect(
        agriGuard
          .connect(unauthorized)
          .logEventWithHandler("PROD-H02", "hashH2", farmer.address)
      ).to.be.revertedWith("AgriGuard: caller lacks authorized role");
    });
  });

  // ─────────────────────────────────────────────
  //  batchLogEvents
  // ─────────────────────────────────────────────

  describe("batchLogEvents", function () {
    it("should log multiple products in one transaction", async function () {
      const ids = ["BATCH-01", "BATCH-02", "BATCH-03"];
      const hashes = ["h1", "h2", "h3"];

      await agriGuard.batchLogEvents(ids, hashes);

      for (let i = 0; i < ids.length; i++) {
        const product = await agriGuard.getProduct(ids[i]);
        expect(product.productId).to.equal(ids[i]);
        expect(product.dataHash).to.equal(hashes[i]);
        expect(product.owner).to.equal(owner.address);
        expect(product.handler).to.equal(owner.address);
        expect(product.timestamp).to.be.gt(0);
      }
    });

    it("should emit BatchLogged event with correct count", async function () {
      const ids = ["B1", "B2"];
      const hashes = ["bh1", "bh2"];

      await expect(agriGuard.batchLogEvents(ids, hashes))
        .to.emit(agriGuard, "BatchLogged")
        .withArgs(owner.address, 2);
    });

    it("should emit ProductVerified for each product in the batch", async function () {
      const ids = ["BV1", "BV2"];
      const hashes = ["bvh1", "bvh2"];

      const tx = agriGuard.batchLogEvents(ids, hashes);
      await expect(tx).to.emit(agriGuard, "ProductVerified");
      await expect(tx).to.emit(agriGuard, "ProductTracked");
    });

    it("should revert on array length mismatch", async function () {
      await expect(
        agriGuard.batchLogEvents(["PROD-A"], ["h1", "h2"])
      ).to.be.revertedWith("AgriGuard: array length mismatch");
    });

    it("should revert on empty batch", async function () {
      await expect(
        agriGuard.batchLogEvents([], [])
      ).to.be.revertedWith("AgriGuard: empty batch");
    });

    it("should reject unauthorized callers", async function () {
      await expect(
        agriGuard.connect(unauthorized).batchLogEvents(["X"], ["xh"])
      ).to.be.revertedWith("AgriGuard: caller lacks authorized role");
    });
  });

  // ─────────────────────────────────────────────
  //  getProduct (backward compatibility)
  // ─────────────────────────────────────────────

  describe("getProduct", function () {
    it("should return empty product for unknown ID", async function () {
      const product = await agriGuard.getProduct("NONEXISTENT");
      expect(product.productId).to.equal("");
      expect(product.timestamp).to.equal(0);
      expect(product.handler).to.equal(ethers.ZeroAddress);
    });

    it("should return the latest state after overwrite", async function () {
      await agriGuard.logEvent("OVERWRITE-01", "first_hash");
      await agriGuard.logEvent("OVERWRITE-01", "second_hash");
      const product = await agriGuard.getProduct("OVERWRITE-01");
      expect(product.dataHash).to.equal("second_hash");
    });
  });
});
