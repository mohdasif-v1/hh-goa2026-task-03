import os
import numpy as np
from deepface import DeepFace
import config

class MatchResult:
    def __init__(self, matched_id: str, distance: float, model: str, distance_metric: str, threshold_used: float, match: bool, face_count: int = 1, matched_face_index: int | None = None, faces_detail: list[dict] = None):
        self.matched_id = matched_id
        self.distance = distance
        self.confidence = distance  # For compatibility / reporting exact cosine distance
        self.model = model
        self.distance_metric = distance_metric
        self.threshold_used = threshold_used
        self.match = match
        self.face_count = face_count
        self.matched_face_index = matched_face_index
        self.faces_detail = faces_detail or []

    def to_dict(self) -> dict:
        return {
            "matched_id": self.matched_id,
            "cosine_distance": round(float(self.distance), 4),
            "confidence": round(float(self.distance), 4),
            "model": self.model,
            "distance_metric": self.distance_metric,
            "threshold_used": self.threshold_used,
            "match": self.match,
            "face_count": self.face_count,
            "matched_face_index": self.matched_face_index,
            "faces_detail": self.faces_detail
        }

import cv2

def compute_face_quality(image_path: str, bbox: dict) -> tuple[int, int, int, int, float, float, str]:
    """Computes face quality metrics for a detected face:
    - original image dimensions (orig_w, orig_h)
    - bounding box width (bw)
    - bounding box height (bh)
    - face area percentage of original image
    - estimated blur score (Laplacian variance of facial crop)
    Returns (orig_w, orig_h, bw, bh, area_pct, blur_score, quality_status).
    
    Quality Gate Thresholds:
    - bw < MIN_FACE_WIDTH (60px) OR bh < MIN_FACE_HEIGHT (60px) OR blur_score < MIN_BLUR_SCORE (20.0) -> REJECTED — FACE QUALITY TOO LOW
    """
    if not image_path or not os.path.exists(image_path):
        return 0, 0, 0, 0, 0.0, 0.0, "REJECTED — IMAGE LOAD FAILED"

    img = cv2.imread(image_path)
    if img is None:
        return 0, 0, 0, 0, 0.0, 0.0, "REJECTED — IMAGE LOAD FAILED"

    orig_h, orig_w = img.shape[:2]
    bx = max(0, bbox.get("x", 0))
    by = max(0, bbox.get("y", 0))
    bw = bbox.get("w", 0)
    bh = bbox.get("h", 0)

    face_area = bw * bh
    img_area = orig_w * orig_h
    area_pct = (face_area / img_area * 100.0) if img_area > 0 else 0.0

    crop_x2 = min(orig_w, bx + bw)
    crop_y2 = min(orig_h, by + bh)
    crop = img[by:crop_y2, bx:crop_x2]

    if crop.size == 0:
        blur_score = 0.0
    else:
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())

    if bw < config.MIN_FACE_WIDTH or bh < config.MIN_FACE_HEIGHT or blur_score < config.MIN_BLUR_SCORE:
        quality_status = "REJECTED — FACE QUALITY TOO LOW"
    else:
        quality_status = "PASSED QUALITY GATE"

    return orig_w, orig_h, bw, bh, area_pct, blur_score, quality_status

def cosine_distance(v1: np.ndarray, v2: np.ndarray) -> float:
    """Computes standard Cosine Distance = 1.0 - (v1 . v2) / (||v1|| ||v2||).
    Lower distance indicates higher identity similarity.
    """
    dot = np.dot(v1, v2)
    norm1 = np.linalg.norm(v1)
    norm2 = np.linalg.norm(v2)
    if norm1 == 0 or norm2 == 0:
        return 1.0
    sim = float(dot / (norm1 * norm2))
    # Clamp cosine similarity to [-1.0, 1.0] for floating point stability
    sim = max(-1.0, min(1.0, sim))
    return 1.0 - sim

def extract_all_faces(image_path: str) -> list[dict]:
    """Extracts all faces from an image using DeepFace with MTCNN backend and strict detection.
    Returns list of dicts: [{"embedding": np.ndarray, "facial_area": dict, "image_path": str}, ...]
    Raises ValueError if no valid face is detected.
    """
    if not os.path.exists(image_path):
        raise ValueError(f"Image path does not exist: {image_path}")

    try:
        results = DeepFace.represent(
            img_path=image_path,
            model_name="ArcFace",
            detector_backend=config.FACE_DETECTOR,
            enforce_detection=True
        )
        if not results or len(results) == 0:
            raise ValueError("no face detected in input image")

        valid_faces = []
        for res in results:
            area = res.get("facial_area", {})
            # Verify valid facial bounding box (w > 0 and h > 0 and non-zero landmarks/crop)
            if area and area.get("w", 0) > 0 and area.get("h", 0) > 0:
                emb = np.array(res["embedding"], dtype=np.float64)
                valid_faces.append({
                    "embedding": emb,
                    "facial_area": area,
                    "image_path": image_path
                })

        if not valid_faces:
            raise ValueError("no face detected in input image")

        return valid_faces

    except Exception as e:
        err_msg = str(e).lower()
        if "face could not be detected" in err_msg or "no face detected" in err_msg or "facenotdetected" in err_msg:
            raise ValueError("no face detected in input image") from e
        raise e


