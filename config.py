import os
from dotenv import load_dotenv

load_dotenv()

SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")
RPC_URL = os.getenv("RPC_URL", "https://rpc-amoy.polygon.technology")
CHAIN_ID = int(os.getenv("CHAIN_ID", "80002"))
PRIVATE_KEY = os.getenv("PRIVATE_KEY", "")
WALLET_ADDRESS = os.getenv("WALLET_ADDRESS", "")
# ArcFace cosine-DISTANCE threshold (lower distance = more similar).
# Calibrated specifically for clear frontal/moderate-pose images (operating regime).
# NOT a universal face recognition threshold.
FACE_MATCH_THRESHOLD = float(os.getenv("FACE_MATCH_THRESHOLD", "0.600"))

# Face Quality Gate Parameters
MIN_FACE_WIDTH = int(os.getenv("MIN_FACE_WIDTH", "60"))
MIN_FACE_HEIGHT = int(os.getenv("MIN_FACE_HEIGHT", "60"))
MIN_BLUR_SCORE = float(os.getenv("MIN_BLUR_SCORE", "20.0"))

# Face detector backend. 'mtcnn' reliably detects faces and landmark locations.
FACE_DETECTOR = os.getenv("FACE_DETECTOR", "mtcnn")
GALLERY_DIR = os.getenv("GALLERY_DIR", "data/gallery")
CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS", "")

