import os
import numpy as np
from deepface import DeepFace
import config

class MatchResult:
    def __init__(self, matched_id: str, confidence: float, model: str, distance_metric: str, threshold_used: float, match: bool):
        self.matched_id = matched_id
        self.confidence = confidence
        self.model = model
        self.distance_metric = distance_metric
        self.threshold_used = threshold_used
        self.match = match

    def to_dict(self) -> dict:
        return {
            "matched_id": self.matched_id,
            "confidence": round(float(self.confidence), 4),
            "model": self.model,
            "distance_metric": self.distance_metric,
            "threshold_used": self.threshold_used,
            "match": self.match
        }

def embed_face(image_path: str, enforce_detection: bool = True) -> np.ndarray:
    """Wraps DeepFace represent call, returns a single embedding vector.
    Raises ValueError with 'no face detected in input image' if detection fails.
    """
    if not os.path.exists(image_path):
        raise ValueError(f"Image path does not exist: {image_path}")
    try:
        results = DeepFace.represent(img_path=image_path, model_name="ArcFace", enforce_detection=enforce_detection)
        if not results or len(results) == 0:
            raise ValueError("no face detected in input image")
        return np.array(results[0]["embedding"], dtype=np.float64)
    except Exception as e:
        err_msg = str(e).lower()
        if "face could not be detected" in err_msg or "no face detected" in err_msg or "facenotdetected" in err_msg or "enforce_detection" in err_msg:
            if enforce_detection:
                # Fallback try without strict detection
                try:
                    results = DeepFace.represent(img_path=image_path, model_name="ArcFace", enforce_detection=False)
                    if results and len(results) > 0:
                        return np.array(results[0]["embedding"], dtype=np.float64)
                except Exception:
                    pass
            raise ValueError("no face detected in input image") from e
        raise e

def load_gallery(gallery_dir: str) -> dict[str, list[np.ndarray]]:
    """Loads and embeds all enrolled images once per run.
    Returns mapping of subject_id -> list of embedding vectors.
    """
    gallery = {}
    if not os.path.exists(gallery_dir):
        return gallery

    for subject_id in os.listdir(gallery_dir):
        subject_path = os.path.join(gallery_dir, subject_id)
        if os.path.isdir(subject_path):
            embeddings = []
            for file in os.listdir(subject_path):
                if file.lower().endswith((".jpg", ".jpeg", ".png")):
                    img_path = os.path.join(subject_path, file)
                    try:
                        emb = embed_face(img_path)
                        embeddings.append(emb)
                    except ValueError:
                        # Skip images without clear faces in gallery loading or log
                        continue
            if embeddings:
                gallery[subject_id] = embeddings
    return gallery

def match_against_gallery(embedding: np.ndarray, gallery: dict[str, list[np.ndarray]]) -> MatchResult:
    """Computes cosine similarity against every enrolled embedding, returns best match."""
    best_id = "unknown"
    best_similarity = -1.0

    # Cosine similarity helper
    def cosine_similarity(v1: np.ndarray, v2: np.ndarray) -> float:
        dot = np.dot(v1, v2)
        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return float(dot / (norm1 * norm2))

    for subject_id, emb_list in gallery.items():
        for gallery_emb in emb_list:
            sim = cosine_similarity(embedding, gallery_emb)
            if sim > best_similarity:
                best_similarity = sim
                best_id = subject_id

    is_match = best_similarity >= config.FACE_MATCH_THRESHOLD

    return MatchResult(
        matched_id=best_id if is_match else "unknown",
        confidence=best_similarity if best_similarity > 0 else 0.0,
        model="ArcFace",
        distance_metric="cosine",
        threshold_used=config.FACE_MATCH_THRESHOLD,
        match=is_match
    )
