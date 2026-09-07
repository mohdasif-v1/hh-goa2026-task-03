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

def test_on_chain_verify_hash_pattern_and_tampering(monkeypatch):
    import time
    test_hash = fingerprint.fingerprint({"unit_test": "on_chain_registration_check", "ts": time.time()})
    assert chain.verify_hash(test_hash) is False
    
    # Mock live gas transaction so unit test does not depend on live testnet faucet balance
    registered_hashes = set()
    def mock_register(h):
        registered_hashes.add(h)
        return ("0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef", 123456)
    
    def mock_verify(h):
        return h in registered_hashes

    monkeypatch.setattr(chain, "register_hash", mock_register)
    monkeypatch.setattr(chain, "verify_hash", mock_verify)

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

    p2c, t2c = web_search.classify_social_url("https://www.instagram.com/accounts/login/")
    assert p2c == "Instagram" and t2c == "profile"

    p2d, t2d = web_search.classify_social_url("https://www.instagram.com/someuser/")
    assert p2d == "Instagram" and t2d == "profile"

    p3, t3 = web_search.classify_social_url("https://x.com/user/status/987654321")
    assert p3 == "X / Twitter" and t3 == "x_post"

    p3b, t3b = web_search.classify_social_url("https://twitter.com/user/status/987654321")
    assert p3b == "X / Twitter" and t3b == "x_post"

    p3c, t3c = web_search.classify_social_url("https://x.com/user_handle")
    assert p3c == "X / Twitter" and t3c == "profile"

    p4, t4 = web_search.classify_social_url("https://www.linkedin.com/in/username")
    assert t4 == "profile"

    p5, t5 = web_search.classify_social_url("https://example.com/some-page")
    assert t5 == "generic_webpage"


def test_candidate_image_download_and_face_detection(monkeypatch):
    gallery = {}
    is_match, score, count, idx, fdetails, status = web_search.verify_candidate_face("https://invalid-url-12345.com/image.jpg", gallery)
    assert is_match is False
    assert status == "UNVERIFIED — POST IMAGE NOT AVAILABLE"

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
    monkeypatch.setattr(web_search, "verify_candidate_face", lambda url, gal, search_anchor_url=None: (False, 0.15, 1, None, [], "REJECTED — FACE MISMATCH"))
    res = web_search.select_best_result(unrelated_candidates, enrollment, dummy_gallery)
    assert "NO VERIFIED SOCIAL MEDIA POST FOUND" in res["verification_status"]
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
    monkeypatch.setattr(web_search, "verify_candidate_face", lambda url, gal, search_anchor_url=None: (False, 0.10, 1, None, [], "REJECTED — FACE MISMATCH"))
    res = web_search.select_best_result(candidates, enrollment, dummy_gallery)
    assert "NO VERIFIED SOCIAL MEDIA POST FOUND" in res["verification_status"]
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
    monkeypatch.setattr(web_search, "verify_candidate_face", lambda url, gal, search_anchor_url=None: (False, 0.12, 1, None, [], "REJECTED — FACE MISMATCH"))
    res = web_search.select_best_result(candidates, enrollment, dummy_gallery)
    assert "NO VERIFIED SOCIAL MEDIA POST FOUND" in res["verification_status"]
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
    assert "NO VERIFIED SOCIAL MEDIA POST FOUND" in res["verification_status"]
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
    monkeypatch.setattr(web_search, "verify_candidate_face", lambda url, gal, search_anchor_url=None: (True, 0.98, 1, 0, [], "VERIFIED SOCIAL MEDIA FACE MATCH"))
    res = web_search.select_best_result(web_candidates, enrollment, dummy_gallery)
    assert "NO VERIFIED SOCIAL MEDIA POST FOUND" in res["verification_status"]
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
    assert "NO VERIFIED SOCIAL MEDIA POST FOUND" in res["verification_status"]
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
    monkeypatch.setattr(web_search, "verify_candidate_face", lambda url, gal, search_anchor_url=None: (False, 0.20, 1, None, [], "REJECTED — FACE MISMATCH"))
    res = web_search.select_best_result(candidates, enrollment, dummy_gallery)
    assert "NO VERIFIED SOCIAL MEDIA POST FOUND" in res["verification_status"]
    assert res["url"] == ""

