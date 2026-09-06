import os
from dotenv import load_dotenv

load_dotenv()

SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")
RPC_URL = os.getenv("RPC_URL", "https://rpc-amoy.polygon.technology")
CHAIN_ID = int(os.getenv("CHAIN_ID", "80002"))
PRIVATE_KEY = os.getenv("PRIVATE_KEY", "")
WALLET_ADDRESS = os.getenv("WALLET_ADDRESS", "")
FACE_MATCH_THRESHOLD = float(os.getenv("FACE_MATCH_THRESHOLD", "0.65"))
GALLERY_DIR = os.getenv("GALLERY_DIR", "data/gallery")
CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS", "")
