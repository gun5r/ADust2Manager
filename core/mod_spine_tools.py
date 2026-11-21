"""Filename sanitising and Spine merge/revert helpers."""
import os
import re
import spine_merger
import tempfile
from typing import Optional, Tuple


class SpineToolsMixin:
    def sanitize_mod_filenames(self, mod_folder: str, log_cb=None) -> Tuple[bool, str]:
        """
        Ensures all files in the mod directory and references inside .atlas
        are strictly lowercase (per Android / Linux ext4 filesystem requirements).
        """
        if not os.path.exists(mod_folder):
            return False, f"Folder {mod_folder} does not exist"

        renamed_count = 0
        for root, _, files in os.walk(mod_folder):
            if ".old" in root or ".bak" in root:
                continue
            for f in files:
                if f.startswith("."):
                    continue
                f_lower = f.lower()
                if f != f_lower:
                    old_path = os.path.join(root, f)
                    new_path = os.path.join(root, f_lower)
                    if os.path.exists(new_path) and not os.path.samefile(old_path, new_path):
                        return False, f"Cannot lowercase {f}: {f_lower} already exists"
                    # Temporary rename for safety
                    descriptor, temp_path = tempfile.mkstemp(prefix=".rename-", dir=root)
                    os.close(descriptor)
                    try:
                        os.replace(old_path, temp_path)
                        os.replace(temp_path, new_path)
                        renamed_count += 1
                        if log_cb: log_cb(f"Renamed {f} -> {f_lower}")
                    except OSError as e:
                        if os.path.exists(temp_path) and not os.path.exists(old_path):
                            os.replace(temp_path, old_path)
                        elif os.path.exists(temp_path):
                            os.unlink(temp_path)
                        return False, f"Could not rename {f} to {f_lower}: {e}"

        # Update .atlas files
        atlas_updated = 0
        for root, _, files in os.walk(mod_folder):
            if ".old" in root:
                continue
            for f in files:
                if f.lower().endswith(('.atlas', '.atlas.txt')):
                    atlas_path = os.path.join(root, f)
                    try:
                        with open(atlas_path, "r", encoding="utf-8") as af:
                            content = af.read()
                        
                        lines = content.splitlines()
                        modified = False
                        new_lines = []
                        for line in lines:
                            if re.search(r'\.(?:png|PNG)\b', line):
                                lower_line = line.lower()
                                if lower_line != line:
                                    modified = True
                                    new_lines.append(lower_line)
                                else:
                                    new_lines.append(line)
                            else:
                                new_lines.append(line)

                        if modified:
                            with open(atlas_path, "w", encoding="utf-8") as af:
                                af.write("\n".join(new_lines) + "\n")
                            atlas_updated += 1
                            if log_cb: log_cb(f"Normalized texture references in {f} to lowercase.")
                    except Exception as e:
                        if log_cb: log_cb(f"Warning updating atlas {f}: {e}")

        msg = f"Sanitized mod: {renamed_count} files renamed to lowercase, {atlas_updated} atlas files updated."
        if log_cb: log_cb(msg)
        return True, msg

    def merge_spine_mod(self, mod_folder: str, target_count: Optional[int] = None, log_cb=None) -> Tuple[bool, str]:
        """
        Manually runs Spine merge on the mod directory.
        """
        self.sanitize_mod_filenames(mod_folder, log_cb)
        return spine_merger.run(mod_folder, target_count=target_count, progress_callback=log_cb or print)

    def revert_spine_mod(self, mod_folder: str, log_cb=None) -> Tuple[bool, str]:
        """
        Restores original files from .old backup.
        """
        return spine_merger.revert_merge(mod_folder, progress_callback=log_cb or print)
