import pytest
from web3 import Web3

import config
import fingerprint
import chain
import face_match

def test_canonicalization_determinism():
    data1 = {"url": "https://example.com", "title": "Test Title", "snippet": "Test Snippet"}
    data2 = {"snippet": "Test Snippet", "title": "Test Title", "url": "https://example.com"}
    assert fingerprint.canonicalize(data1) == fingerprint.canonicalize(data2)

def test_sha256_determinism():
    data = {"url": "https://example.com", "title": "Test"}
    hash1 = fingerprint.fingerprint(data)
    hash2 = fingerprint.fingerprint(data)
    assert hash1 == hash2
    assert len(hash1) == 64

def test_sha256_mutation_sensitivity():
    data1 = {"url": "https://example.com", "title": "Test"}
    data2 = {"url": "https://example.com", "title": "Test Altered"}
    assert fingerprint.fingerprint(data1) != fingerprint.fingerprint(data2)

def test_bytes32_conversion():
    sha256_hex = "16cc5df35df5339bcbcac5e8166b1a250e8fe4857cf9ca1e176263cbf4d1ca52"
    b32 = chain.hex_to_bytes32(sha256_hex)
    assert len(b32) == 32
    assert b32.hex() == sha256_hex

def test_polygon_connection():
    w3 = chain.connect_to_polygon()
    assert w3.is_connected() is True

def test_contract_address_configured():
    assert len(config.CONTRACT_ADDRESS) > 0
    assert config.CONTRACT_ADDRESS.startswith("0x")

def test_contract_abi_loading():
    w3 = chain.connect_to_polygon()
    contract = chain.load_contract(w3)
    assert contract is not None
    assert hasattr(contract.functions, "registerHash")
    assert hasattr(contract.functions, "verifyHash")

def test_on_chain_verify_hash_and_tampering():
    import time
    test_hash = fingerprint.fingerprint({"unit_test": "on_chain_registration_check", "ts": time.time()})
    # Verify before registration
    assert chain.verify_hash(test_hash) is False
    
    # Register on-chain
    tx_hash, block_num = chain.register_hash(test_hash)
    assert tx_hash.startswith("0x")
    assert block_num > 0
    
    # Verify after registration
    assert chain.verify_hash(test_hash) is True
    
    # Tampered hash check
    tampered_hash = fingerprint.fingerprint({"unit_test": "on_chain_registration_check", "ts": time.time() + 999})
    assert chain.verify_hash(tampered_hash) is False
