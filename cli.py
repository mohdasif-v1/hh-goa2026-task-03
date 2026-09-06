import os
import sys

def configure_environment(verbose: bool = False):
    """Configures environment variables to suppress TensorFlow/absl/CUDA C++ logging startup noise."""
    os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
    os.environ["ABSL_LOG_LEVEL"] = "error"
    os.environ["AUTOGRAPH_VERBOSITY"] = "0"
    
    if not verbose:
        import warnings
        warnings.filterwarnings("ignore")

def print_header(verbose: bool = False):
    print("\nFaceChain Verifier")
    print("------------------\n")

def print_step_1_face(match_result: dict, image_path: str):
    print("[1/5] Face verification")
    print(f"      Input       : {image_path}")
    if match_result.get("match"):
        print("      Face        : Detected")
        print(f"      Subject     : {match_result.get('matched_id')}")
        print(f"      Similarity  : {match_result.get('confidence'):.3f}")
        print(f"      Threshold   : {match_result.get('threshold_used'):.3f}")
        print("      Status      : MATCH\n")
    else:
        print("      Face        : Not Detected or Low Similarity")
        print(f"      Similarity  : {match_result.get('confidence'):.3f}")
        print(f"      Threshold   : {match_result.get('threshold_used'):.3f}")
        print("      Status      : NO MATCH\n")

def print_step_2_search(candidate_count: int, selected_result: dict, engine_name: str):
    print("[2/5] Web search")
    print(f"      Engine      : {engine_name}")
    print(f"      Candidates  : {candidate_count}\n")
    
    if selected_result.get("verification_status") == "VERIFIED":
        print("      Candidate 1")
        print(f"      Platform    : {selected_result.get('platform', 'Web')}")
        print(f"      Title       : {selected_result.get('title')}")
        print(f"      URL         : {selected_result.get('url')}")
        print(f"      Status      : VERIFIED MATCH ({selected_result.get('verification_reason')})\n")
    else:
        print(f"      Status      : NO VERIFIED MATCH ({selected_result.get('verification_reason')})\n")

def print_no_match_result():
    print("RESULT")
    print("------")
    print("No verified social-media match was found.")
    print("Blockchain registration skipped.\n")

def print_step_3_fingerprint(sha256_hash: str):
    print("[3/5] Evidence fingerprint")
    print("      Algorithm   : SHA-256")
    print(f"      Fingerprint : {sha256_hash}\n")

def print_step_4_blockchain(contract_address: str, tx_hash: str, block_number: int):
    print("[4/5] Blockchain registration")
    print(f"      Network     : Polygon Amoy")
    print("      Chain ID    : 80002")
    print(f"      Contract    : {contract_address}")
    print(f"      Transaction : {tx_hash}")
    print(f"      Explorer    : https://amoy.polygonscan.com/tx/{tx_hash}")
    print(f"      Block       : #{block_number}")
    print("      Status      : CONFIRMED\n")

def print_step_5_verification(is_verified: bool):
    print("[5/5] Verification")
    if is_verified:
        print("      On-chain    : VERIFIED\n")
        print("RESULT")
        print("------")
        print("CONTENT VERIFIED\n")
        print("Fingerprint matches the on-chain record.\n")
    else:
        print("      On-chain    : NOT VERIFIED\n")
        print("RESULT")
        print("------")
        print("VERIFICATION FAILED\n")

def print_tamper_demo(original_hash: str, original_verified: bool, tampered_hash: str, tampered_verified: bool):
    print("Tamper check")
    print("------------")
    print(f"Original     : {original_hash}")
    print(f"On-chain     : {'VERIFIED' if original_verified else 'NOT FOUND'}\n")
    print(f"Modified     : {tampered_hash}")
    print(f"On-chain     : {'VERIFIED' if tampered_verified else 'NOT FOUND'}\n")
    
    print("RESULT")
    print("------")
    if original_verified and not tampered_verified:
        print("TAMPERING DETECTED\n")
    else:
        print("TAMPER CHECK FAILED\n")