def embed_face(image_path: str) -> np.ndarray:
    """Wraps extract_all_faces, returning the embedding of the primary (first/largest) face detected.
    Raises ValueError if no valid face is detected.
    """
    faces = extract_all_faces(image_path)
    return faces[0]["embedding"]

def load_gallery(gallery_dir: str) -> dict[str, list[np.ndarray]]:
    """Loads and embeds all enrolled images once per run using strict face detection.
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
                        continue
            if embeddings:
                gallery[subject_id] = embeddings
    return gallery

def match_against_gallery(embeddings: np.ndarray | list[np.ndarray] | list[dict], gallery: dict[str, list[np.ndarray]]) -> MatchResult:
    """Computes minimum cosine distance against every enrolled embedding for each face detected in candidate image.
    Reports every face's distance and bounding box, and sets matched_face_index for the best passing face.
    Accepts candidate if minimum distance < FACE_MATCH_THRESHOLD.
    """
    if isinstance(embeddings, np.ndarray):
        raw_faces = [{"embedding": embeddings, "facial_area": {}}]
    elif isinstance(embeddings, list) and embeddings and isinstance(embeddings[0], np.ndarray):
        raw_faces = [{"embedding": e, "facial_area": {}} for e in embeddings]
    elif isinstance(embeddings, list):
        raw_faces = embeddings
    else:
        raw_faces = []

    if not raw_faces or not gallery:
        return MatchResult(
            matched_id="unknown",
            distance=1.0,
            model="ArcFace",
            distance_metric="cosine",
            threshold_used=config.FACE_MATCH_THRESHOLD,
            match=False,
            face_count=len(raw_faces),
            matched_face_index=None,
            faces_detail=[]
        )

    faces_detail = []
    best_overall_id = "unknown"
    best_overall_dist = 999.0
    best_overall_face_idx = None
    is_overall_match = False

    for idx, face_info in enumerate(raw_faces):
        cand_emb = face_info["embedding"]
        bbox = face_info.get("facial_area", {})
        img_path = face_info.get("image_path", "")
        
        orig_w, orig_h, bw, bh, area_pct, blur_score, quality_status = compute_face_quality(img_path, bbox) if img_path else (0, 0, bbox.get("w", 0), bbox.get("h", 0), 0.0, 100.0, "PASSED QUALITY GATE")
        
        # Enforce quality gate
        if quality_status.startswith("REJECTED"):
            faces_detail.append({
                "face_index": idx,
                "bounding_box": bbox,
                "bbox_width": bw,
                "bbox_height": bh,
                "blur_score": round(blur_score, 1),
                "quality_status": quality_status,
                "cosine_distance": 1.0,
                "matched_id": "unknown",
                "status": quality_status
            })
            continue

        face_min_dist = 999.0
        face_best_id = "unknown"
        
        for subject_id, enrolled_embs in gallery.items():
            for enrolled_emb in enrolled_embs:
                dist = cosine_distance(cand_emb, enrolled_emb)
                if dist < face_min_dist:
                    face_min_dist = dist
                    face_best_id = subject_id
        
        face_is_match = face_min_dist < config.FACE_MATCH_THRESHOLD
        face_dist_val = face_min_dist if face_min_dist < 999.0 else 1.0
        
        faces_detail.append({
            "face_index": idx,
            "bounding_box": bbox,
            "bbox_width": bw,
            "bbox_height": bh,
            "blur_score": round(blur_score, 1),
            "quality_status": quality_status,
            "cosine_distance": round(float(face_dist_val), 4),
            "matched_id": face_best_id if face_is_match else "unknown",
            "status": "MATCH" if face_is_match else "NO MATCH"
        })

        if face_is_match and face_min_dist < best_overall_dist:
            best_overall_dist = face_min_dist
            best_overall_id = face_best_id
            best_overall_face_idx = idx
            is_overall_match = True

    if not is_overall_match:
        # Find minimum distance even if no match passed threshold
        for idx, fdetail in enumerate(faces_detail):
            if fdetail.get("cosine_distance", 1.0) < best_overall_dist:
                best_overall_dist = fdetail["cosine_distance"]

    return MatchResult(
        matched_id=best_overall_id if is_overall_match else "unknown",
        distance=best_overall_dist if best_overall_dist < 999.0 else 1.0,
        model="ArcFace",
        distance_metric="cosine",
        threshold_used=config.FACE_MATCH_THRESHOLD,
        match=is_overall_match,
        face_count=len(raw_faces),
        matched_face_index=best_overall_face_idx,
        faces_detail=faces_detail
    )


