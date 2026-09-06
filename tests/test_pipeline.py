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
    assert chain.verify_hash(test_hash) is False
    
    tx_hash, block_num = chain.register_hash(test_hash)
    assert re.match(r"^0x[a-fA-F0-9]{64}$", tx_hash) is not None, f"Invalid tx_hash format: {tx_hash}"
    assert tx_hash != "0xRegisteredOnChain"
    assert block_num > 0
    
    assert chain.verify_hash(test_hash) is True
    
    tampered_hash = fingerprint.fingerprint({"unit_test": "on_chain_registration_check", "ts": time.time() + 999})
    assert chain.verify_hash(tampered_hash) is False

def test_url_classification():
    p1, t1 = web_search.classify_social_url("https://www.linkedin.com/posts/user_activity-12345")
    assert p1 == "LinkedIn" and t1 == "linkedin_post"

    p2, t2 = web_search.classify_social_url("https://www.instagram.com/p/C-12345/")
    assert p2 == "Instagram" and t2 == "instagram_post"

    p2b, t2b = web_search.classify_social_url("https://www.instagram.com/reel/C-98765/")
    assert p2b == "Instagram" and t2b == "instagram_post"

    p3, t3 = web_search.classify_social_url("https://x.com/user/status/987654321")
    assert p3 == "X / Twitter" and t3 == "x_post"

    p3b, t3b = web_search.classify_social_url("https://twitter.com/user/status/987654321")
    assert p3b == "X / Twitter" and t3b == "x_post"

    p4, t4 = web_search.classify_social_url("https://www.linkedin.com/in/username")
    assert t4 == "profile"

    p5, t5 = web_search.classify_social_url("https://example.com/some-page")
    assert t5 == "generic_webpage"

def test_candidate_image_download_and_face_detection(monkeypatch):
    gallery = {}
    is_match, score, count, status = web_search.verify_candidate_face("https://invalid-url-12345.com/image.jpg", gallery)
    assert is_match is False
    assert status == "UNVERIFIED — CANDIDATE IMAGE UNAVAILABLE"

def test_unrelated_linkedin_post_rejected(monkeypatch):
    enrollment = {"display_name": "Mohd Asif"}
    dummy_gallery = {}
    unrelated_candidates = [{
        "url": "https://www.linkedin.com/posts/pandearun_did-you-know-a-fax-machine",
        "title": "Unrelated Post",
        "image_url": "https://example.com/fax.jpg",
        "all_image_urls": ["https://example.com/fax.jpg"],
        "candidate_platform": "LinkedIn",
        "candidate_type": "linkedin_post"
    }]
    monkeypatch.setattr(web_search, "verify_candidate_face", lambda url, gal: (False, 0.15, 1, "REJECTED — FACE MISMATCH"))
    res = web_search.select_best_result(unrelated_candidates, enrollment, dummy_gallery)
    assert "REJECTED" in res["verification_status"] or "UNVERIFIED" in res["verification_status"]
    assert res["url"] == ""

def test_unrelated_instagram_post_rejected(monkeypatch):
    enrollment = {"display_name": "Mohd Asif"}
    dummy_gallery = {}
    candidates = [{
        "url": "https://www.instagram.com/p/Db-sY20tXy2/",
        "title": "Unrelated Instagram Reel",
        "image_url": "https://example.com/ig.jpg",
        "all_image_urls": ["https://example.com/ig.jpg"],
        "candidate_platform": "Instagram",
        "candidate_type": "instagram_post"
    }]
    monkeypatch.setattr(web_search, "verify_candidate_face", lambda url, gal: (False, 0.10, 1, "REJECTED — FACE MISMATCH"))
    res = web_search.select_best_result(candidates, enrollment, dummy_gallery)
    assert "REJECTED" in res["verification_status"] or "UNVERIFIED" in res["verification_status"]
    assert res["url"] == ""

def test_unrelated_x_post_rejected(monkeypatch):
    enrollment = {"display_name": "Mohd Asif"}
    dummy_gallery = {}
    candidates = [{
        "url": "https://x.com/someone/status/123456789",
        "title": "Unrelated X Post",
        "image_url": "https://example.com/x.jpg",
        "all_image_urls": ["https://example.com/x.jpg"],
        "candidate_platform": "X / Twitter",
        "candidate_type": "x_post"
    }]
    monkeypatch.setattr(web_search, "verify_candidate_face", lambda url, gal: (False, 0.12, 1, "REJECTED — FACE MISMATCH"))
    res = web_search.select_best_result(candidates, enrollment, dummy_gallery)
    assert "REJECTED" in res["verification_status"] or "UNVERIFIED" in res["verification_status"]
    assert res["url"] == ""

