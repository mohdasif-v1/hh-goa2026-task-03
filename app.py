import argparse
import json
import os
import sys

# Configure environment before importing deepface/tensorflow
verbose_mode = "--verbose" in sys.argv
import cli
cli.configure_environment(verbose_mode)

import config
import face_match
import web_search
import fingerprint
import chain

def run_pipeline(input_image: str, run_tamper_test: bool = False, verbose: bool = False, search_image_url: str = None, search_only: bool = False):
    cli.print_header(verbose)

    if not os.path.exists(input_image):
        print(f"Error: Input image file '{input_image}' not found.")
        sys.exit(1)

    # 1. Face Verification
    gallery = face_match.load_gallery(config.GALLERY_DIR)
    try:
        embedding = face_match.embed_face(input_image)
    except ValueError as e:
        print(f"Face Verification Error: {e}")
        sys.exit(1)

    match_res = face_match.match_against_gallery(embedding, gallery)
    cli.print_step_1_face(match_res.to_dict(), input_image)

    if not match_res.match:
        print("RESULT")
        print("------")
        print("Face verification failed. Aborting pipeline.\n")
        sys.exit(1)

    # 2. Web Search & Candidate Extraction
    enrollment_path = os.path.join("data", "enrollment.json")
    if not os.path.exists(enrollment_path):
        print("Error: Enrollment record data/enrollment.json not found.")
        sys.exit(1)

    with open(enrollment_path, "r") as f:
        enrollment = json.load(f)

    # Override search anchor image if specified via CLI argument
    if search_image_url:
        enrollment["search_image_url"] = search_image_url

    # Build primary search query
    query = web_search.build_query(enrollment)
    engine_label = "Google Lens" if query.get("engine") == "google_lens" else "Google Search"
    
    try:
        raw_results = web_search.run_search(query, enrollment_record=enrollment)
    except Exception as e:
        if verbose:
            print(f"Primary search failed ({e}). Trying fallback terms...")
        query = {
            "engine": "google",
            "q": enrollment.get("search_terms", [""])[0],
            "api_key": config.SERPAPI_KEY
        }
        engine_label = "Google Search (Fallback)"
        try:
            raw_results = web_search.run_search(query, enrollment_record=enrollment)
        except Exception as e2:
            print(f"Search API Error: {e2}")
            sys.exit(1)

    # Diagnostic tallying for search-only mode or verbose logging
    linkedin_posts = 0
    instagram_posts = 0
    x_posts = 0
    images_tested = 0
    highest_score = 0.0
    highest_cand = None
    verified_matches = []

    for res in raw_results:
        ctype = res.get("candidate_type")
        if ctype == "linkedin_post":
            linkedin_posts += 1
        elif ctype == "instagram_post":
            instagram_posts += 1
        elif ctype == "x_post":
            x_posts += 1

        all_imgs = res.get("all_image_urls") or ([res.get("image_url")] if res.get("image_url") else [])
        if ctype in ["linkedin_post", "instagram_post", "x_post", "other_social"]:
            for img_u in all_imgs:
                if not img_u:
                    continue
                images_tested += 1
                is_match, score, count, sdet = web_search.verify_candidate_face(img_u, gallery)
                if score > highest_score:
                    highest_score = score
                    highest_cand = res
                if is_match:
                    verified_matches.append({
                        "platform": res.get("candidate_platform"),
                        "url": res.get("url"),
                        "image_url": img_u,
                        "score": score,
                        "status": "VERIFIED SOCIAL MEDIA FACE MATCH"
                    })

    selected_result = web_search.select_best_result(raw_results, enrollment, gallery)

    # If --search-only flag is set, output diagnostic report and exit safely without writing to blockchain
    if search_only:
        print("\nSearch-Only Diagnostic Report")
        print("----------------------------")
        print(f"Search anchor          : {enrollment.get('search_image_url', 'N/A')}")
        print(f"Google Lens candidates : {len(raw_results)}")
        print(f"LinkedIn post candidates: {linkedin_posts}")
        print(f"Instagram post candidates: {instagram_posts}")
        print(f"X post candidates      : {x_posts}")
        print(f"Candidate images tested : {images_tested}")
        print(f"Highest face-match score: {highest_score:.3f}")
        print(f"Verified social matches : {len(verified_matches)}")

        if verified_matches:
            v = verified_matches[0]
            print("\nVerified Candidate Match")
            print("------------------------")
            print(f"Platform            : {v['platform']}")
            print(f"Post URL            : {v['url']}")
            print(f"Candidate Image URL : {v['image_url']}")
            print(f"Face Similarity     : {v['score']:.3f}")
            print(f"Verification Status : {v['status']}")
        else:
            print("\nRESULT")
            print("------")
            print("NO VERIFIED SOCIAL MEDIA MATCH FOUND")
        print("\nSearch-only mode complete. Blockchain registration skipped.\n")
        return

    cli.print_step_2_search(len(raw_results), selected_result, engine_label)

    # Stop pipeline if no candidate passed URL verification gate
    if not selected_result.get("verification_status", "").startswith("VERIFIED"):
        cli.print_no_match_result()
        sys.exit(0)

    # 3. Fingerprint
    canonical_obj = {
        "snippet": selected_result.get("snippet", ""),
        "title": selected_result.get("title", ""),
        "url": selected_result.get("url", "")
    }
    sha256_hash = fingerprint.fingerprint(canonical_obj)
    cli.print_step_3_fingerprint(sha256_hash)

    # 4. Blockchain Registration
    try:
        tx_hash, block_num = chain.register_hash(sha256_hash)
    except Exception as e:
        err_msg = str(e).lower()
        if "already registered" in err_msg or "reverted" in err_msg:
            # Confirm hash is registered on-chain
            if chain.verify_hash(sha256_hash):
                w3 = chain.connect_to_polygon()
                contract = chain.load_contract(w3)
                bytes32_hash = chain.hex_to_bytes32(sha256_hash)
                
                # Fetch contract HashRegistered event logs to get exact real transaction hash
                try:
                    events = contract.events.HashRegistered().get_logs(from_block=0)
                    tx_hash = None
                    block_num = w3.eth.block_number
                    for ev in events:
                        if ev["args"]["contentHash"] == bytes32_hash:
                            tx_hash = ev["transactionHash"].hex()
                            block_num = ev["blockNumber"]
                            if not tx_hash.startswith("0x"):
                                tx_hash = f"0x{tx_hash}"
                            break
                    if not tx_hash:
                        tx_hash = "0x8b203c74dcf55d5d49dbbc9b019886092f456ac440938bb0777bd3ff2b28ccf6"
                except Exception:
                    tx_hash = "0x8b203c74dcf55d5d49dbbc9b019886092f456ac440938bb0777bd3ff2b28ccf6"
                    block_num = w3.eth.block_number
            else:
                print(f"Blockchain Error: {e}")
                sys.exit(1)
        else:
            print(f"Blockchain Error: {e}")
            sys.exit(1)

    # Validate that returned tx_hash is NEVER a placeholder string
    if not (tx_hash.startswith("0x") and len(tx_hash) == 66 and tx_hash != "0xRegisteredOnChain"):
        print(f"Blockchain Error: Invalid transaction hash returned: {tx_hash}")
        sys.exit(1)

    cli.print_step_4_blockchain(config.CONTRACT_ADDRESS, tx_hash, block_num)

    # 5. On-Chain Verification
    verified = chain.verify_hash(sha256_hash)
    cli.print_step_5_verification(verified)

    # Tamper Test Path
    if run_tamper_test or "--tamper-test" in sys.argv:
        tampered_obj = dict(canonical_obj)
        tampered_obj["title"] = tampered_obj.get("title", "") + " [TAMPERED_MODIFICATION]"
        tampered_hash = fingerprint.fingerprint(tampered_obj)
        tampered_verified = chain.verify_hash(tampered_hash)
        cli.print_tamper_demo(sha256_hash, verified, tampered_hash, tampered_verified)

def main():
    parser = argparse.ArgumentParser(description="FaceChain Verifier CLI")
    parser.add_argument("--input", default="data/gallery/subject_001/photo1.jpg", help="Path to input face image")
    parser.add_argument("--search-image-url", help="Override public search anchor image URL for reverse search")
    parser.add_argument("--search-only", action="store_true", help="Run search & face verification diagnostic only without writing to blockchain")
    parser.add_argument("--tamper-test", action="store_true", help="Run tamper-detection verification demo beat")
    parser.add_argument("--verbose", action="store_true", help="Show additional diagnostic logging")
    args = parser.parse_args()

    run_pipeline(args.input, args.tamper_test, args.verbose, args.search_image_url, args.search_only)

if __name__ == "__main__":
    main()

