import datetime
import os
import tempfile
import requests
import config
import face_match

def build_query(enrollment_record: dict) -> dict:
    """Chooses image-URL-based reverse search if search_image_url is present,
    else falls back to text search using search_terms.
    """
    if enrollment_record.get("search_image_url"):
        return {
            "engine": "google_lens",
            "url": enrollment_record["search_image_url"],
            "api_key": config.SERPAPI_KEY
        }
    else:
        terms = enrollment_record.get("search_terms", [])
        query_str = terms[0] if terms else enrollment_record.get("display_name", "")
        return {
            "engine": "google",
            "q": query_str,
            "api_key": config.SERPAPI_KEY
        }

def run_search(query: dict) -> list[dict]:
    """Executes the live SerpApi call, returns parsed results with candidate image URLs when available."""
    url = "https://serpapi.com/search"
    resp = requests.get(url, params=query, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    results = []
    if query.get("engine") == "google_lens":
        raw_matches = data.get("visual_matches", [])
        for item in raw_matches:
            results.append({
                "url": item.get("link") or item.get("source"),
                "title": item.get("title", "No Title"),
                "snippet": item.get("snippet") or item.get("source") or "",
                "source": item.get("source", ""),
                "image_url": item.get("thumbnail") or item.get("image")
            })
    else:
        raw_matches = data.get("organic_results", [])
        for item in raw_matches:
            img_url = None
            pagemap = item.get("pagemap", {})
            if "cse_image" in pagemap and isinstance(pagemap["cse_image"], list) and pagemap["cse_image"]:
                img_url = pagemap["cse_image"][0].get("src")
            elif "og_image" in pagemap and isinstance(pagemap["og_image"], list) and pagemap["og_image"]:
                img_url = pagemap["og_image"][0].get("src")
                
            results.append({
                "url": item.get("link"),
                "title": item.get("title", "No Title"),
                "snippet": item.get("snippet", ""),
                "source": item.get("displayed_link", ""),
                "image_url": img_url
            })
    return results

def normalize_url(url: str) -> str:
    """Normalizes URL for profile matching."""
    if not url:
        return ""
    u = url.lower().strip()
    for prefix in ["https://", "http://", "www."]:
        if u.startswith(prefix):
            u = u[len(prefix):]
    return u.rstrip("/")

def verify_candidate_face(candidate_image_url: str, gallery: dict) -> tuple[bool, float]:
    """Downloads candidate image and runs embed_face() + match_against_gallery().
    Returns (is_face_match, similarity_score).
    """
    if not candidate_image_url:
        return False, 0.0

    tmp_file = None
    try:
        resp = requests.get(candidate_image_url, timeout=10)
        if resp.status_code != 200:
            return False, 0.0
            
        fd, tmp_file = tempfile.mkstemp(suffix=".jpg")
        os.write(fd, resp.content)
        os.close(fd)

        embedding = face_match.embed_face(tmp_file, enforce_detection=False)
        match_result = face_match.match_against_gallery(embedding, gallery)
        
        if os.path.exists(tmp_file):
            os.remove(tmp_file)

        return match_result.match, match_result.confidence
    except Exception:
        if tmp_file and os.path.exists(tmp_file):
            try:
                os.remove(tmp_file)
            except Exception:
                pass
        return False, 0.0

def select_best_result(results: list[dict], enrollment_record: dict, gallery: dict = None) -> dict:
    """Selection logic with FACE_MATCH && WEB_CONTENT_FACE_MATCH verification gate.
    Requires that discovered candidate content contains an independently verified face match against the enrolled gallery.
    URL/profile ownership is supporting evidence (OWNERSHIP_MATCH).
    """
    iso_timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if gallery is None:
        gallery = face_match.load_gallery(config.GALLERY_DIR)

    own_profiles = enrollment_record.get("own_known_profiles", [])
    normalized_profiles = [normalize_url(p) for p in own_profiles if p]

    if not results:
        return {
            "candidate_url": "",
            "candidate_title": "",
            "candidate_platform": "N/A",
            "candidate_image_url": "",
            "face_match_score": 0.0,
            "ownership_match": False,
            "verification_status": "UNVERIFIED",
            "verification_reason": "Search API returned zero candidates",
            "url": "",
            "title": "",
            "snippet": "",
            "retrieved_at": iso_timestamp
        }

    verified_candidate = None
    best_unverified_reason = "No candidate image available for independent face verification"

    for res in results:
        cand_url_raw = res.get("url") or ""
        cand_url_norm = normalize_url(cand_url_raw)
        cand_img_url = res.get("image_url")

        # Check ownership match
        is_owner = False
        if cand_url_norm:
            for prof in normalized_profiles:
                if cand_url_norm == prof or cand_url_norm.startswith(prof + "/"):
                    is_owner = True
                    break

        if not cand_img_url:
            continue

        is_face_match, score = verify_candidate_face(cand_img_url, gallery)

        if is_face_match:
            verified_candidate = {
                "candidate_url": cand_url_raw,
                "candidate_title": res.get("title", ""),
                "candidate_platform": "GitHub" if "github" in cand_url_raw.lower() else ("LinkedIn" if "linkedin" in cand_url_raw.lower() else "Web"),
                "candidate_image_url": cand_img_url,
                "face_match_score": score,
                "ownership_match": is_owner,
                "verification_status": "VERIFIED MATCH" if is_owner else "VERIFIED FACE MATCH",
                "verification_reason": f"Discovered web image verified against gallery (score: {score:.3f}, ownership: {is_owner})",
                "url": cand_url_raw,
                "title": res.get("title", ""),
                "snippet": res.get("snippet", ""),
                "retrieved_at": iso_timestamp
            }
            break

    if verified_candidate:
        return verified_candidate

    # Return structured UNVERIFIED output when no candidate content contains a verified face match
    first_cand = results[0] if results else {}
    first_url = first_cand.get("url", "")
    is_first_owner = any(normalize_url(first_url) == p or normalize_url(first_url).startswith(p + "/") for p in normalized_profiles)

    return {
        "candidate_url": first_url,
        "candidate_title": first_cand.get("title", ""),
        "candidate_platform": "GitHub" if "github" in first_url.lower() else ("LinkedIn" if "linkedin" in first_url.lower() else "Web"),
        "candidate_image_url": first_cand.get("image_url", ""),
        "face_match_score": 0.0,
        "ownership_match": is_first_owner,
        "verification_status": "UNVERIFIED — candidate image unavailable" if not first_cand.get("image_url") else "REJECTED — face match score below threshold",
        "verification_reason": best_unverified_reason if not first_cand.get("image_url") else "Discovered image failed independent face verification",
        "url": "",
        "title": "",
        "snippet": "",
        "retrieved_at": iso_timestamp
    }
