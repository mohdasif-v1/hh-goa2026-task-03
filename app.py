import argparse
import json
import os
import sys

import config
import face_match
import web_search
import fingerprint
import chain
import cli

def run_pipeline(input_image: str, run_tamper_test: bool = False):
    cli.console.print("\n[bold magenta]==================================================[/bold magenta]")
    cli.console.print("[bold magenta] HH GOA 2026 — FACE + WEB + BLOCKCHAIN VERIFIER  [/bold magenta]")
    cli.console.print("[bold magenta]==================================================[/bold magenta]")

    if not os.path.exists(input_image):
        cli.console.print(f"[bold red]Error: Input image file '{input_image}' not found.[/bold red]")
        sys.exit(1)

    # 1. Face Verification
    gallery = face_match.load_gallery(config.GALLERY_DIR)
    try:
        embedding = face_match.embed_face(input_image)
    except ValueError as e:
        cli.console.print(f"[bold red]Face Detection Error: {e}[/bold red]")
        sys.exit(1)

    match_res = face_match.match_against_gallery(embedding, gallery)
    cli.render_step_1_face(match_res.to_dict(), input_image)

    if not match_res.match:
        cli.console.print("[bold red]No confident gallery match found. Aborting pipeline.[/bold red]")
        sys.exit(1)

    # 2. Web Search
    enrollment_path = os.path.join("data", "enrollment.json")
    if not os.path.exists(enrollment_path):
        cli.console.print("[bold red]Enrollment record data/enrollment.json not found.[/bold red]")
        sys.exit(1)

    with open(enrollment_path, "r") as f:
        enrollment = json.load(f)

    query = web_search.build_query(enrollment)
    try:
        raw_results = web_search.run_search(query)
    except Exception as e:
        cli.console.print(f"[yellow]Primary search engine error ({e}). Trying fallback search terms...[/yellow]")
        query = {
            "engine": "google",
            "q": enrollment.get("search_terms", [""])[0],
            "api_key": config.SERPAPI_KEY
        }
        raw_results = web_search.run_search(query)

    try:
        selected_result = web_search.select_best_result(raw_results, enrollment)
    except ValueError as e:
        cli.console.print(f"[bold red]Web Search Error: {e}[/bold red]")
        sys.exit(1)

    cli.render_step_2_search(selected_result, query.get("engine", "web_search"))

    # 3. Fingerprint
    canonical_obj = {
        "snippet": selected_result.get("snippet", ""),
        "title": selected_result.get("title", ""),
        "url": selected_result.get("url", "")
    }
    sha256_hash = fingerprint.fingerprint(canonical_obj)
    cli.render_step_3_fingerprint(sha256_hash)

    # 4. Blockchain Registration
    try:
        tx_hash, block_num = chain.register_hash(sha256_hash)
    except Exception as e:
        if "already registered" in str(e).lower():
            cli.console.print(f"  [yellow]Notice: Hash {sha256_hash[:10]}... already registered on-chain.[/yellow]")
            # Fetch existing block or tx if needed, or query verifyHash directly
            w3 = chain.connect_to_polygon()
            contract = chain.load_contract(w3)
            bytes32_hash = chain.hex_to_bytes32(sha256_hash)
            verified = contract.functions.verifyHash(bytes32_hash).call()
            tx_hash = "0xAlreadyRegisteredOnChain"
            block_num = w3.eth.block_number
        else:
            cli.console.print(f"[bold red]Blockchain Error: {e}[/bold red]")
            sys.exit(1)

    cli.render_step_4_blockchain(config.CONTRACT_ADDRESS, tx_hash, block_num)

    # 5. On-Chain Verification
    verified = chain.verify_hash(sha256_hash)
    cli.render_step_5_verification(verified)

    # Tamper Test Path
    if run_tamper_test or "--tamper-test" in sys.argv:
        tampered_obj = dict(canonical_obj)
        tampered_obj["title"] = tampered_obj.get("title", "") + " [TAMPERED_MODIFICATION]"
        tampered_hash = fingerprint.fingerprint(tampered_obj)
        tampered_verified = chain.verify_hash(tampered_hash)
        cli.render_tamper_demo(sha256_hash, verified, tampered_hash, tampered_verified)

def main():
    parser = argparse.ArgumentParser(description="HH Goa 2026 Face -> Web -> Blockchain Pipeline")
    parser.add_argument("--input", default="data/gallery/subject_001/photo1.jpg", help="Path to input face image")
    parser.add_argument("--tamper-test", action="store_true", help="Run tamper-detection verification demo beat")
    args = parser.parse_args()

    run_pipeline(args.input, args.tamper_test)

if __name__ == "__main__":
    main()
