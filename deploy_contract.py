import json
import os
import solcx
from web3 import Web3
import config

def compile_contract():
    solcx.install_solc("0.8.20")
    solcx.set_solc_version("0.8.20")
    
    contract_path = os.path.join(os.path.dirname(__file__), "contracts", "ContentRegistry.sol")
    compiled = solcx.compile_files(
        [contract_path],
        output_values=["abi", "bin"],
        solc_version="0.8.20"
    )
    
    key = list(compiled.keys())[0]
    abi = compiled[key]["abi"]
    bytecode = compiled[key]["bin"]
    
    abi_dir = os.path.join(os.path.dirname(__file__), "src", "blockchain", "abi")
    os.makedirs(abi_dir, exist_ok=True)
    abi_path = os.path.join(abi_dir, "ContentRegistry.json")
    with open(abi_path, "w") as f:
        json.dump(abi, f, indent=2)
        
    return abi, bytecode

def update_env_file(key: str, value: str):
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    lines = []
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            lines = f.readlines()
            
    updated = False
    new_lines = []
    for line in lines:
        if line.strip().startswith(f"{key}="):
            new_lines.append(f"{key}={value}\n")
            updated = True
        else:
            new_lines.append(line)
            
    if not updated:
        new_lines.append(f"\n{key}={value}\n")
        
    with open(env_path, "w") as f:
        f.writelines(new_lines)

def deploy():
    print("Compiling ContentRegistry.sol...")
    abi, bytecode = compile_contract()
    
    w3 = Web3(Web3.HTTPProvider(config.RPC_URL))
    if not w3.is_connected():
        raise RuntimeError(f"Failed to connect to RPC: {config.RPC_URL}")
        
    account = w3.eth.account.from_key(config.PRIVATE_KEY)
    sender_address = account.address
    
    print(f"Deploying from wallet: {sender_address}")
    
    contract = w3.eth.contract(abi=abi, bytecode=bytecode)
    nonce = w3.eth.get_transaction_count(sender_address)
    
    tx_params = {
        "from": sender_address,
        "nonce": nonce,
        "gasPrice": w3.eth.gas_price,
        "chainId": config.CHAIN_ID
    }
    
    try:
        estimated_gas = contract.constructor().estimate_gas({"from": sender_address})
        tx_params["gas"] = int(estimated_gas * 1.2)
    except Exception:
        tx_params["gas"] = 1500000
        
    construct_tx = contract.constructor().build_transaction(tx_params)
    signed_tx = w3.eth.account.sign_transaction(construct_tx, config.PRIVATE_KEY)
    
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    tx_hash_hex = tx_hash.hex()
    
    print(f"Deployment transaction submitted: {tx_hash_hex}")
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    
    if receipt["status"] != 1:
        raise RuntimeError("Smart contract deployment transaction reverted!")
        
    contract_address = receipt["contractAddress"]
    update_env_file("CONTRACT_ADDRESS", contract_address)
    
    print("\nBlockchain Deployment")
    print("---------------------")
    print(f"Network: Polygon Amoy")
    print(f"Chain ID: {config.CHAIN_ID}")
    print(f"Wallet: {sender_address}")
    print(f"Contract: {contract_address}")
    print(f"Transaction: {tx_hash_hex}")
    print(f"Status: SUCCESS")
    print(f"\nPolygonScan links:")
    print(f"https://amoy.polygonscan.com/address/{contract_address}")
    print(f"https://amoy.polygonscan.com/tx/{tx_hash_hex}")
    
    return contract_address, tx_hash_hex

if __name__ == "__main__":
    deploy()
