// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract ContentRegistry {
    mapping(bytes32 => uint256) public records;

    event HashRegistered(
        bytes32 indexed contentHash,
        uint256 timestamp
    );

    function registerHash(bytes32 contentHash) external {
        require(records[contentHash] == 0, "Hash already registered");
        records[contentHash] = block.timestamp;
        emit HashRegistered(contentHash, block.timestamp);
    }

    function verifyHash(bytes32 contentHash) external view returns (bool) {
        return records[contentHash] != 0;
    }
}
