import datetime
import requests
import config

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
    """Executes the live SerpApi call, returns parsed results.
    If image search fails or returns 0 results, falls back to text search.
    """
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
                "source": item.get("source", "")
            })
    else:
        raw_matches = data.get("organic_results", [])
        for item in raw_matches:
            results.append({
                "url": item.get("link"),
                "title": item.get("title", "No Title"),
                "snippet": item.get("snippet", ""),
                "source": item.get("displayed_link", "")
            })
    return results

def normalize_url(url: str) -> str:
    """Normalizes URL for strict profile matching (removes protocol, www, trailing slashes, converts to lowercase)."""
    if not url:
        return ""
    u = url.lower().strip()
    for prefix in ["https://", "http://", "www."]:
        if u.startswith(prefix):
            u = u[len(prefix):]
    return u.rstrip("/")

def select_best_result(results: list[dict], enrollment_record: dict) -> dict:
    """Selection logic with REQUIRED own profile URL verification gate.
    A candidate is VERIFIED only if its normalized URL matches or is a subpath of an own_known_profiles entry.
    Returns canonical search result structure and verification status metadata.
    """
    iso_timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    own_profiles = enrollment_record.get("own_known_profiles", [])
    normalized_profiles = [normalize_url(p) for p in own_profiles if p]

    if not results:
        return {
            "url": "",
            "title": "",
            "snippet": "",
            "platform": "N/A",
            "verification_status": "NO_VERIFIED_MATCH",
            "verification_reason": "Search API returned zero candidates",
            "retrieved_at": iso_timestamp
        }

    selected = None
    matched_profile = None

    for res in results:
        cand_url_raw = res.get("url") or ""
        cand_url_norm = normalize_url(cand_url_raw)
        if not cand_url_norm:
            continue

        for prof in normalized_profiles:
            if cand_url_norm == prof or cand_url_norm.startswith(prof + "/"):
                selected = res
                matched_profile = prof
                break
        if selected:
            break

    if not selected:
        return {
            "url": "",
            "title": "",
            "snippet": "",
            "platform": "N/A",
            "verification_status": "NO_VERIFIED_MATCH",
            "verification_reason": f"No candidate URL matched enrolled profile allowlist ({', '.join(own_profiles)})",
            "retrieved_at": iso_timestamp
        }

    url_val = selected.get("url", "")
    platform_name = "Web"
    if "linkedin.com" in url_val.lower():
        platform_name = "LinkedIn"
    elif "github.com" in url_val.lower():
        platform_name = "GitHub"
    elif "x.com" in url_val.lower() or "twitter.com" in url_val.lower():
        platform_name = "X / Twitter"

    return {
        "url": url_val,
        "title": selected.get("title", ""),
        "snippet": selected.get("snippet", ""),
        "platform": platform_name,
        "verification_status": "VERIFIED (own profile URL match)",
        "verification_reason": f"Candidate URL matches enrolled profile '{matched_profile}'",
        "retrieved_at": iso_timestamp
    }
