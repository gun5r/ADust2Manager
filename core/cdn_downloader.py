# -*- coding: utf-8 -*-
from game_info import UNITY_USER_AGENT
import base64
import json
import os
import requests
import struct
import tempfile
import threading
import time
from persistence import write_json_atomic
from pathlib import Path

# Re-export the existing parsing API while sharing one implementation.
from catalog_parser import SerializationUtilities, read_int32_from_byte_array, read_object_from_byte_array
import maintenance_info_pb2

_VERSION_TTL_SECONDS = 600
_version_cache = {}  # quality tier -> (fetched_at, version)
_version_lock = threading.Lock()


def get_cdn_version(quality):
    """Latest game bundle version. Cached for ten minutes (resolving one mod asks for it, and a batch resolves dozens);
    when the endpoint cannot be reached the last known version keeps cached catalogs usable."""
    tier = "HD" if str(quality).upper() in ("HD", "FHD") else "SD"
    now = time.monotonic()
    with _version_lock:
        cached = _version_cache.get(tier)
    if cached and now - cached[0] < _VERSION_TTL_SECONDS:
        return cached[1]
    version = _fetch_cdn_version(quality)
    if version:
        with _version_lock:
            _version_cache[tier] = (now, version)
        return version
    return cached[1] if cached else None


def _fetch_cdn_version(quality):
    try:
        headers = {
            "accept": "*/*",
            "accept-encoding": "gzip",
            "connection": "close",
            "content-type": "multipart/form-data",
            "host": "mt.bd2.pmang.cloud",
            "user-agent": UNITY_USER_AGENT,
        }
        resp = requests.put("https://mt.bd2.pmang.cloud/MaintenanceInfo", data=b"EAQ=", headers=headers, timeout=15)
        if resp.status_code == 200:
            response_json = resp.json()
            base64_data = response_json['data']
            binary_data = base64.b64decode(base64_data)

            maintenance_response = maintenance_info_pb2.MaintenanceInfoResponse()
            maintenance_response.ParseFromString(binary_data)

            # Both FHD and HD map to bundle_version; SD maps to bundle_version_sd
            is_hd_tier = str(quality).upper() in ('HD', 'FHD')
            return maintenance_response.market_info.bundle_version if is_hd_tier else maintenance_response.market_info.bundle_version_sd
        else:
            print(f"Failed to get CDN version. HTTP Code: {resp.status_code}")
    except Exception as e:
        print(f"Requests failed in get_cdn_version: {e}")
        import traceback
        traceback.print_exc()

    return None


def download_catalog(output_dir, quality, version, cache, lock, progress_callback=None):
    quality_dir = "HD" if str(quality).upper() in ("HD", "FHD") else "SD"
    if not version:
        return None, "Cannot download catalog without a game version"
    cache_key = f"{quality_dir}_{version}"
    with lock:
        if cache_key in cache:
            return cache[cache_key], None
        filename = Path(output_dir) / f"catalog_{quality_dir.lower()}_{version}.json"
        if filename.is_file():
            try:
                content = json.loads(filename.read_text(encoding="utf-8"))
                if isinstance(content, dict):
                    cache[cache_key] = content
                    return content, None
            except (OSError, ValueError):
                pass  # An invalid disk cache is replaced by a fresh download.
        url = f"https://cdn.bd2.pmang.cloud/ServerData/Android/{quality_dir}/{version}/catalog_alpha.json"
        if progress_callback:
            progress_callback(f"Downloading catalog from {url}...")
        try:
            with requests.get(url, timeout=(15, 60)) as response:
                response.raise_for_status()
                content = json.loads(response.content)
            if not isinstance(content, dict):
                return None, "Downloaded catalog must be a JSON object"
            filename.parent.mkdir(parents=True, exist_ok=True)
            write_json_atomic(str(filename), content)
            cache[cache_key] = content
            return content, None
        except (requests.exceptions.RequestException, ValueError, OSError) as exc:
            error = f"Failed to download catalog: {exc}"
            if progress_callback:
                progress_callback(error)
            return None, error


DOWNLOAD_ATTEMPTS = 5  # the CDN (S3 behind CloudFront) now and then resets a long transfer; each retry resumes where it stopped


