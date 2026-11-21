import os
import re
import shutil
import glob
from typing import Dict, List, Tuple, Optional, Any
from PIL import Image

import mod_health

def _parse_atlas(atlas_path: str, progress_callback=print) -> Optional[Dict[str, Any]]:
    """
    Parses a Spine .atlas file into a structured dictionary.
    Handles Spine 3.8 and Spine 4.x formats, Windows/Unix line endings,
    and isolates page header attributes (size, filter, format, repeat, pma)
    so they never get contaminated into sprite lists.
    """
    progress_callback(f"  Parsing atlas file: {os.path.basename(atlas_path)}")
    try:
        with open(atlas_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        with open(atlas_path, 'r', encoding='latin-1') as f:
            content = f.read()
    except Exception as e:
        progress_callback(f"  FATAL: Could not read atlas file at {atlas_path}: {e}")
        return None

    # Normalize line endings
    content = content.replace('\r\n', '\n').replace('\r', '\n')

    # Split into page blocks (each page begins with a filename, usually ending with .png)
    # Using regex to split at newlines followed by a non-indented image file line
    raw_blocks = re.split(r'\n(?=[^\n\s]+\.(?:png|PNG)\n)', content.strip())
    
    atlas_database = {}
    for block_text in raw_blocks:
        block_text = block_text.strip()
        if not block_text:
            continue

        lines = block_text.split('\n')
        block_name = lines[0].strip()

        header_props = {}
        sprite_lines = []
        in_sprites = False

        for line in lines[1:]:
            stripped = line.strip()
            if not stripped:
                continue

            if not in_sprites:
                match = re.match(r'^(size|format|filter|repeat|pma)\s*:', stripped, re.IGNORECASE)
                if match:
                    prop_name = match.group(1).lower()
                    header_props[prop_name] = line
                    continue
                else:
                    in_sprites = True

            sprite_lines.append(line)

        entry = {
            'original_name': block_name,
            'header_props': header_props,
            'size_line': header_props.get('size', 'size: 2048, 2048'),
            'filter_line': header_props.get('filter', 'filter: Linear, Linear'),
            'sprites': '\n'.join(sprite_lines)
        }
        # Index with lowercase key for case-insensitive lookup
        atlas_database[block_name.lower()] = entry

    progress_callback(f"  Successfully parsed {len(atlas_database)} atlas page blocks.")
    return atlas_database

def _get_sorted_pngs(base_dir: str, file_prefix: str) -> List[str]:
    """
    Scans directory for PNG files matching prefix case-insensitively,
    and returns them sorted naturally (base, _2, _3, ...).
    """
    prefix_lower = file_prefix.lower()
    matches = []

    for f in os.listdir(base_dir):
        f_lower = f.lower()
        if f_lower.startswith(prefix_lower) and f_lower.endswith('.png'):
            matches.append(f)

    def sort_key(filename: str):
        f_lower = filename.lower()
        if f_lower == f"{prefix_lower}.png":
            return 1
        m = re.search(r'_(\d+)\.png$', f_lower)
        if m:
            return int(m.group(1))
        return 999999

    matches.sort(key=sort_key)
    return matches

def _generate_operations(
    base_dir: str, 
    file_prefix: str, 
    target_count: Optional[int] = None, 
    progress_callback=print
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Generates merge operations.
    If target_count is provided, merges pngs down to that exact count.
    If target_count is None, performs pairwise merging.
    """
    png_files = _get_sorted_pngs(base_dir, file_prefix)
    progress_callback(f"  Found {len(png_files)} matching PNG files: {png_files}")

    if not png_files:
        return [], []

    source_pngs_for_backup = png_files[:]
    operations = []

    if target_count is not None and target_count > 0:
        if len(png_files) <= target_count:
            progress_callback(f"  Texture count ({len(png_files)}) is already <= target count ({target_count}). No merge needed.")
            return [], source_pngs_for_backup

        plan = {i: [] for i in range(target_count)}
        for idx, png_name in enumerate(png_files):
            plan[idx % target_count].append(png_name)

        for i in range(target_count):
            sources = plan[i]
            if not sources:
                continue
            out_name = f"{file_prefix}.png" if i == 0 else f"{file_prefix}_{i+1}.png"
            if len(sources) > 1:
                operations.append({"type": "merge", "sources": sources, "output": out_name})
            else:
                operations.append({"type": "copy", "sources": sources, "output": out_name})
    else:
        # Default pairwise merging (e.g. 7 textures -> 4 textures, 4 -> 2)
        i = 0
        pair_index = 1
        while i < len(png_files):
            if pair_index == 1:
                output_filename = f"{file_prefix}.png"
            else:
                output_filename = f"{file_prefix}_{pair_index}.png"

            if i + 1 < len(png_files):
                operations.append({
                    "type": "merge",
                    "sources": [png_files[i], png_files[i + 1]],
                    "output": output_filename
                })
                i += 2
            else:
                operations.append({
                    "type": "copy",
                    "sources": [png_files[i]],
                    "output": output_filename
                })
                i += 1
            pair_index += 1

    progress_callback("  Generated operations:")
    for op in operations:
        progress_callback(f"    - {op['type'].upper()}: {op['sources']} -> {op['output']}")

    return operations, source_pngs_for_backup

def has_backup(mod_dir_path: str) -> bool:
    """Checks if .old backup directory exists and has files."""
    old_dir = os.path.join(mod_dir_path, ".old")
    if os.path.isdir(old_dir):
        return len(os.listdir(old_dir)) > 0
    return False

def revert_merge(mod_dir_path: str, progress_callback=print) -> Tuple[bool, str]:
    """
    Reverts a previous spine merge by restoring the original files from .old/.
    """
    old_dir = os.path.join(mod_dir_path, ".old")
    if not os.path.isdir(old_dir):
        return False, "No .old backup folder found to revert from."

    backup_files = os.listdir(old_dir)
    if not backup_files:
        return False, "The .old backup directory is empty."

    progress_callback(f"Reverting Spine merge in: {mod_dir_path}")

    # Remove any existing merged pngs and atlas files currently in mod_dir_path
    for f in os.listdir(mod_dir_path):
        if f == ".old" or f.startswith("."):
            continue
        p = os.path.join(mod_dir_path, f)
        if os.path.isfile(p) and f.lower().endswith(('.png', '.atlas', '.atlas.txt')):
            try:
                os.remove(p)
            except Exception as e:
                progress_callback(f"  Warning: could not remove merged file {f}: {e}")

    # Move all files from .old back into mod_dir_path
    for f in backup_files:
        src = os.path.join(old_dir, f)
        dst = os.path.join(mod_dir_path, f)
        shutil.move(src, dst)
        progress_callback(f"  Restored: {f}")

    try:
        shutil.rmtree(old_dir)
    except Exception:
        pass

    progress_callback("Revert completed successfully! Original files restored.")
    return True, "Revert completed successfully! Original files restored."

def run(
    mod_dir_path: str, 
    target_count: Optional[int] = None, 
    progress_callback=print
) -> Tuple[bool, str]:
    """
    Processes all Spine assets for a single mod directory in-place:
    1. Backs up original textures and atlas to .old/
    2. Horizontally stitches images side-by-side
    3. Corrects coordinate offsets for both bounds: (Spine 4) and xy: (Spine 3.8)
    4. Writes cleaned, valid .atlas file
    """
    progress_callback(f"\n--- Processing Spine Merge for: {os.path.basename(mod_dir_path)} ---")

    atlas_files = [f for f in os.listdir(mod_dir_path) if f.lower().endswith(('.atlas', '.atlas.txt'))]
    if not atlas_files:
        return False, "SKIPPING: No .atlas file found in directory."

    original_atlas_path = os.path.join(mod_dir_path, atlas_files[0])
    file_prefix = os.path.splitext(os.path.basename(original_atlas_path))[0].lower()

    # A cut-off texture would be merged as if its missing rows were empty, and the damage could never be told from the art afterwards.
    damaged = [d["file"] for d in mod_health.damaged_textures(mod_dir_path)]
    if damaged:
        return False, f"FAILED: {', '.join(damaged)} {'is' if len(damaged) == 1 else 'are'} cut off (an incomplete download), so merging would lose parts of the model for good. Download the mod again."

    # 1. Generate operations and list of pngs to process
    operations, all_source_pngs = _generate_operations(
        mod_dir_path, file_prefix, target_count=target_count, progress_callback=progress_callback
    )
    if not operations:
        return False, "SKIPPING: No image operations to perform or already at target count."

    # 2. Parse original Atlas
    atlas_db = _parse_atlas(original_atlas_path, progress_callback)
    if not atlas_db:
        return False, "FAILED: Could not parse atlas file."

    # 3. Create .old directory and move original files
    old_dir = os.path.join(mod_dir_path, ".old")
    os.makedirs(old_dir, exist_ok=True)
    progress_callback(f"  Backup directory: {old_dir}")

    # Move original atlas to .old
    backup_atlas_path = os.path.join(old_dir, os.path.basename(original_atlas_path))
    if not os.path.exists(backup_atlas_path):
        shutil.move(original_atlas_path, backup_atlas_path)

    # Move all source pngs to .old
    for png_file in all_source_pngs:
        src = os.path.join(mod_dir_path, png_file)
        dst = os.path.join(old_dir, png_file)
        if os.path.exists(src) and not os.path.exists(dst):
            shutil.move(src, dst)
    progress_callback(f"  Moved original atlas and {len(all_source_pngs)} PNG files to .old backup.")

    final_atlas_blocks = []

    # 4. Process all operations
    for op in operations:
        op_type = op['type']
        sources = op['sources']
        output_name = op['output'].lower()
        output_path = os.path.join(mod_dir_path, output_name)

        if op_type == 'copy':
            source_file = sources[0]
            source_path = os.path.join(old_dir, source_file)

            # Ensure dimensions are divisible by 4 for ASTC block alignment
            with Image.open(source_path) as s_img:
                s_w, s_h = s_img.size
                aligned_w = ((s_w + 3) // 4) * 4
                aligned_h = ((s_h + 3) // 4) * 4
                needs_alignment = (aligned_w != s_w or aligned_h != s_h)
                
                if needs_alignment:
                    aligned_img = Image.new('RGBA', (aligned_w, aligned_h))
                    aligned_img.paste(s_img, (0, 0))
                    aligned_img.save(output_path)
                    progress_callback(f"  Padded copy {source_file} -> {output_name} ({s_w}x{s_h} -> {aligned_w}x{aligned_h})")
                else:
                    shutil.copy(source_path, output_path)
                    progress_callback(f"  Copied {source_file} -> {output_name}")

            source_data = atlas_db.get(source_file.lower())
            if source_data:
                header_lines = [output_name]
                header_lines.append(f"size: {aligned_w}, {aligned_h}")
                for prop in ['format', 'filter', 'repeat', 'pma']:
                    if prop in source_data['header_props']:
                        header_lines.append(source_data['header_props'][prop])
                
                block_content = '\n'.join(header_lines) + '\n' + source_data['sprites']
                final_atlas_blocks.append(block_content.strip())

        elif op_type == 'merge':
            # Load all images in this merge group from .old
            loaded_images = []
            for src_name in sources:
                src_p = os.path.join(old_dir, src_name)
                img = Image.open(src_p)
                img.load()
                loaded_images.append((src_name, img))

            # Compute combined dimensions and align to 4 for ASTC block alignment
            raw_width = sum(img.width for _, img in loaded_images)
            raw_height = max(img.height for _, img in loaded_images)
            aligned_width = ((raw_width + 3) // 4) * 4
            aligned_height = ((raw_height + 3) // 4) * 4

            new_img = Image.new('RGBA', (aligned_width, aligned_height))
            curr_x = 0
            offsets = {}

            for src_name, img in loaded_images:
                offsets[src_name.lower()] = curr_x
                new_img.paste(img, (curr_x, 0))
                curr_x += img.width

            new_img.save(output_path)
            progress_callback(f"  Merged {len(sources)} images -> {output_name} ({aligned_width}x{aligned_height})")

            # Clean up images to free memory
            for _, img in loaded_images:
                img.close()

            # Build merged atlas page block
            primary_src_name = sources[0].lower()
            primary_data = atlas_db.get(primary_src_name)
            if not primary_data:
                continue

            header_lines = [output_name]
            header_lines.append(f"size: {aligned_width}, {aligned_height}")
            if 'format' in primary_data['header_props']:
                header_lines.append(primary_data['header_props']['format'])
            filter_val = primary_data['header_props'].get('filter', 'filter: Linear, Linear')
            header_lines.append(filter_val)
            if 'repeat' in primary_data['header_props']:
                header_lines.append(primary_data['header_props']['repeat'])
            if 'pma' in primary_data['header_props']:
                header_lines.append(primary_data['header_props']['pma'])

            # Collect sprites with proper coordinate offsets
            merged_sprites = []
            for src_name in sources:
                src_data = atlas_db.get(src_name.lower())
                if not src_data:
                    continue

                offset_x = offsets[src_name.lower()]
                if offset_x == 0:
                    merged_sprites.append(src_data['sprites'])
                else:
                    modified = []
                    for line in src_data['sprites'].split('\n'):
                        stripped = line.strip()
                        if stripped.startswith('bounds:'):
                            try:
                                parts = stripped.split(':')
                                coords = [int(c.strip()) for c in parts[1].split(',')]
                                x, y, w, h = coords
                                x += offset_x
                                indent = line[:line.find('bounds:')]
                                modified.append(f"{indent}bounds: {x}, {y}, {w}, {h}")
                            except Exception:
                                modified.append(line)
                        elif stripped.startswith('xy:'):
                            try:
                                parts = stripped.split(':')
                                coords = [int(c.strip()) for c in parts[1].split(',')]
                                x, y = coords
                                x += offset_x
                                indent = line[:line.find('xy:')]
                                modified.append(f"{indent}xy: {x}, {y}")
                            except Exception:
                                modified.append(line)
                        else:
                            modified.append(line)
                    merged_sprites.append('\n'.join(modified))

            block_content = '\n'.join(header_lines) + '\n' + '\n'.join(merged_sprites)
            final_atlas_blocks.append(block_content.strip())

    # 5. Write final Atlas file
    final_atlas_path = os.path.join(mod_dir_path, f"{file_prefix}.atlas")
    progress_callback(f"  Writing final atlas file to: {final_atlas_path}")
    with open(final_atlas_path, 'w', encoding='utf-8') as f:
        f.write('\n\n'.join(final_atlas_blocks) + '\n')

    msg = f"Successfully merged Spine textures in {os.path.basename(mod_dir_path)} down to {len(operations)} sheets."
    progress_callback(f"  {msg}")
    return True, msg
