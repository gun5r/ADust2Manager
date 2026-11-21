"""Validation of persisted queue items."""
import os
from typing import Any, Dict, List, Tuple


class QueueMixin:
    def validate_queue_items(self, items: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Validates persistent queue items:
        - If queued/preparing: verifies source mod folders exist on disk.
        - If prepared: verifies repacked file exists on disk and is non-empty.
        Returns (validated_items, issues).
        """
        issues = []
        validated = []
        for it in items:
            item = dict(it)
            status = item.get("status", "queued")
            # If server or session stopped mid-operation, gracefully reset to stable states
            if status == "preparing":
                status = "queued"
                item["status"] = "queued"
                item["progress"] = 0
                item["progress_text"] = "Waiting to prepare..."
            elif status == "transferring":
                status = "prepared"
                item["status"] = "prepared"
                item["progress"] = 100
                item["progress_text"] = "Ready to Bundle & Transfer"

            if status == "queued":
                folders = item.get("mod_folders") or ([item.get("mod_folder")] if item.get("mod_folder") else [])
                missing = []
                for f in folders:
                    if not f:
                        continue
                    f_path = f
                    if not os.path.isabs(f_path):
                        f_path = os.path.join(self.workspace_dir, f_path)
                    if not os.path.exists(f_path):
                        missing.append(f)
                if missing:
                    err_msg = f"Source folder not found on disk: {missing[0]}"
                    item["status"] = "failed_prepare"
                    item["error"] = err_msg
                    item["missing_files"] = True
                    issues.append({"job_id": item.get("id"), "mod_name": item.get("mod_name"), "issue": err_msg})
                else:
                    item["missing_files"] = False
            elif status == "prepared":
                prep = item.get("prepared_data") or {}
                r_path = prep.get("repacked_path") or ""
                check_path = r_path
                if check_path and not os.path.isabs(check_path):
                    check_path = os.path.join(self.workspace_dir, check_path)
                if check_path and os.path.isdir(check_path):
                    check_path = os.path.join(check_path, "__data")
                if not check_path or not os.path.exists(check_path) or os.path.getsize(check_path) == 0:
                    err_msg = f"Repacked cache bundle missing or corrupted: {r_path or 'unknown'}"
                    item["status"] = "failed_prepare"
                    item["error"] = err_msg
                    item["missing_files"] = True
                    issues.append({"job_id": item.get("id"), "mod_name": item.get("mod_name"), "issue": err_msg})
                else:
                    item["missing_files"] = False

            # Ensure item and prepared_data have canonical asset_key populated
            if not item.get("asset_key"):
                item["asset_key"] = self.extract_mod_asset_key(item)
            if item.get("prepared_data") and isinstance(item["prepared_data"], dict):
                if not item["prepared_data"].get("asset_key"):
                    item["prepared_data"]["asset_key"] = item["asset_key"]

            validated.append(item)
        return validated, issues
