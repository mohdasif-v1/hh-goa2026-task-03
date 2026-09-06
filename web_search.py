import datetime
import os
import re
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

def classify_social_url(url: str) -> tuple[str, str]:
    """Classifies a URL into candidate_platform and candidate_type.
    Returns (candidate_platform, candidate_type).
    Types: linkedin_post, instagram_post, x_post, other_social, profile, generic_webpage.
    """
    if not url:
        return "N/A", "generic_webpage"

    u = url.lower()
    
    # LinkedIn
    if "linkedin.com" in u:
        if "/posts/" in u or "/activity/" in u or "/feed/update/" in u or "/pulse/" in u:
            return "LinkedIn", "linkedin_post"
        elif "/in/" in u or "/company/" in u:
            return "LinkedIn", "profile"
        return "LinkedIn", "other_social"

    # Instagram
    if "instagram.com" in u:
        if "/p/" in u or "/reel/" in u or "/tv/" in u:
            return "Instagram", "instagram_post"
        return "Instagram", "profile"

    # X / Twitter
    if "x.com" in u or "twitter.com" in u:
        if "/status/" in u:
            return "X / Twitter", "x_post"
        return "X / Twitter", "profile"

    # GitHub
    if "github.com" in u:
        parts = u.split("github.com/")[-1].strip("/").split("/")
        if len(parts) >= 2 and parts[1] not in ["followers", "following", "stars", "tab"]:
            return "GitHub", "other_social"  # Repository/Project Post
        return "GitHub", "profile"

    return "Web", "generic_webpage"

