"""Atlas file parsing utilities."""
import re
import os
from typing import Dict, Optional, Tuple, Any


def parse_atlas_file(atlas_path: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Parse a .atlas file into a structured dictionary.
    Handles Spine 3.8 and Spine 4.x formats, Windows/Unix line endings,
    and isolates page header attributes (size, filter, format, repeat, pma).
    
    Args:
        atlas_path: Path to the .atlas file
        
    Returns:
        Tuple of (atlas_database dict, error message)
        If successful, returns (dict, None)
        If failed, returns (None, error_message)
    """
    atlas_database = {}
    
    try:
        with open(atlas_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        try:
            with open(atlas_path, 'r', encoding='latin-1') as f:
                content = f.read()
        except Exception as e:
            return None, f"Error decoding atlas file: {e}"
    except FileNotFoundError:
        return None, f"Atlas file not found at {atlas_path}"
    except Exception as e:
        return None, f"Error reading atlas file: {e}"

    # Normalize line endings
    content = content.replace('\r\n', '\n').replace('\r', '\n')

    # Split content into blocks (one per PNG image)
    blocks = re.split(r'\n(?=[^\n\s]+\.(?:png|PNG)\n)', content.strip())
    
    for block_text in blocks:
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
                    header_props[match.group(1).lower()] = line
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
        # Provide both original and lower-case keys for compatibility
        atlas_database[block_name] = entry
        atlas_database[block_name.lower()] = entry
    
    return atlas_database, None
