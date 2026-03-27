// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/AccessControl.sol";

/// @title AgriGuard - Agricultural Supply Chain Tracking
/// @author AgriGuard Team
/// @notice Tracks agricultural products through the supply chain with role-based access control
/// @dev Uses OpenZeppelin AccessControl for FARMER, DISTRIBUTOR, and ADMIN roles
contract AgriGuard is AccessControl {
    // ──────────────────────────────────────────────
    //  Roles
    // ──────────────────────────────────────────────

    /// @notice Role identifier for farmers who originate products
    bytes32 public constant FARMER_ROLE = keccak256("FARMER_ROLE");

    /// @notice Role identifier for distributors who handle products in transit
    bytes32 public constant DISTRIBUTOR_ROLE = keccak256("DISTRIBUTOR_ROLE");

    /// @notice Role identifier for administrators
    bytes32 public constant ADMIN_ROLE = keccak256("ADMIN_ROLE");

    // ──────────────────────────────────────────────
    //  Data Structures
    // ──────────────────────────────────────────────

    /// @notice Represents a tracked agricultural product
    /// @param productId Unique string identifier for the product
    /// @param owner Address that last logged this product
    /// @param dataHash SHA-256 hash of the product event data
    /// @param timestamp Block timestamp when the product was last logged
    /// @param handler Address of the current supply-chain handler
    struct Product {
        string productId;
        address owner;
        string dataHash;
        uint256 timestamp;
        address handler;
    }

    // ──────────────────────────────────────────────
    //  State
    // ──────────────────────────────────────────────

    /// @notice Mapping from product ID string to its Product record
    mapping(string => Product) public products;

    // ──────────────────────────────────────────────
    //  Events
    // ──────────────────────────────────────────────

    /// @notice Emitted when a product is verified/logged (legacy event, kept for backward compatibility)
    /// @param productId The unique product identifier
    /// @param owner The address that submitted the event
    /// @param dataHash Hash of the event payload
    /// @param timestamp Block timestamp of the event
    event ProductVerified(
        string productId,
        address owner,
        string dataHash,
        uint256 timestamp
    );

    /// @notice Emitted when a product is tracked through the supply chain
    /// @param productId The unique product identifier (indexed for efficient filtering)
    /// @param owner The address that submitted the event (indexed for efficient filtering)
    /// @param handler The current handler in the supply chain
    /// @param dataHash Hash of the event payload
    /// @param timestamp Block timestamp of the event
    event ProductTracked(
        string indexed productId,
        address indexed owner,
        address handler,
        string dataHash,
        uint256 timestamp
    );

    /// @notice Emitted when a batch of products is logged in a single transaction
    /// @param caller The address that submitted the batch
    /// @param count Number of products in the batch
    event BatchLogged(address indexed caller, uint256 count);

    // ──────────────────────────────────────────────
    //  Constructor
    // ──────────────────────────────────────────────

    /// @notice Initializes the contract and grants all roles to the deployer
    /// @dev The deployer receives DEFAULT_ADMIN_ROLE, ADMIN_ROLE, FARMER_ROLE, and DISTRIBUTOR_ROLE
    constructor() {
        _grantRole(DEFAULT_ADMIN_ROLE, msg.sender);
        _grantRole(ADMIN_ROLE, msg.sender);
        _grantRole(FARMER_ROLE, msg.sender);
        _grantRole(DISTRIBUTOR_ROLE, msg.sender);
    }

    // ──────────────────────────────────────────────
    //  External / Public Functions
    // ──────────────────────────────────────────────

    /// @notice Log a supply-chain event for a product (backward-compatible signature)
    /// @dev Any authorized role (FARMER, DISTRIBUTOR, or ADMIN) can call this.
    ///      The handler is set to msg.sender for backward compatibility.
    /// @param _productId Unique identifier of the product
    /// @param _dataHash Hash of the event data payload
    function logEvent(
        string memory _productId,
        string memory _dataHash
    ) public onlyAuthorized {
        _logProduct(_productId, _dataHash, msg.sender);
    }

    /// @notice Log a supply-chain event with an explicit handler address
    /// @dev Allows specifying a different handler than the caller (e.g., admin logging on behalf of a distributor)
    /// @param _productId Unique identifier of the product
    /// @param _dataHash Hash of the event data payload
    /// @param _handler Address of the current handler in the supply chain
    function logEventWithHandler(
        string memory _productId,
        string memory _dataHash,
        address _handler
    ) public onlyAuthorized {
        _logProduct(_productId, _dataHash, _handler);
    }

    /// @notice Log multiple supply-chain events in a single transaction
    /// @dev Saves gas when recording multiple products. Arrays must be equal length.
    /// @param _productIds Array of product identifiers
    /// @param _dataHashes Array of data hashes corresponding to each product
    function batchLogEvents(
        string[] memory _productIds,
        string[] memory _dataHashes
    ) public onlyAuthorized {
        require(
            _productIds.length == _dataHashes.length,
            "AgriGuard: array length mismatch"
        );
        require(_productIds.length > 0, "AgriGuard: empty batch");

        for (uint256 i = 0; i < _productIds.length; i++) {
            _logProduct(_productIds[i], _dataHashes[i], msg.sender);
        }

        emit BatchLogged(msg.sender, _productIds.length);
    }

    /// @notice Retrieve the stored product record (backward-compatible signature)
    /// @param _productId The unique product identifier to look up
    /// @return The Product struct for the given ID
    function getProduct(
        string memory _productId
    ) public view returns (Product memory) {
        return products[_productId];
    }

    // ──────────────────────────────────────────────
    //  Admin Functions
    // ──────────────────────────────────────────────

    /// @notice Grant the FARMER_ROLE to an address
    /// @dev Only callable by an account with ADMIN_ROLE
    /// @param account The address to grant the farmer role to
    function addFarmer(address account) external onlyRole(ADMIN_ROLE) {
        grantRole(FARMER_ROLE, account);
    }

    /// @notice Grant the DISTRIBUTOR_ROLE to an address
    /// @dev Only callable by an account with ADMIN_ROLE
    /// @param account The address to grant the distributor role to
    function addDistributor(address account) external onlyRole(ADMIN_ROLE) {
        grantRole(DISTRIBUTOR_ROLE, account);
    }

    /// @notice Revoke the FARMER_ROLE from an address
    /// @dev Only callable by an account with ADMIN_ROLE
    /// @param account The address to revoke the farmer role from
    function removeFarmer(address account) external onlyRole(ADMIN_ROLE) {
        revokeRole(FARMER_ROLE, account);
    }

    /// @notice Revoke the DISTRIBUTOR_ROLE from an address
    /// @dev Only callable by an account with ADMIN_ROLE
    /// @param account The address to revoke the distributor role from
    function removeDistributor(address account) external onlyRole(ADMIN_ROLE) {
        revokeRole(DISTRIBUTOR_ROLE, account);
    }

    // ──────────────────────────────────────────────
    //  Internal Functions
    // ──────────────────────────────────────────────

    /// @notice Internal function that stores a product record and emits events
    /// @param _productId Unique identifier of the product
    /// @param _dataHash Hash of the event data payload
    /// @param _handler Address of the current supply-chain handler
    function _logProduct(
        string memory _productId,
        string memory _dataHash,
        address _handler
    ) internal {
        products[_productId] = Product({
            productId: _productId,
            owner: msg.sender,
            dataHash: _dataHash,
            timestamp: block.timestamp,
            handler: _handler
        });

        // Legacy event (backward compatibility)
        emit ProductVerified(
            _productId,
            msg.sender,
            _dataHash,
            block.timestamp
        );

        // New indexed event
        emit ProductTracked(
            _productId,
            msg.sender,
            _handler,
            _dataHash,
            block.timestamp
        );
    }

    // ──────────────────────────────────────────────
    //  Modifiers
    // ──────────────────────────────────────────────

    /// @notice Restricts access to accounts with FARMER_ROLE, DISTRIBUTOR_ROLE, or ADMIN_ROLE
    modifier onlyAuthorized() {
        require(
            hasRole(FARMER_ROLE, msg.sender) ||
                hasRole(DISTRIBUTOR_ROLE, msg.sender) ||
                hasRole(ADMIN_ROLE, msg.sender),
            "AgriGuard: caller lacks authorized role"
        );
        _;
    }
}
