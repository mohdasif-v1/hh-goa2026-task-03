import re
import pytest
from web3 import Web3

import config
import fingerprint
import chain
import face_match
import web_search

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

def test_on_chain_verify_hash_pattern_and_tampering():
    import time
    test_hash = fingerprint.fingerprint({"unit_test": "on_chain_registration_check", "ts": time.time()})
    # Verify before registration
    assert chain.verify_hash(test_hash) is False
    
    # Register on-chain
    tx_hash, block_num = chain.register_hash(test_hash)
    assert re.match(r"^0x[a-fA-F0-9]{64}$", tx_hash) is not None, f"Invalid tx_hash format: {tx_hash}"
    assert tx_hash != "0xRegisteredOnChain"
    assert block_num > 0
    
    # Verify after registration
    assert chain.verify_hash(test_hash) is True
    
    # Tampered hash check
    tampered_hash = fingerprint.fingerprint({"unit_test": "on_chain_registration_check", "ts": time.time() + 999})
    assert chain.verify_hash(tampered_hash) is False

def test_web_content_face_verification_rules(monkeypatch):
    enrollment = {
        "display_name": "Mohd Asif",
        "own_known_profiles": ["github.com/mohdasif-v1"]
    }
    dummy_gallery = {"subject_001": []}

    # 1. Unrelated LinkedIn result without matching face -> REJECTED / UNVERIFIED
    unrelated_candidates = [{
        "url": "https://www.linkedin.com/posts/pandearun_did-you-know-a-fax-machine",
        "title": "Did you know a fax machine",
        "snippet": "LinkedIn post",
        "image_url": "https://example.com/unrelated.jpg"
    }]
    monkeypatch.setattr(web_search, "verify_candidate_face", lambda url, gal: (False, 0.15))
    res_unrelated = web_search.select_best_result(unrelated_candidates, enrollment, dummy_gallery)
    assert res_unrelated["verification_status"].startswith("REJECTED") or res_unrelated["verification_status"].startswith("UNVERIFIED")
    assert res_unrelated["url"] == ""

    # 2. Own profile URL but no candidate face/image -> UNVERIFIED
    no_img_candidates = [{
        "url": "https://github.com/mohdasif-v1/content-platform",
        "title": "mohdasif-v1/content-platform",
        "snippet": "Project repo",
        "image_url": None
    }]
    res_no_img = web_search.select_best_result(no_img_candidates, enrollment, dummy_gallery)
    assert "UNVERIFIED" in res_no_img["verification_status"]
    assert res_no_img["ownership_match"] is True
    assert res_no_img["url"] == ""

    # 3. Candidate with verified matching face -> VERIFIED
    valid_candidates = [{
        "url": "https://github.com/mohdasif-v1/content-platform",
        "title": "mohdasif-v1/content-platform",
        "snippet": "Mohd Asif GitHub project",
        "image_url": "https://github.com/mohdasif-v1.png"
    }]
    monkeypatch.setattr(web_search, "verify_candidate_face", lambda url, gal: (True, 0.95))
    res_valid = web_search.select_best_result(valid_candidates, enrollment, dummy_gallery)
    assert res_valid["verification_status"].startswith("VERIFIED")
    assert res_valid["face_match_score"] == 0.95
    assert res_valid["ownership_match"] is True
    assert res_valid["url"] == "https://github.com/mohdasif-v1/content-platform"

    # 4. Unrelated candidate on an owned profile without face match -> REJECTED
    monkeypatch.setattr(web_search, "verify_candidate_face", lambda url, gal: (False, 0.10))
    res_owned_unrelated = web_search.select_best_result(valid_candidates, enrollment, dummy_gallery)
    assert res_owned_unrelated["verification_status"].startswith("REJECTED")
    assert res_owned_unrelated["url"] == ""
