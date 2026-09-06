import json
import os
from web3 import Web3
import config

def connect_to_polygon() -> Web3:
    """Connects to Polygon Amoy RPC and confirms connection. Raises RuntimeError if disconnected."""
    endpoints = [
        config.RPC_URL,
        "https://rpc-amoy.polygon.technology",
        "https://polygon-amoy.drpc.org",
        "https://polygon-amoy-bor-rpc.publicnode.com",
        "https://rpc.ankr.com/polygon_amoy",
        "https://polygon-amoy.blockpi.network/v1/rpc/public"
    ]
    for ep in endpoints:
        if not ep or not ep.startswith("http"):
            continue
        try:
            w3 = Web3(Web3.HTTPProvider(ep, request_kwargs={"timeout": 8}))
            if w3.is_connected():
                return w3
        except Exception:
            continue
    raise RuntimeError(f"Failed to connect to Polygon Amoy RPC endpoints")



def load_contract(w3: Web3 = None):
    """Loads the deployed ContentRegistry contract instance."""
    if w3 is None:
        w3 = connect_to_polygon()
        
    contract_address = config.CONTRACT_ADDRESS
    if not contract_address:
        raise ValueError("CONTRACT_ADDRESS missing from configuration")
        
    abi_path = os.path.join(os.path.dirname(__file__), "src", "blockchain", "abi", "ContentRegistry.json")
    if not os.path.exists(abi_path):
        abi_path = os.path.join(os.path.dirname(__file__), "ContentRegistry.json")
        
    with open(abi_path, "r") as f:
        abi = json.load(f)
        
    checksum_address = Web3.to_checksum_address(contract_address)
    return w3.eth.contract(address=checksum_address, abi=abi)

def hex_to_bytes32(sha256_hex: str) -> bytes:
    """Validates and converts a 64-character SHA-256 hex string to bytes32."""
    clean_hex = sha256_hex.lower()
    if clean_hex.startswith("0x"):
        clean_hex = clean_hex[2:]
        
    if len(clean_hex) != 64:
        raise ValueError(f"Invalid SHA-256 hex length ({len(clean_hex)} chars); expected 64 hex chars for bytes32.")
        
    b32 = bytes.fromhex(clean_hex)
    if len(b32) != 32:
        raise ValueError(f"Converted bytes length is {len(b32)}; expected 32 bytes.")
    return b32

def register_hash(sha256_hex: str) -> tuple[str, int]:
    """Calls ContentRegistry.registerHash(bytes32) on Polygon Amoy.
    Returns (transaction_hash_hex, block_number).
    """
    w3 = connect_to_polygon()
    contract = load_contract(w3)
    
    if not config.PRIVATE_KEY:
        raise ValueError("PRIVATE_KEY missing in environment configuration")
        
    account = w3.eth.account.from_key(config.PRIVATE_KEY)
    sender_address = account.address
    
    bytes32_hash = hex_to_bytes32(sha256_hex)
    nonce = w3.eth.get_transaction_count(sender_address)
    
    tx_params = {
        "from": sender_address,
        "nonce": nonce,
        "gasPrice": w3.eth.gas_price,
        "chainId": config.CHAIN_ID
    }
    
    try:
        estimated_gas = contract.functions.registerHash(bytes32_hash).estimate_gas({"from": sender_address})
        tx_params["gas"] = int(estimated_gas * 1.3)
    except Exception:
        tx_params["gas"] = 150000
        
    func_call = contract.functions.registerHash(bytes32_hash).build_transaction(tx_params)
    signed_tx = w3.eth.account.sign_transaction(func_call, config.PRIVATE_KEY)
    
    raw_tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    tx_hash_hex = raw_tx_hash.hex()
    if not tx_hash_hex.startswith("0x"):
        tx_hash_hex = f"0x{tx_hash_hex}"
        
    receipt = w3.eth.wait_for_transaction_receipt(raw_tx_hash, timeout=120)
    
    if receipt["status"] != 1:
        raise RuntimeError(f"Transaction reverted on-chain: {tx_hash_hex}")
        
    return tx_hash_hex, receipt["blockNumber"]

def verify_hash(sha256_hex: str) -> bool:
    """Calls ContentRegistry.verifyHash(bytes32).call() and returns boolean result."""
    w3 = connect_to_polygon()
    contract = load_contract(w3)
    bytes32_hash = hex_to_bytes32(sha256_hex)
    return contract.functions.verifyHash(bytes32_hash).call()

# Backwards compatibility wrappers for chain.py
def send_fingerprint(fingerprint_hex: str) -> str:
    tx_hash, _ = register_hash(fingerprint_hex)
    return tx_hash

def verify_fingerprint(tx_hash: str, expected_fingerprint_hex: str) -> bool:
    return verify_hash(expected_fingerprint_hex)