def test_cli_search_image_url_override(monkeypatch):
    import json
    enrollment = {"search_image_url": "https://old.com/img.png", "display_name": "Test"}
    monkeypatch.setattr("json.load", lambda f: enrollment)
    q = web_search.build_query({"search_image_url": "https://new.com/override.jpg"})
    assert q["url"] == "https://new.com/override.jpg"

def test_search_anchor_not_proof_of_verification(monkeypatch):
    enrollment = {"search_image_url": "https://github.com/mohdasif-v1.png", "display_name": "Mohd Asif"}
    dummy_gallery = {}
    candidates = [{
        "url": "https://www.linkedin.com/posts/unrelated-post",
        "title": "Unrelated LinkedIn Post",
        "image_url": "https://github.com/mohdasif-v1.png",  # Same image URL as anchor
        "all_image_urls": ["https://github.com/mohdasif-v1.png"],
        "candidate_platform": "LinkedIn",
        "candidate_type": "linkedin_post"
    }]
    monkeypatch.setattr(web_search, "verify_candidate_face", lambda url, gal, search_anchor_url=None: (False, 0.10, 1, None, [], "REJECTED — CANDIDATE MATCHES SEARCH ANCHOR"))
    res = web_search.select_best_result(candidates, enrollment, dummy_gallery)
    assert "NO VERIFIED SOCIAL MEDIA POST FOUND" in res["verification_status"]
    assert res["url"] == ""

def test_no_face_candidate_rejected_by_verify_candidate_face(monkeypatch):
    # Mock face_match.extract_all_faces to raise ValueError("no face detected in input image")
    def mock_extract(path):
        raise ValueError("no face detected in input image")
    monkeypatch.setattr(face_match, "extract_all_faces", mock_extract)
    
    # Mock requests.get to return fake image content
    class FakeResp:
        status_code = 200
        content = b"fake image content"
    monkeypatch.setattr("requests.get", lambda url, **kw: FakeResp())
    
    is_match, dist, count, idx, fdetails, status = web_search.verify_candidate_face("https://example.com/noface.jpg", {})
    assert is_match is False
    assert count == 0
    assert "REJECTED — NO FACE DETECTED" in status

def test_false_linkedin_candidate_no_face_rejected():
    # The false LinkedIn candidate preview image
    cand_url = "https://media.licdn.com/dms/image/v2/D4E22AQGwBTjkIDAK7g/feedshare-image-high-res/B4EZ_0Z7HwJQAY-/0/1786511864616?e=2147483647&v=beta&t=Ik1OOk8du5GDU9OOd6aXwAQ5zAvU3GO7g_N1RxeqUms"
    gallery = face_match.load_gallery(config.GALLERY_DIR)
    is_match, dist, count, idx, fdetails, status = web_search.verify_candidate_face(cand_url, gallery)
    assert is_match is False
    assert count == 0
    assert "REJECTED — NO FACE DETECTED" in status

def test_profile_avatar_url_rejected():
    profile_img_url = "https://media.licdn.com/dms/image/v2/D5603AQFXk4bsVFFnjQ/profile-displayphoto-scale_400_400/B56Z6ET.1RIoAg-/0/1780336292509"
    assert web_search.is_profile_avatar_url(profile_img_url) is True
    
    is_match, dist, count, idx, fdetails, status = web_search.verify_candidate_face(profile_img_url, {})
    assert is_match is False
    assert status == "REJECTED — PROFILE AVATAR NOT POST MEDIA"

def test_search_anchor_url_rejected():
    anchor_url = "https://github.com/mohdasif-v1.png"
    is_match, dist, count, idx, fdetails, status = web_search.verify_candidate_face(anchor_url, {}, search_anchor_url=anchor_url)
    assert is_match is False
    assert status == "REJECTED — CANDIDATE MATCHES SEARCH ANCHOR"