def test_own_profile_url_not_a_post_rejected():
    enrollment = {"display_name": "Mohd Asif", "own_known_profiles": ["github.com/mohdasif-v1"]}
    dummy_gallery = {}
    profile_candidates = [{
        "url": "https://github.com/mohdasif-v1",
        "title": "Mohd Asif Profile",
        "image_url": "https://github.com/mohdasif-v1.png",
        "all_image_urls": ["https://github.com/mohdasif-v1.png"],
        "candidate_platform": "GitHub",
        "candidate_type": "profile"
    }]
    res = web_search.select_best_result(profile_candidates, enrollment, dummy_gallery)
    assert "REJECTED" in res["verification_status"]
    assert res["url"] == ""

def test_generic_website_rejected_for_social_post_requirement(monkeypatch):
    enrollment = {"display_name": "Mohd Asif"}
    dummy_gallery = {}
    web_candidates = [{
        "url": "https://bazilhassan.com/",
        "title": "Bazil Hassan Portfolio",
        "image_url": "https://bazilhassan.com/me.jpg",
        "all_image_urls": ["https://bazilhassan.com/me.jpg"],
        "candidate_platform": "Web",
        "candidate_type": "generic_webpage"
    }]
    monkeypatch.setattr(web_search, "verify_candidate_face", lambda url, gal: (True, 0.98, 1, "VERIFIED SOCIAL MEDIA FACE MATCH"))
    res = web_search.select_best_result(web_candidates, enrollment, dummy_gallery)
    assert "REJECTED" in res["verification_status"]
    assert res["url"] == ""

def test_social_post_no_image_unverified():
    enrollment = {"display_name": "Mohd Asif"}
    dummy_gallery = {}
    candidates = [{
        "url": "https://www.linkedin.com/posts/mohd-asif_activity-12345",
        "title": "Mohd Asif LinkedIn Post",
        "image_url": None,
        "all_image_urls": [],
        "candidate_platform": "LinkedIn",
        "candidate_type": "linkedin_post"
    }]
    res = web_search.select_best_result(candidates, enrollment, dummy_gallery)
    assert "UNVERIFIED" in res["verification_status"]
    assert res["url"] == ""

def test_social_post_different_face_rejected(monkeypatch):
    enrollment = {"display_name": "Mohd Asif"}
    dummy_gallery = {}
    candidates = [{
        "url": "https://www.linkedin.com/posts/other_person_post",
        "title": "Other Person Post",
        "image_url": "https://example.com/other.jpg",
        "all_image_urls": ["https://example.com/other.jpg"],
        "candidate_platform": "LinkedIn",
        "candidate_type": "linkedin_post"
    }]
    monkeypatch.setattr(web_search, "verify_candidate_face", lambda url, gal: (False, 0.20, 1, "REJECTED — FACE MISMATCH"))
    res = web_search.select_best_result(candidates, enrollment, dummy_gallery)
    assert "REJECTED" in res["verification_status"]
    assert res["url"] == ""

def test_genuine_social_post_verified_face_match(monkeypatch):
    enrollment = {"display_name": "Mohd Asif"}
    dummy_gallery = {}
    valid_candidates = [{
        "url": "https://www.linkedin.com/posts/mohd-asif_building-web3-activity-9999",
        "title": "Mohd Asif - Building Web3",
        "image_url": "https://media.licdn.com/dms/image/post.jpg",
        "all_image_urls": ["https://media.licdn.com/dms/image/post.jpg"],
        "candidate_platform": "LinkedIn",
        "candidate_type": "linkedin_post"
    }]
    monkeypatch.setattr(web_search, "verify_candidate_face", lambda url, gal: (True, 0.94, 1, "VERIFIED SOCIAL MEDIA FACE MATCH"))
    res = web_search.select_best_result(valid_candidates, enrollment, dummy_gallery)
    assert res["verification_status"] == "VERIFIED SOCIAL MEDIA FACE MATCH"
    assert res["face_match_score"] == 0.94
    assert res["url"] == "https://www.linkedin.com/posts/mohd-asif_building-web3-activity-9999"

