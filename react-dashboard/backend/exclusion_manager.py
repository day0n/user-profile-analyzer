import json
import os
from typing import List, Dict

EXCLUSION_FILE = os.path.join(os.path.dirname(__file__), "exclusion.json")

class ExclusionManager:
    def __init__(self):
        self._ensure_file()

    def _ensure_file(self):
        if not os.path.exists(EXCLUSION_FILE):
             self._save({"charts": [], "list": []})

    def load(self) -> Dict[str, List[str]]:
        try:
            with open(EXCLUSION_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading exclusion file: {e}")
            return {"charts": [], "list": []}

    def _save(self, data: Dict[str, List[str]]):
        try:
            with open(EXCLUSION_FILE, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving exclusion file: {e}")

    def add(self, email: str, exclude_charts: bool, exclude_list: bool):
        data = self.load()
        changed = False
        if exclude_charts and email not in data["charts"]:
            data["charts"].append(email)
            changed = True
        if exclude_list and email not in data["list"]:
            data["list"].append(email)
            changed = True
        
        if changed:
            self._save(data)

    def remove(self, email: str):
        data = self.load()
        changed = False
        if email in data["charts"]:
            data["charts"].remove(email)
            changed = True
        if email in data["list"]:
            data["list"].remove(email)
            changed = True
        
        if changed:
            self._save(data)

    def get_exclusions(self) -> Dict[str, List[str]]:
        return self.load()

exclusion_manager = ExclusionManager()