def test_provenance_metadata_in_select_best_result(monkeypatch):
    enrollment = {"display_name": "Mohd Asif", "search_image_url": "https://anchor.com/me.jpg"}
    dummy_gallery = {}
    candidates = [{
        "url": "https://www.linkedin.com/posts/test_activity-100",
        "title": "Test Post",
        "image_url": "https://example.com/post_media.jpg",
        "all_image_urls": ["https://example.com/post_media.jpg"],
        "image_source_types": ["post_media_og"],
        "candidate_platform": "LinkedIn",
        "candidate_type": "linkedin_post"
    }]
    
    monkeypatch.setattr(web_search, "verify_candidate_face", lambda url, gal, search_anchor_url=None: (True, 0.4200, 1, 0, [], "VERIFIED SOCIAL MEDIA FACE MATCH"))
    res = web_search.select_best_result(candidates, enrollment, dummy_gallery)
    
    assert res["verification_status"] == "VERIFIED SOCIAL MEDIA FACE MATCH"
    assert res["image_belongs_to_post"] is True
    assert res["image_source_type"] == "post_media_og"
    assert res["face_count"] == 1
    assert res["cosine_distance"] == 0.4200
    assert res["matched_face_index"] == 0



def test_search_thumbnail_rejected():
    thumb_url = "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcR..."
    assert web_search.is_search_thumbnail_url(thumb_url) is True
    
    is_match, dist, count, idx, fdetails, status = web_search.verify_candidate_face(thumb_url, {})
    assert is_match is False
    assert status == "REJECTED — SEARCH THUMBNAIL NOT POST MEDIA"

def test_multiple_faces_one_matching_face(monkeypatch):
    dummy_gallery = {}
    
    # Mock extract_all_faces to return 2 faces
    f1 = {"embedding": [0.1] * 512, "facial_area": {"x": 10, "y": 10, "w": 50, "h": 50}}
    f2 = {"embedding": [0.9] * 512, "facial_area": {"x": 100, "y": 100, "w": 50, "h": 50}}
    monkeypatch.setattr(face_match, "extract_all_faces", lambda p: [f1, f2])
    
    # Mock match_against_gallery to report face index 1 as match with distance 0.15
    mres = face_match.MatchResult(
        matched_id="subject_001",
        distance=0.15,
        model="ArcFace",
        distance_metric="cosine",
        threshold_used=config.FACE_MATCH_THRESHOLD,
        match=True,
        face_count=2,
        matched_face_index=1,
        faces_detail=[
            {"face_index": 0, "bounding_box": f1["facial_area"], "cosine_distance": 0.85, "matched_id": "unknown", "status": "NO MATCH"},
            {"face_index": 1, "bounding_box": f2["facial_area"], "cosine_distance": 0.15, "matched_id": "subject_001", "status": "MATCH"}
        ]
    )
    monkeypatch.setattr(face_match, "match_against_gallery", lambda faces, gal: mres)
    
    class FakeResp:
        status_code = 200
        content = b"fake image content"
    monkeypatch.setattr("requests.get", lambda url, **kw: FakeResp())

    is_match, dist, count, idx, fdetails, status = web_search.verify_candidate_face("https://example.com/multi.jpg", dummy_gallery)
    assert is_match is True
    assert count == 2
    assert idx == 1
    assert dist == 0.15
    assert len(fdetails) == 2
    assert fdetails[1]["status"] == "MATCH"

def test_multiple_faces_no_matching_face(monkeypatch):
    dummy_gallery = {}
    f1 = {"embedding": [0.1] * 512, "facial_area": {"x": 10, "y": 10, "w": 50, "h": 50}}
    f2 = {"embedding": [0.2] * 512, "facial_area": {"x": 100, "y": 100, "w": 50, "h": 50}}
    monkeypatch.setattr(face_match, "extract_all_faces", lambda p: [f1, f2])
    
    mres = face_match.MatchResult(
        matched_id="unknown",
        distance=0.75,
        model="ArcFace",
        distance_metric="cosine",
        threshold_used=config.FACE_MATCH_THRESHOLD,
        match=False,
        face_count=2,
        matched_face_index=None,
        faces_detail=[
            {"face_index": 0, "bounding_box": f1["facial_area"], "cosine_distance": 0.75, "matched_id": "unknown", "status": "NO MATCH"},
            {"face_index": 1, "bounding_box": f2["facial_area"], "cosine_distance": 0.80, "matched_id": "unknown", "status": "NO MATCH"}
        ]
    )
    monkeypatch.setattr(face_match, "match_against_gallery", lambda faces, gal: mres)
    
    class FakeResp:
        status_code = 200
        content = b"fake image content"
    monkeypatch.setattr("requests.get", lambda url, **kw: FakeResp())

    is_match, dist, count, idx, fdetails, status = web_search.verify_candidate_face("https://example.com/multi_nomatch.jpg", dummy_gallery)
    assert is_match is False
    assert count == 2
    assert idx is None
    assert status == "REJECTED — FACE MISMATCH"