def run_search(query: dict, enrollment_record: dict = None) -> list[dict]:
    """Executes live SerpApi call(s) and extracts candidates with all available image URLs."""
    url = "https://serpapi.com/search"
    results = []

    # 1. Google Lens search if query engine is google_lens
    if query.get("engine") == "google_lens":
        resp = requests.get(url, params=query, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        raw_matches = data.get("visual_matches", [])
        for item in raw_matches:
            link_url = item.get("link") or item.get("source") or ""
            platform, cand_type = classify_social_url(link_url)
            
            img_urls = []
            for k in ["thumbnail", "image", "original"]:
                v = item.get(k)
                if v and isinstance(v, str) and v.startswith("http"):
                    img_urls.append(v)
            primary_img = img_urls[0] if img_urls else None

            results.append({
                "url": link_url,
                "title": item.get("title", "No Title"),
                "snippet": item.get("snippet") or item.get("source") or "",
                "source": item.get("source", ""),
                "image_url": primary_img,
                "all_image_urls": img_urls,
                "candidate_platform": platform,
                "candidate_type": cand_type,
                "raw_item": item
            })

    # 2. Organic Google search targeting social sites if enrollment_record provides search terms
    if enrollment_record and enrollment_record.get("display_name"):
        disp_name = enrollment_record["display_name"]
        site_queries = [
            f'"{disp_name}" site:linkedin.com/posts/',
            f'"{disp_name}" site:instagram.com/p/',
            f'"{disp_name}" site:instagram.com/reel/',
            f'"{disp_name}" site:x.com/*/status/',
            f'"{disp_name}" site:twitter.com/*/status/'
        ]
        for sq in site_queries:
            org_query = {
                "engine": "google",
                "q": sq,
                "api_key": config.SERPAPI_KEY
            }
            try:
                r = requests.get(url, params=org_query, timeout=10)
                if r.status_code == 200:
                    org_data = r.json()
                    org_matches = org_data.get("organic_results", [])
                    for item in org_matches:
                        link_url = item.get("link", "")
                        platform, cand_type = classify_social_url(link_url)
                        
                        img_urls = []
                        pagemap = item.get("pagemap", {})
                        if "cse_image" in pagemap and isinstance(pagemap["cse_image"], list):
                            for ci in pagemap["cse_image"]:
                                if ci.get("src") and ci.get("src").startswith("http"):
                                    img_urls.append(ci.get("src"))
                        if "og_image" in pagemap and isinstance(pagemap["og_image"], list):
                            for ogi in pagemap["og_image"]:
                                if ogi.get("src") and ogi.get("src").startswith("http"):
                                    img_urls.append(ogi.get("src"))

                        primary_img = img_urls[0] if img_urls else None
                        results.append({
                            "url": link_url,
                            "title": item.get("title", "No Title"),
                            "snippet": item.get("snippet", ""),
                            "source": item.get("displayed_link", ""),
                            "image_url": primary_img,
                            "all_image_urls": img_urls,
                            "candidate_platform": platform,
                            "candidate_type": cand_type,
                            "raw_item": item
                        })
            except Exception:
                pass

    return results

def normalize_url(url: str) -> str:
    """Normalizes URL for matching."""
    if not url:
        return ""
    u = url.lower().strip()
    for prefix in ["https://", "http://", "www."]:
        if u.startswith(prefix):
            u = u[len(prefix):]
    return u.rstrip("/")

def verify_candidate_face(candidate_image_url: str, gallery: dict) -> tuple[bool, float, int, str]:
    """Downloads candidate image and runs embed_face() + match_against_gallery().
    Returns (is_face_match, similarity_score, face_count, status_detail).
    """
    if not candidate_image_url or not candidate_image_url.startswith("http"):
        return False, 0.0, 0, "UNVERIFIED — CANDIDATE IMAGE UNAVAILABLE"

    tmp_file = None
    try:
        resp = requests.get(candidate_image_url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code != 200 or not resp.content:
            return False, 0.0, 0, "UNVERIFIED — CANDIDATE IMAGE UNAVAILABLE"

        fd, tmp_file = tempfile.mkstemp(suffix=".jpg")
        os.write(fd, resp.content)
        os.close(fd)

        # Check face detection
        embedding = face_match.embed_face(tmp_file, enforce_detection=False)
        match_result = face_match.match_against_gallery(embedding, gallery)

        if os.path.exists(tmp_file):
            os.remove(tmp_file)

        if match_result.match:
            return True, match_result.confidence, 1, "VERIFIED SOCIAL MEDIA FACE MATCH"
        else:
            return False, match_result.confidence, 1 if match_result.confidence > 0 else 0, "REJECTED — FACE MISMATCH"
    except Exception as e:
        if tmp_file and os.path.exists(tmp_file):
            try:
                os.remove(tmp_file)
            except Exception:
                pass
        return False, 0.0, 0, "UNVERIFIED — CANDIDATE IMAGE UNAVAILABLE"

def select_best_result(results: list[dict], enrollment_record: dict, gallery: dict = None) -> dict:
    """Rigorous candidate selection requiring:
    1. Candidate must have a candidate_image_url that passes independent face verification against the enrolled gallery.
    2. Primary requirement for Task 3: Candidate URL must be a valid social post (linkedin_post, instagram_post, x_post, or other_social).
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
            "candidate_type": "N/A",
            "candidate_image_url": "",
            "face_match_score": 0.0,
            "ownership_match": False,
            "verification_status": "NO VERIFIED SOCIAL MEDIA MATCH FOUND",
            "verification_reason": "Search API returned zero candidates",
            "url": "",
            "title": "",
            "snippet": "",
            "retrieved_at": iso_timestamp
        }

    verified_candidate = None

    for res in results:
        cand_url_raw = res.get("url") or ""
        cand_url_norm = normalize_url(cand_url_raw)
        cand_type = res.get("candidate_type", "generic_webpage")
        cand_platform = res.get("candidate_platform", "Web")
        all_imgs = res.get("all_image_urls") or ([res.get("image_url")] if res.get("image_url") else [])

        # Ownership match check
        is_owner = False
        if cand_url_norm:
            for prof in normalized_profiles:
                if cand_url_norm == prof or cand_url_norm.startswith(prof + "/"):
                    is_owner = True
                    break

        # Check post type requirement (linkedin_post, instagram_post, x_post, or other_social)
        is_social_post = cand_type in ["linkedin_post", "instagram_post", "x_post", "other_social"]
        if not is_social_post:
            continue

        if not all_imgs:
            continue

        for cand_img_url in all_imgs:
            if not cand_img_url:
                continue
            is_face_match, score, fcount, status_det = verify_candidate_face(cand_img_url, gallery)

            if is_face_match:
                verified_candidate = {
                    "candidate_url": cand_url_raw,
                    "candidate_title": res.get("title", ""),
                    "candidate_platform": cand_platform,
                    "candidate_type": cand_type,
                    "candidate_image_url": cand_img_url,
                    "face_match_score": score,
                    "ownership_match": is_owner,
                    "verification_status": "VERIFIED SOCIAL MEDIA FACE MATCH",
                    "verification_reason": f"Discovered social media post content verified via face match (score: {score:.3f}, type: {cand_type})",
                    "url": cand_url_raw,
                    "title": res.get("title", ""),
                    "snippet": res.get("snippet", ""),
                    "retrieved_at": iso_timestamp
                }
                break

        if verified_candidate:
            break

    if verified_candidate:
        return verified_candidate

    # Return structured NO VERIFIED MATCH when no social media post candidate contains a verified face match
    first_cand = results[0] if results else {}
    first_url = first_cand.get("url", "")
    is_first_owner = any(normalize_url(first_url) == p or normalize_url(first_url).startswith(p + "/") for p in normalized_profiles)

    status_str = "UNVERIFIED — CANDIDATE IMAGE UNAVAILABLE" if not first_cand.get("image_url") else ("REJECTED — NOT A SOCIAL MEDIA POST" if first_cand.get("candidate_type") in ["profile", "generic_webpage"] else "REJECTED — FACE MISMATCH")

    return {
        "candidate_url": first_url,
        "candidate_title": first_cand.get("title", ""),
        "candidate_platform": first_cand.get("candidate_platform", "Web"),
        "candidate_type": first_cand.get("candidate_type", "generic_webpage"),
        "candidate_image_url": first_cand.get("image_url", ""),
        "face_match_score": 0.0,
        "ownership_match": is_first_owner,
        "verification_status": status_str,
        "verification_reason": "No discovered social media post contains a candidate image matching the enrolled face gallery",
        "url": "",
        "title": "",
        "snippet": "",
        "retrieved_at": iso_timestamp
    }