def _try_download_bundle(url, output_file_path, bundle_size, progress_callback=None):
    """Publish only a complete download; interrupted transfers cannot poison the cache.
    A dropped connection is resumed with a Range request (the CDN accepts them); an HTTP error is final for this url."""
    output_file_path = Path(output_file_path)
    temporary = None
    error = "no data received"
    try:
        with tempfile.NamedTemporaryFile(dir=output_file_path.parent, prefix=".download-", delete=False) as staged:
            temporary = staged.name
        downloaded = 0
        for attempt in range(1, DOWNLOAD_ATTEMPTS + 1):
            if attempt > 1:
                if progress_callback:
                    progress_callback(f"Connection lost ({error}); resuming at {downloaded / 1024:.0f} KB (try {attempt}/{DOWNLOAD_ATTEMPTS})...")
                time.sleep(2 * (attempt - 1))
            try:
                headers = {"Range": f"bytes={downloaded}-"} if downloaded else {}
                with requests.get(url, stream=True, timeout=(15, 60), headers=headers) as response:
                    response.raise_for_status()
                    resumed = bool(downloaded) and response.status_code == 206
                    if downloaded and not resumed:
                        downloaded = 0  # the server sent the whole file again
                    with open(temporary, "ab" if resumed else "wb") as output:
                        for chunk in response.iter_content(chunk_size=65536):
                            if chunk:
                                output.write(chunk)
                                downloaded += len(chunk)
                                if progress_callback:
                                    progress_callback(f"Downloading... {downloaded / 1024:.2f} KB / {bundle_size / 1024:.2f} KB")
                break
            except requests.exceptions.HTTPError as exc:
                return False, str(exc)
            except (requests.exceptions.RequestException, OSError) as exc:
                error = str(exc)
                if attempt == DOWNLOAD_ATTEMPTS:
                    return False, error
        if not downloaded or (bundle_size and downloaded != bundle_size):
            return False, f"Incomplete bundle: expected {bundle_size} bytes, received {downloaded}"
        os.replace(temporary, output_file_path)
        return True, None
    except OSError as exc:
        return False, str(exc)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def _generate_download_urls(base_url, download_name, bundle_name, bundle_hash):
    """
    Generate a list of possible download URLs to try.
    Handles cases where the CDN file may or may not include the hash in the filename.
    """
    urls = []
    
    # 1. Primary: use raw download_name from catalog
    urls.append(f"{base_url}/{download_name}")
    
    # 2. If download_name doesn't contain hash, try adding it
    #    e.g., common-skeleton-data_assets_all.bundle -> common-skeleton-data_assets_all_{hash}.bundle
    if bundle_hash and bundle_hash not in download_name:
        if download_name.endswith('.bundle'):
            name_with_hash = download_name[:-7] + f"_{bundle_hash}.bundle"
            urls.append(f"{base_url}/{name_with_hash}")
    
    # 3. If download_name contains hash but CDN expects without hash, try removing it
    #    e.g., common-skeleton-data_assets_all_{hash}.bundle -> common-skeleton-data_assets_all.bundle
    if bundle_hash and bundle_hash in download_name:
        name_without_hash = download_name.replace(f"_{bundle_hash}", "")
        if name_without_hash != download_name:
            urls.append(f"{base_url}/{name_without_hash}")
    
    # 4. Use bundle_name directly if different from download_name
    if bundle_name and bundle_name != download_name:
        urls.append(f"{base_url}/{bundle_name}")
        # Also try bundle_name with hash
        if bundle_hash and bundle_name.endswith('.bundle'):
            name_with_hash = bundle_name[:-7] + f"_{bundle_hash}.bundle"
            urls.append(f"{base_url}/{name_with_hash}")
    
    # Remove duplicates while preserving order
    seen = set()
    unique_urls = []
    for url in urls:
        if url not in seen:
            seen.add(url)
            unique_urls.append(url)
    
    return unique_urls


