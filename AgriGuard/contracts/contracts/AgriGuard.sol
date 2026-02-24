// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract AgriGuard {
    struct Product {
        string productId;
        address owner;
        string dataHash;
        uint256 timestamp;
    }

    mapping(string => Product) public products;

    event ProductVerified(string productId, address owner, string dataHash, uint256 timestamp);

    function logEvent(string memory _productId, string memory _dataHash) public {
        products[_productId] = Product({
            productId: _productId,
            owner: msg.sender,
            dataHash: _dataHash,
            timestamp: block.timestamp
        });
        
        emit ProductVerified(_productId, msg.sender, _dataHash, block.timestamp);
    }
    
    function getProduct(string memory _productId) public view returns (Product memory) {
        return products[_productId];
    }
}
