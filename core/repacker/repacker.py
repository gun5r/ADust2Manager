from game_info import UNITY_VERSION
from paths import bin_path
from PIL import Image
import os
from .json_to_skel import json_to_skel
import skel_convert
import mod_health
import tempfile
import gc
from PIL import ImageFile
import re
import shutil
import glob
from concurrent.futures import ProcessPoolExecutor, as_completed

# 平行處理設定
# 限制同時處理的紋理數量，避免記憶體過載
MAX_PARALLEL_TEXTURES = min(4, max(1, (os.cpu_count() or 4) // 2))

from UnityPy.helpers import TypeTreeHelper
TypeTreeHelper.read_typetree_boost = False
import UnityPy

UnityPy.config.FALLBACK_UNITY_VERSION = UNITY_VERSION
ImageFile.LOAD_TRUNCATED_IMAGES = True  # a cut-off texture is warned about (mod_health) and still installed, as before: not fatal, in every code path

# Editors export "name_4.1.skel" (the Spine version in the file name); the game's asset is "name.skel".
_SPINE_VERSION_SUFFIX = re.compile(r'_\d+\.\d+(?=\.(skel(\.bytes)?|json)$)', re.IGNORECASE)


def _game_name(filename: str) -> str:
    return _SPINE_VERSION_SUFFIX.sub('', filename)


def _build_file_index(working_dirs) -> dict:
    """
    一次遍歷建立完整的檔案索引，避免重複 os.walk 操作。
    支援單一目錄 (str) 或多目錄合併 (list of str)。
    
    Returns:
        dict with keys:
        - 'skel_json': {base_name: (type, filepath, directory)}
        - 'all_files': [filepath, ...]
    """
    if isinstance(working_dirs, str):
        working_dirs = [working_dirs]

    index = {
        'skel_json': {},   # base_name -> (type, path, directory)
        'all_files': []    # [path]
    }
    
    for wdir in working_dirs:
        if not wdir or not os.path.exists(wdir):
            continue
        for root, _, files in os.walk(wdir):
            if '.old' in root:
                continue
            for f in files:
                filepath = os.path.join(root, f)
                index['all_files'].append(filepath)
                f_lower = _game_name(f.lower())
                
                if f_lower.endswith(('.skel', '.skel.bytes', '.json')):
                    base_name = re.sub(r'\.(skel\.bytes|skel|json)$', '', f_lower)
                    file_type = 'json' if f_lower.endswith('.json') else 'skel'
                    if base_name not in index['skel_json']:
                        index['skel_json'][base_name] = (file_type, filepath, root)
    
    return index


from utils.atlas_operations import parse_atlas_file

def _merge_spine_assets(mod_dir_path, base_name, target_count, report_progress):
    report_progress(f"Starting Spine asset merge for '{base_name}' in temporary directory.")

    _png_pattern = re.compile(rf'^{re.escape(base_name)}(_\d+)?\.png$', re.IGNORECASE)
    original_png_files = sorted([
        os.path.join(mod_dir_path, f) for f in os.listdir(mod_dir_path)
        if _png_pattern.match(f)
    ])
    original_atlas_path = os.path.join(mod_dir_path, f"{base_name}.atlas")

    if not original_png_files or not os.path.exists(original_atlas_path):
        return f"SKIPPING: Missing png or atlas files for {base_name} in the working directory."

    atlas_db, err = parse_atlas_file(original_atlas_path)
    if err:
        return f"FAILED: Could not parse atlas file: {err}"

    # Sort pngs correctly (_2 before _10)
    def sort_key(filename):
        if filename.endswith(f"{base_name}.png"): return 1
        match = re.search(r'_(\d+)\.png$', filename)
        return int(match.group(1)) if match else float('inf')
    original_png_files.sort(key=lambda x: sort_key(os.path.basename(x)))

    if len(original_png_files) <= target_count:
        # This case should be handled by the calling function, but as a safeguard:
        return "Merge not needed, texture count is already at or below target."

    cut_off = [os.path.basename(p) for p in original_png_files if not mod_health.png_complete(p)]
    if cut_off:
        return f"FAILED: {', '.join(cut_off)} is cut off (an incomplete download); merging it would lose parts of the model."
    report_progress(f"Merging {len(original_png_files)} textures down to {target_count}.")

    images = {}
    for p in original_png_files:
        try:
            img = Image.open(p)
            img.load()  # Force reading the entire image immediately to catch corruption early
            images[os.path.basename(p)] = img
        except OSError as e:
            # Clean up what we opened so far
            for opened_img in images.values():
                opened_img.close()
            return f"FAILED: Could not decode image file '{os.path.basename(p)}'. The PNG stream might be corrupted or in an unsupported format. Error: {e}"
    merging_plan = {i: [] for i in range(target_count)}
    for i, png_path in enumerate(original_png_files):
        merging_plan[i % target_count].append(os.path.basename(png_path))
    
    final_atlas_blocks = []

    for i in range(target_count):
        target_pngs = merging_plan[i]
        if not target_pngs: continue

        base_image_name = target_pngs[0]
        base_image = images[base_image_name].copy()
        
        merged_offsets = {base_image_name: (0, 0)}
        
        current_width = base_image.width
        max_height = base_image.height
        
        for extra_image_name in target_pngs[1:]:
            extra_image = images[extra_image_name]
            merged_offsets[extra_image_name] = (current_width, 0)
            
            new_width = current_width + extra_image.width
            max_height = max(max_height, extra_image.height)
            
            new_base_image = Image.new('RGBA', (new_width, max_height))
            new_base_image.paste(base_image, (0, 0))
            new_base_image.paste(extra_image, (current_width, 0))
            
            # Clean up old base_image to free memory
            base_image.close()
            base_image = new_base_image
            current_width = new_width

        aligned_width = ((current_width + 3) // 4) * 4
        aligned_height = ((max_height + 3) // 4) * 4
        if aligned_width != current_width or aligned_height != max_height:
            aligned_base_image = Image.new('RGBA', (aligned_width, aligned_height))
            aligned_base_image.paste(base_image, (0, 0))
            base_image.close()
            base_image = aligned_base_image

        output_image_name = f"{base_name}.png" if i == 0 else f"{base_name}_{i+1}.png"
        output_path = os.path.join(mod_dir_path, output_image_name)
        base_image.save(output_path)
        base_image.close()  # Close after saving
        report_progress(f"Saved merged image: {output_path}")

        all_sprites_for_block = []
        primary_data = None
        for original_png_name in target_pngs:
            atlas_data = atlas_db.get(original_png_name.lower()) or atlas_db.get(original_png_name)
            if not atlas_data:
                report_progress(f"WARNING: Missing atlas entry for {original_png_name}; skipping atlas block data during merge.")
                continue

            if primary_data is None:
                primary_data = atlas_data

            offset_x, offset_y = merged_offsets[original_png_name]
            
            if offset_x == 0 and offset_y == 0:
                all_sprites_for_block.append(atlas_data['sprites'])
            else:
                modified_sprites = []
                for line in atlas_data['sprites'].split('\n'):
                    stripped = line.strip()
                    if stripped.startswith('bounds:'):
                        try:
                            parts = stripped.split(':')
                            coords = [int(c.strip()) for c in parts[1].split(',')]
                            x, y, w, h = coords
                            x += offset_x
                            y += offset_y
                            indent = line[:line.find('bounds:')]
                            modified_sprites.append(f"{indent}bounds: {x}, {y}, {w}, {h}")
                        except Exception:
                            modified_sprites.append(line)
                    elif stripped.startswith('xy:'):
                        try:
                            parts = stripped.split(':')
                            coords = [int(c.strip()) for c in parts[1].split(',')]
                            x, y = coords
                            x += offset_x
                            indent = line[:line.find('xy:')]
                            modified_sprites.append(f"{indent}xy: {x}, {y}")
                        except Exception:
                            modified_sprites.append(line)
                    else:
                        modified_sprites.append(line)
                all_sprites_for_block.append('\n'.join(modified_sprites))

        if primary_data is None:
            report_progress(f"WARNING: No atlas blocks matched merged texture group {target_pngs}; skipping output atlas block for {output_image_name}.")
            continue

        header_lines = [output_image_name]
        header_lines.append(f"size: {base_image.width}, {base_image.height}")
        header_props = primary_data.get('header_props', {})
        if 'format' in header_props:
            header_lines.append(header_props['format'])
        header_lines.append(header_props.get('filter', primary_data.get('filter_line', 'filter: Linear, Linear')))
        if 'repeat' in header_props:
            header_lines.append(header_props['repeat'])
        if 'pma' in header_props:
            header_lines.append(header_props['pma'])

        new_block = '\n'.join(header_lines) + '\n' + '\n'.join(all_sprites_for_block)
        final_atlas_blocks.append(new_block.strip())
    
    final_atlas_path = os.path.join(mod_dir_path, f"{base_name}.atlas")
    with open(final_atlas_path, 'w', encoding='utf-8') as f:
        f.write('\n\n'.join(final_atlas_blocks) + '\n')
    report_progress(f"Wrote final atlas file to: {final_atlas_path}")
    
    # Clean up images dict to free memory
    for img in images.values():
        img.close()
    del images
    
    # Clean up old, unmerged png files
    report_progress("Cleaning up original, unmerged texture files...")
    for png_path in original_png_files:
        try:
            # Check if the file is one of the NEWLY created merged files.
            # If so, don't delete it.
            if os.path.basename(png_path) not in [f"{base_name}.png" if i == 0 else f"{base_name}_{i+1}.png" for i in range(target_count)]:
                os.remove(png_path)
        except OSError as e:
            report_progress(f"Could not delete old file {png_path}: {e}")
            
    return None

from utils.file_operations import find_file_case_insensitive


import subprocess

def _get_astcenc_bin():
    local_bin = bin_path("astcenc")
    if os.path.exists(local_bin):
        return local_bin
    return shutil.which("astcenc") or local_bin


def _compress_texture_worker(args):
    """
    Worker function to compress texture to ASTC format using native astcenc binary.
    """
    mod_filepath, target_asset_name, block_x, block_y = args
    result = {
        'success': False,
        'target_asset_name': target_asset_name,
        'mod_filepath': mod_filepath,
        'compressed_data': None,
        'width': 0,
        'height': 0,
        'error': None
    }
    
    astcenc_bin = _get_astcenc_bin()
    if not os.path.exists(astcenc_bin):
        result['error'] = f"astcenc binary not found at {astcenc_bin}"
        return result

    try:
        with Image.open(mod_filepath) as pil_img:
            width, height = pil_img.size
            result['width'] = width
            result['height'] = height

        with tempfile.NamedTemporaryFile(suffix=".astc", delete=False) as tmp_astc:
            tmp_astc_path = tmp_astc.name
        try:
            tmp_astc_path.encode('ascii')
        except UnicodeEncodeError:
            if os.path.exists('/tmp') and os.access('/tmp', os.W_OK):
                safe_astc_path = os.path.join('/tmp', f"astc_{os.getpid()}_{id(tmp_astc)}.astc")
                try:
                    os.remove(tmp_astc_path)
                except OSError:
                    pass
                tmp_astc_path = safe_astc_path

        # Support non-ASCII paths (e.g., Korean/Chinese/Japanese characters) by copying to an ASCII-safe temp path
        tmp_png_path = None
        input_path = mod_filepath
        try:
            mod_filepath.encode('ascii')
        except UnicodeEncodeError:
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_png:
                tmp_png_path = tmp_png.name
            try:
                tmp_png_path.encode('ascii')
            except UnicodeEncodeError:
                if os.path.exists('/tmp') and os.access('/tmp', os.W_OK):
                    safe_png_path = os.path.join('/tmp', f"png_{os.getpid()}_{id(tmp_png)}.png")
                    try:
                        os.remove(tmp_png_path)
                    except OSError:
                        pass
                    tmp_png_path = safe_png_path
            shutil.copyfile(mod_filepath, tmp_png_path)
            input_path = tmp_png_path

        try:
            # -cs = LDR sRGB, -yflip = vertical flip for Unity Texture2D, -medium quality, -decode_unorm8 for accurate 8-bit rounding, -silent
            cmd = [
                astcenc_bin, "-cs", input_path, tmp_astc_path,
                f"{block_x}x{block_y}", "-medium", "-yflip", "-decode_unorm8", "-silent"
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True)
            if proc.returncode != 0:
                result['error'] = proc.stderr.strip() or f"astcenc error code {proc.returncode}"
            else:
                with open(tmp_astc_path, "rb") as f:
                    data = f.read()
                # Remove 16-byte ASTC header to extract raw ASTC blocks
                result['compressed_data'] = data[16:]
                result['success'] = True
        finally:
            if os.path.exists(tmp_astc_path):
                try:
                    os.remove(tmp_astc_path)
                except OSError:
                    pass
            if tmp_png_path and os.path.exists(tmp_png_path):
                try:
                    os.remove(tmp_png_path)
                except OSError:
                    pass
    except Exception as e:
        result['error'] = str(e)
    
    return result



def _asset_objects(asset_map, target_asset_name: str, type_name: str = None, container_by_path_id: dict = None, spine_base_names: list = None):
    candidates = [target_asset_name]
    if target_asset_name.endswith('.skel'):
        candidates.append(target_asset_name + '.bytes')
    elif target_asset_name.endswith('.skel.bytes'):
        candidates.append(target_asset_name[:-6])
    elif target_asset_name.endswith('.atlas'):
        candidates.append(target_asset_name + '.txt')
    elif target_asset_name.endswith('.atlas.txt'):
        candidates.append(target_asset_name[:-4])

    extra_cands = []
    for c in candidates:
        if c.startswith('illust_'):
            extra_cands.append(c[len('illust_'):])
        else:
            extra_cands.append(f"illust_{c}")
    candidates.extend(extra_cands)

    objects = []
    for cand in candidates:
        found = asset_map.get(cand, [])
        if found:
            objects = list(found)
            break

    if type_name:
        objects = [obj for obj in objects if obj.type.name == type_name]
    if container_by_path_id and spine_base_names:
        for s_base in spine_base_names:
            s_base_lower = s_base.lower()
            if target_asset_name.startswith(s_base_lower):
                target_dir = f"/skeletondata/{s_base_lower}/"
                scoped = [
                    obj for obj in objects
                    if target_dir in container_by_path_id.get(obj.path_id, "").lower()
                ]
                if scoped:
                    return scoped
    return objects


def repack_bundle(original_bundle_path: str, modded_assets_folder, output_path: str, use_astc: bool, progress_callback=None, is_cancelled=None, quality: str = "HD"):
    """
    Repack a unity bundle with modded assets.
    Supports single mod folder (str) or multiple mod folders (list of str) for shared bundle merging.
    Returns a tuple: (success: bool, message: str)
    """
    def report_progress(message):
        if is_cancelled and is_cancelled():
            raise InterruptedError("Repack cancelled by user.")
        if progress_callback:
            progress_callback(message)
        print(message)
        
    env = None
    try:
        if isinstance(modded_assets_folder, list):
            working_dirs = [d for d in modded_assets_folder if d and os.path.exists(d)]
            report_progress(f"Using {len(working_dirs)} mod directories for bundle merge: {', '.join(os.path.basename(d) for d in working_dirs)}")
        else:
            working_dirs = [modded_assets_folder]
            report_progress(f"Using mod directory: {modded_assets_folder}")

        # The game only finds lowercase file names: lowercase every file and atlas reference first, whatever the caller did.
        from mod_spine_tools import SpineToolsMixin
        for working_dir in working_dirs:
            ok, error = SpineToolsMixin.sanitize_mod_filenames(None, working_dir, report_progress)
            if not ok:
                return False, error

        report_progress("Loading original game file...")
        env = UnityPy.load(original_bundle_path)
        edited = False

        container_by_path_id = {}
        if hasattr(env, "container") and env.container:
            container_by_path_id = {pptr.path_id: path for path, pptr in env.container.items()}

        # --- 建立檔案索引，一次遍歷取代多次 os.walk ---
        report_progress("Building file index...")
        file_index = _build_file_index(working_dirs)
        
        # 從索引中取得 spine mods
        spine_mods_to_process = {
            base_name: directory 
            for base_name, (file_type, filepath, directory) in file_index['skel_json'].items()
        }
        spine_base_names = list(spine_mods_to_process.keys())

        if spine_mods_to_process:
            report_progress(f"Detected {len(spine_mods_to_process)} unique Spine mods for pre-processing: {spine_base_names}")
            for spine_base_name, mod_dir_path in spine_mods_to_process.items():
                report_progress(f"--- Processing: {spine_base_name} ---")
                pattern = re.compile(f"^{re.escape(spine_base_name)}(_\\d+)?$", re.IGNORECASE)
                target_skel_dir = f"/skeletondata/{spine_base_name.lower()}/"
                s_base_lower = spine_base_name.lower()

                # Authoritative material slot count check via SpineAtlasAsset MonoBehaviour (_atlas.asset)
                original_texture_count = 0
                mb_material_count = 0
                for obj in env.objects:
                    if obj.type.name == "MonoBehaviour":
                        c_path = container_by_path_id.get(obj.path_id, "").lower()
                        if c_path.endswith(("_atlas.asset", "_atlas")) and (s_base_lower in c_path or s_base_lower in c_path.replace("illust_", "")):
                            try:
                                atlas_data = obj.read_typetree()
                                if isinstance(atlas_data, dict):
                                    materials = atlas_data.get("materials", [])
                                    if isinstance(materials, list) and len(materials) > 0:
                                        mb_material_count = max(mb_material_count, len(materials))
                            except Exception:
                                pass

                if mb_material_count > 0:
                    original_texture_count = mb_material_count
                    report_progress(f"Found {original_texture_count} material slots in SpineAtlasAsset MonoBehaviour for {spine_base_name}.")
                else:
                    for obj in env.objects:
                        if obj.type.name == "Texture2D":
                            try:
                                asset_name = obj.read().m_Name
                                c_path = container_by_path_id.get(obj.path_id, "").lower()
                                if c_path:
                                    if target_skel_dir in c_path and pattern.match(asset_name):
                                        original_texture_count += 1
                                elif pattern.match(asset_name):
                                    original_texture_count += 1
                            except Exception as e:
                                report_progress(f"Couldn't read asset name, skipping. Error: {e}")
                    report_progress(f"Found {original_texture_count} matching textures in the original game file for {spine_base_name}.")

                _mod_png_pattern = re.compile(rf'^{re.escape(spine_base_name)}(_\d+)?\.png$', re.IGNORECASE)
                mod_texture_count = sum(1 for f in os.listdir(mod_dir_path) if _mod_png_pattern.match(f))
                report_progress(f"Mod has {mod_texture_count} textures for {spine_base_name}.")

                if mod_texture_count > original_texture_count and original_texture_count > 0:
                    report_progress("Mod texture count exceeds original, starting merge process into temp directory...")
                    merge_error = _merge_spine_assets(mod_dir_path, spine_base_name, original_texture_count, report_progress)

                    if merge_error:
                        report_progress(f"ERROR during merge for {spine_base_name}: {merge_error}.")
                    else:
                        report_progress(f"Merge successful for {spine_base_name}.")
                        # Rebuild index to include newly merged files
                        file_index = _build_file_index(working_dirs)
                else:
                    report_progress("Texture count matches or is lower, no merge needed.")

        report_progress("Scanning for moddable assets...")
        
        # Build asset_map indexed by internal m_Name, container path filenames, and extension aliases
        total_objects = len(env.objects)
        asset_map = {}
        for obj in env.objects:
            try:
                data = obj.read()
                if hasattr(data, 'm_Name') and data.m_Name:
                    name_key = data.m_Name.lower()
                    asset_map.setdefault(name_key, []).append(obj)
                    if obj.type.name == "Texture2D" and not name_key.endswith(".png"):
                        asset_map.setdefault(f"{name_key}.png", []).append(obj)
            except Exception:
                pass  # Skip objects that can't be read

        if container_by_path_id:
            for path_id, c_path in container_by_path_id.items():
                c_filename = os.path.basename(c_path).lower()
                target_obj = next((o for o in env.objects if getattr(o, "path_id", None) == path_id), None)
                if target_obj:
                    asset_map.setdefault(c_filename, []).append(target_obj)
                    if target_obj.type.name == "TextAsset":
                        if c_filename.endswith(".skel"):
                            asset_map.setdefault(f"{c_filename}.bytes", []).append(target_obj)
                        elif c_filename.endswith(".atlas"):
                            asset_map.setdefault(f"{c_filename}.txt", []).append(target_obj)

        # 直接使用索引中的檔案列表
        mod_files = file_index['all_files']
        total_assets = len(mod_files)
        
        # ========== 階段一：分類所有 mod 檔案 ==========
        report_progress("Phase 1: Categorizing mod files...")
        for folder in sorted({os.path.dirname(p) for p in mod_files}):
            for bad in mod_health.damaged_textures(folder):  # (a damaged skeleton fails in its own conversion below)
                report_progress(f"WARNING: {bad['file']}: {bad['reason']} Download the mod again for a complete result.")
        
        json_files = []      # JSON -> SKEL 轉換
        png_astc_files = []  # PNG -> ASTC 壓縮 (需平行處理)
        png_rgba_files = []  # PNG -> RGBA32 (不需壓縮)
        text_files = []      # TextAsset 替換
        
        for mod_filepath in mod_files:
            mod_filename = _game_name(os.path.basename(mod_filepath))
            
            if mod_filename.lower().endswith('.json'):
                base_name, _ = os.path.splitext(mod_filename)
                target_asset_name = (base_name + ".skel").lower()
                if _asset_objects(asset_map, target_asset_name, "TextAsset", container_by_path_id, spine_base_names):
                    json_files.append((mod_filepath, target_asset_name))
                    
            elif mod_filename.lower().endswith('.png'):
                target_asset_name = os.path.splitext(mod_filename)[0].lower()
                if _asset_objects(asset_map, target_asset_name, "Texture2D", container_by_path_id, spine_base_names):
                    if use_astc:
                        png_astc_files.append((mod_filepath, target_asset_name))
                    else:
                        png_rgba_files.append((mod_filepath, target_asset_name))
            else:
                target_asset_name = mod_filename.lower()
                if _asset_objects(asset_map, target_asset_name, "TextAsset", container_by_path_id, spine_base_names):
                    text_files.append((mod_filepath, target_asset_name))
        
        report_progress(f"  - JSON animations: {len(json_files)}")
        report_progress(f"  - ASTC textures: {len(png_astc_files)}")
        report_progress(f"  - RGBA32 textures: {len(png_rgba_files)}")
        report_progress(f"  - Text assets: {len(text_files)}")
        
        # ========== 階段二：處理 JSON 和 TextAsset (序列) ==========
        report_progress("Phase 2: Processing JSON and TextAsset files...")
        
        # 處理 JSON -> SKEL
        for i, (mod_filepath, target_asset_name) in enumerate(json_files):
            mod_filename = os.path.basename(mod_filepath)
            current_progress = f"(JSON {i+1}/{len(json_files)}) "
            
            try:
                report_progress(f"{current_progress}Converting animation: {mod_filename}")
                target_objects = _asset_objects(asset_map, target_asset_name, "TextAsset", container_by_path_id, spine_base_names)

                with tempfile.NamedTemporaryFile(delete=False, suffix=".skel") as tmp_skel_file:
                    temp_skel_path = tmp_skel_file.name
                
                try:
                    json_to_skel(mod_filepath, temp_skel_path)
                    with open(temp_skel_path, 'rb') as f:
                        skel_binary_data = skel_convert.to_current(f.read())  # json_to_skel writes 4.1; the game reads 4.2

                    for obj in target_objects:
                        data = obj.read()
                        data.m_Script = skel_binary_data.decode("utf-8", "surrogateescape")
                        data.save()
                        edited = True
                    report_progress(f"{current_progress}Successfully replaced: {mod_filename} -> {len(target_objects)} object(s)")
                finally:
                    if os.path.exists(temp_skel_path):
                        os.remove(temp_skel_path)
                        
            except Exception as e:
                import traceback
                report_progress(f"Error processing {mod_filename}: {traceback.format_exc()}")
        
        # 處理 TextAsset
        for i, (mod_filepath, target_asset_name) in enumerate(text_files):
            mod_filename = os.path.basename(mod_filepath)
            current_progress = f"(Text {i+1}/{len(text_files)}) "
            
            try:
                report_progress(f"{current_progress}Replacing asset: {mod_filename}")
                target_objects = _asset_objects(asset_map, target_asset_name, "TextAsset", container_by_path_id, spine_base_names)
                with open(mod_filepath, "rb") as f:
                    raw_asset = f.read()
                if mod_filepath.lower().endswith((".skel", ".skel.bytes")):
                    raw_asset = skel_convert.to_current(raw_asset)  # a mod exported for Spine 4.1 is converted for the game's 4.2
                new_script = raw_asset.decode("utf-8", "surrogateescape")

                for obj in target_objects:
                    data = obj.read()
                    data.m_Script = new_script
                    data.save()
                    edited = True
                
            except Exception as e:
                import traceback
                report_progress(f"Error processing {mod_filename}: {traceback.format_exc()}")
        
        # ========== 階段三：平行處理 ASTC 紋理壓縮 ==========
        # 優化策略：單一 Executor + 完成一個就立即寫入，控制記憶體峰值
        if png_astc_files:
            total_textures = len(png_astc_files)
            
            # Dynamic ASTC block footprint & format per quality (HD = 4x4, SD = 8x8)
            is_sd = str(quality).upper() == "SD"
            block_x, block_y = (8, 8) if is_sd else (4, 4)
            astc_format = 51 if is_sd else 48  # 51 = ASTC_RGB_8x8, 48 = ASTC_RGB_4x4
            quality_tag = "SD 8x8" if is_sd else "HD 4x4"
            
            report_progress(f"Phase 3: Parallel ASTC compression [{quality_tag}] ({total_textures} textures, {MAX_PARALLEL_TEXTURES} Process workers)...")
            
            total_success = 0
            total_failed = 0
            completed_count = 0
            
            # 準備所有 worker 參數
            worker_args = [
                (mod_filepath, target_asset_name, block_x, block_y)
                for mod_filepath, target_asset_name in png_astc_files
            ]
            
            try:
                with ProcessPoolExecutor(max_workers=MAX_PARALLEL_TEXTURES) as executor:
                    # 一次提交所有任務
                    future_to_args = {
                        executor.submit(_compress_texture_worker, args): args 
                        for args in worker_args
                    }
                    
                    # 完成一個就立即處理（寫入 + 清理）
                    for future in as_completed(future_to_args):
                        if is_cancelled and is_cancelled():
                            report_progress("Repack cancelled by user, aborting textures...")
                            for f in future_to_args:
                                f.cancel()
                            raise InterruptedError("Repack cancelled by user.")
                        completed_count += 1
                        args = future_to_args[future]
                        mod_filename = os.path.basename(args[0])
                        
                        try:
                            result = future.result()
                            
                            if result['success']:
                                # 立即寫入 Bundle
                                target_asset_name = result['target_asset_name']
                                try:
                                    target_objects = _asset_objects(asset_map, target_asset_name, "Texture2D", container_by_path_id, spine_base_names)
                                    for obj in target_objects:
                                        data = obj.read()
                                        
                                        data.m_TextureFormat = astc_format
                                        data.image_data = result['compressed_data']
                                        data.m_CompleteImageSize = len(result['compressed_data'])
                                        data.m_Width = result['width']
                                        data.m_Height = result['height']
                                        data.m_MipCount = 1
                                        
                                        if hasattr(data, 'm_StreamData'):
                                            data.m_StreamData.offset = 0
                                            data.m_StreamData.size = 0
                                            data.m_StreamData.path = ""
                                        
                                        data.save()
                                        edited = True
                                    total_success += len(target_objects)
                                    
                                except Exception as e:
                                    total_failed += 1
                                    report_progress(f"  Write error {mod_filename}: {e}")
                            else:
                                total_failed += 1
                                report_progress(f"  FAILED: {mod_filename} - {result['error']}")
                            
                            # 立即清理這個結果的記憶體
                            del result
                                
                        except Exception as e:
                            total_failed += 1
                            report_progress(f"  ERROR: {mod_filename} - {str(e)}")
                        
                        # 定期報告進度（每 25% 或每 10 個）
                        if total_textures <= 10 or completed_count == total_textures or completed_count % max(1, total_textures // 4) == 0:
                            report_progress(f"  Progress: {completed_count}/{total_textures} ({100*completed_count//total_textures}%)")
                        
                        # 定期執行 gc（每處理 10 個紋理）
                        if completed_count % 10 == 0:
                            gc.collect()
                            
            except Exception as e:
                report_progress(f"Executor failed, falling back to sequential: {e}")
                # 回退到序列處理
                for args in worker_args:
                    completed_count += 1
                    result = _compress_texture_worker(args)
                    
                    if result['success']:
                        target_asset_name = result['target_asset_name']
                        mod_filename = os.path.basename(result['mod_filepath'])
                        try:
                            target_objects = _asset_objects(asset_map, target_asset_name, "Texture2D", container_by_path_id, spine_base_names)
                            for obj in target_objects:
                                data = obj.read()
                                data.m_TextureFormat = astc_format
                                data.image_data = result['compressed_data']
                                data.m_CompleteImageSize = len(result['compressed_data'])
                                data.m_Width = result['width']
                                data.m_Height = result['height']
                                data.m_MipCount = 1
                                if hasattr(data, 'm_StreamData'):
                                    data.m_StreamData.offset = 0
                                    data.m_StreamData.size = 0
                                    data.m_StreamData.path = ""
                                data.save()
                                edited = True
                            total_success += len(target_objects)
                        except Exception as e:
                            total_failed += 1
                    else:
                        total_failed += 1
                        mod_filename = os.path.basename(args[0])
                        report_progress(f"  FAILED (seq): {mod_filename} - {result['error']}")
                    
                    del result
                    if completed_count % 10 == 0:
                        gc.collect()
            
            # 最終清理
            del worker_args
            gc.collect()
            
            # 最終報告
            report_progress(f"  ASTC compression complete: {total_success} success, {total_failed} failed")
        
        # ========== 處理 RGBA32 紋理 (不需壓縮，序列處理) ==========
        if png_rgba_files:
            report_progress(f"Processing RGBA32 textures ({len(png_rgba_files)})...")
            
            for i, (mod_filepath, target_asset_name) in enumerate(png_rgba_files):
                mod_filename = os.path.basename(mod_filepath)
                current_progress = f"(RGBA {i+1}/{len(png_rgba_files)}) "
                
                pil_img = None
                try:
                    report_progress(f"{current_progress}Processing: {mod_filename}")
                    target_objects = _asset_objects(asset_map, target_asset_name, "Texture2D", container_by_path_id, spine_base_names)
                    pil_img = Image.open(mod_filepath).convert("RGBA")

                    for obj in target_objects:
                        data = obj.read()
                        
                        data.m_TextureFormat = 4  # RGBA32
                        data.image = pil_img
                        
                        data.m_MipCount = 1
                        
                        if hasattr(data, 'm_StreamData'):
                            data.m_StreamData.offset = 0
                            data.m_StreamData.size = 0
                            data.m_StreamData.path = ""
                        
                        data.save()
                        edited = True
                    
                except Exception as e:
                    import traceback
                    report_progress(f"Error processing {mod_filename}: {traceback.format_exc()}")
                finally:
                    if pil_img:
                        pil_img.close()
                        del pil_img
        
        del asset_map
        del mod_files
        gc.collect()

        if edited:
            if is_cancelled and is_cancelled():
                raise InterruptedError("Repack cancelled by user.")
            report_progress("Saving modified game file...")
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            try:
                saved_bytes = env.file.save(packer="lz4")
                with open(output_path, "wb") as f:
                    f.write(saved_bytes)
                report_progress("Saved successfully!")
                return True, "Repack completed successfully."
            except Exception as e:
                error_msg = f"Error saving bundle: {e}"
                report_progress(error_msg)
                return False, error_msg
        else:
            error_msg = "No modifications were made: none of the mod's files match an asset in the resolved game bundle (the game may not have this asset yet, e.g. an idle for a character that only has a cutscene)."
            report_progress(error_msg)
            return False, error_msg

    except InterruptedError:
        if progress_callback:
            progress_callback("Repack aborted by user cancellation.")
        if os.path.exists(output_path):
            try: os.remove(output_path)
            except Exception: pass
        return False, "Repack cancelled by user."
    except Exception as e:
        import traceback
        error_message = traceback.format_exc()
        report_progress(f"Error processing bundle: {error_message}")
        return False, error_message
    finally:
        if env is not None:
            del env
        gc.collect()