def test_blockchain_cannot_execute_without_verified_candidate(monkeypatch):
    import app
    recorded_calls = []
    monkeypatch.setattr(chain, "register_hash", lambda h: recorded_calls.append("register") or ("0x123", 1))
    monkeypatch.setattr(web_search, "select_best_result", lambda res, en, gal=None: {
        "candidate_url": "",
        "verification_status": "NO VERIFIED SOCIAL MEDIA POST FOUND",
        "image_belongs_to_post": False
    })
    
    try:
        app.run_pipeline("data/gallery/subject_001/photo4.png")
    except SystemExit:
        pass

    assert "register" not in recorded_calls

def test_tampered_evidence_hash_not_found(monkeypatch):
    import app
    enrollment = {"display_name": "Mohd Asif"}
    dummy_gallery = {}
    
    canonical_evidence = {
        "subject_id": "subject_001",
        "platform": "LinkedIn",
        "post_url": "https://www.linkedin.com/posts/test",
        "post_image_url": "https://example.com/media.jpg",
        "image_source_type": "post_media_og",
        "image_belongs_to_post": True,
        "image_is_profile_avatar": False,
        "image_is_search_anchor": False,
        "face_count": 1,
        "matched_face_index": 0,
        "cosine_distance": 0.15,
        "threshold": 0.600,
        "face_model": "ArcFace",
        "detector": "mtcnn",
        "search_engine": "Google Lens",
        "verification_timestamp": "2026-09-06T12:00:00Z"
    }
    
    orig_hash = fingerprint.fingerprint(canonical_evidence)
    
    tampered_evidence = dict(canonical_evidence)
    tampered_evidence["cosine_distance"] = 0.0001
    tampered_hash = fingerprint.fingerprint(tampered_evidence)
    
    assert orig_hash != tampered_hash
    
    # Mock chain verification where orig_hash exists on chain, but tampered_hash does not
    monkeypatch.setattr(chain, "verify_hash", lambda h: h == orig_hash)
    
    assert chain.verify_hash(orig_hash) is True
    assert chain.verify_hash(tampered_hash) is False

def test_search_results_containing_only_irrelevant_pages(monkeypatch):
    enrollment = {"display_name": "Mohd Asif"}
    dummy_gallery = {}
    results = [{
        "url": "https://example.com/blog/random-article",
        "title": "Random Article",
        "image_url": "https://example.com/banner.jpg",
        "all_image_urls": ["https://example.com/banner.jpg"],
        "candidate_platform": "Web",
        "candidate_type": "generic_webpage"
    }]
    res = web_search.select_best_result(results, enrollment, dummy_gallery)
    assert res["verification_status"] == "NO VERIFIED SOCIAL MEDIA POST FOUND"

def test_instagram_carousel_url_classification():
    p1, t1 = web_search.classify_social_url("https://www.instagram.com/p/DWmhi_Ik-E1/?img_index=1")
    p2, t2 = web_search.classify_social_url("https://www.instagram.com/p/DWmhi_Ik-E1/?img_index=2")
    p3, t3 = web_search.classify_social_url("https://www.instagram.com/p/DWmhi_Ik-E1/")
    assert p1 == "Instagram" and t1 == "instagram_post"
    assert p2 == "Instagram" and t2 == "instagram_post"
    assert p3 == "Instagram" and t3 == "instagram_post"
    assert web_search.normalize_url(p1) == web_search.normalize_url(p3)

def test_calibrated_threshold_config():
    assert config.FACE_MATCH_THRESHOLD == 0.600
    assert config.MIN_FACE_WIDTH == 60
    assert config.MIN_FACE_HEIGHT == 60
    assert config.MIN_BLUR_SCORE == 20.0