def find_and_download_bundle(catalog_content, version, quality, hashed_name, output_dir, progress_callback=None):
    if not catalog_content:
        return None, "Catalog content is missing or empty."

    # Dynamically find the AssetBundleProvider index from m_ProviderIds
    provider_ids = catalog_content.get('m_ProviderIds', [])
    bundle_provider = "UnityEngine.ResourceManagement.ResourceProviders.AssetBundleProvider"
    bundle_provider_index = provider_ids.index(bundle_provider) if bundle_provider in provider_ids else -1

    bucket_array = base64.b64decode(catalog_content['m_BucketDataString'])
    key_array = base64.b64decode(catalog_content['m_KeyDataString'])
    extra_data = base64.b64decode(catalog_content['m_ExtraDataString'])
    entry_data = base64.b64decode(catalog_content['m_EntryDataString'])

    num_buckets = struct.unpack_from('<i', bucket_array, 0)[0]
    data_offsets = []
    index = 4
    for _ in range(num_buckets):
        data_offsets.append(read_int32_from_byte_array(bucket_array, index))
        index += 4 # offset
        num_entries = read_int32_from_byte_array(bucket_array, index)
        index += 4 # num_entries
        index += 4 * num_entries # skip entries

    keys = [read_object_from_byte_array(key_array, offset) for offset in data_offsets]

    number_of_entries = read_int32_from_byte_array(entry_data, 0)
    index = 4
    for _ in range(number_of_entries):
        index += 4 # internal_id
        provider_index = read_int32_from_byte_array(entry_data, index)
        index += 4 # provider_index
        index += 4 # dependency_key
        index += 4 # dependency_hash
        data_index = read_int32_from_byte_array(entry_data, index)
        index += 4 # data_index
        primary_key_index = read_int32_from_byte_array(entry_data, index)
        index += 4 # primary_key
        index += 4 # resource_type

        if provider_index == bundle_provider_index and data_index >= 0:
            bundle_info = read_object_from_byte_array(extra_data, data_index)
            if bundle_info and bundle_info.get('m_BundleName') == hashed_name:
                raw_key = keys[primary_key_index] if primary_key_index < len(keys) else ''
                download_name = str(raw_key)

                if not download_name:
                    continue

                bundle_size = bundle_info.get('m_BundleSize', 0)
                bundle_name = bundle_info.get('m_BundleName')
                bundle_hash = bundle_info.get('m_Hash')
                
                quality_dir = "HD" if str(quality).upper() in ("HD", "FHD") else "SD"
                base_url = f"https://cdn.bd2.pmang.cloud/ServerData/Android/{quality_dir}/{version}"
                urls_to_try = _generate_download_urls(base_url, download_name, bundle_name, bundle_hash)
                
                output_file_path = Path(output_dir).joinpath(bundle_name, bundle_hash, "__data")
                output_file_path.parent.mkdir(parents=True, exist_ok=True)

                # Check if bundle already exists in local cache with valid size
                if output_file_path.exists() and output_file_path.stat().st_size > 0:
                    if bundle_size == 0 or output_file_path.stat().st_size == bundle_size:
                        if progress_callback:
                            progress_callback(f"Using cached original bundle '{bundle_name}' ({bundle_hash[:8]}...). Skipping CDN download.")
                        return str(output_file_path), None

                last_error = None
                for i, url in enumerate(urls_to_try):
                    if progress_callback:
                        if i == 0:
                            progress_callback(f"Found bundle. Downloading from {url}...")
                        else:
                            progress_callback(f"Retrying with alternative URL ({i+1}/{len(urls_to_try)}): {url}...")
                    
                    success, error = _try_download_bundle(url, output_file_path, bundle_size, progress_callback)
                    
                    if success:
                        if progress_callback: progress_callback("Download complete.")
                        return str(output_file_path), None
                    else:
                        last_error = error
                        if progress_callback and i < len(urls_to_try) - 1:
                            progress_callback(f"Download failed: {error}. Trying alternative...")
                
                # All URLs failed
                error_message = f"Failed to download bundle after trying {len(urls_to_try)} URL(s). Last error: {last_error}"
                if progress_callback: progress_callback(error_message)
                return None, error_message

    return None, f"Bundle with hash {hashed_name} not found in catalog."
    


def find_bundle_by_key(catalog_content, needle):
    """First AssetBundle entry whose catalog key contains `needle`: (key, bundle_size) or None."""
    provider_ids = catalog_content.get('m_ProviderIds', [])
    bundle_provider = "UnityEngine.ResourceManagement.ResourceProviders.AssetBundleProvider"
    if bundle_provider not in provider_ids:
        return None
    bundle_provider_index = provider_ids.index(bundle_provider)
    bucket_array = base64.b64decode(catalog_content['m_BucketDataString'])
    key_array = base64.b64decode(catalog_content['m_KeyDataString'])
    extra_data = base64.b64decode(catalog_content['m_ExtraDataString'])
    entry_data = base64.b64decode(catalog_content['m_EntryDataString'])
    num_buckets = struct.unpack_from('<i', bucket_array, 0)[0]
    offsets, index = [], 4
    for _ in range(num_buckets):
        offsets.append(read_int32_from_byte_array(bucket_array, index))
        index += 8 + 4 * read_int32_from_byte_array(bucket_array, index + 4)
    keys = [read_object_from_byte_array(key_array, offset) for offset in offsets]
    index = 4
    for _ in range(read_int32_from_byte_array(entry_data, 0)):
        provider_index = read_int32_from_byte_array(entry_data, index + 4)
        data_index = read_int32_from_byte_array(entry_data, index + 16)
        key_index = read_int32_from_byte_array(entry_data, index + 20)
        index += 28
        if provider_index == bundle_provider_index and data_index >= 0 and key_index < len(keys) and needle in str(keys[key_index]):
            info = read_object_from_byte_array(extra_data, data_index) or {}
            return str(keys[key_index]), info.get('m_BundleSize', 0), info.get('m_Hash')
    return None


def download_catalog_file(version, quality, key, bundle_hash, bundle_size, output_path, progress_callback=None):
    """Download one catalog entry. The CDN serves it without the `_<hash>` suffix the catalog key carries."""
    quality_dir = "HD" if str(quality).upper() in ("HD", "FHD") else "SD"
    name = key.replace(f"_{bundle_hash}", "") if bundle_hash else key
    url = f"https://cdn.bd2.pmang.cloud/ServerData/Android/{quality_dir}/{version}/{name}"
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    return _try_download_bundle(url, output_path, bundle_size, progress_callback)
