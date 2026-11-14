"""Product platform repo, catalog check and impact (ASP-050, ASP-051), stdlib only.

`catalog/product.json`:
  {"product": str,
   "modules":      [{"id", "repo"}],
   "capabilities": [{"id", "owner", "modules": [...], "specs": ["<module>:<path>" | "<path>"]}],
   "interfaces":   [{"id", "contract": "<path>" | "<module>:<path>", "provider", "consumers": [...]}],
   "data":         [{"id", "owner", "writers": [...], "readers": [...]}]}
A "<module>:<path>" reference is checked when that module's checkout sits next to the platform repo
(folder = last part of its "repo"); otherwise only the module is checked.
"""
from __future__ import annotations

import json
from pathlib import Path

KINDS = ("modules", "capabilities", "interfaces", "data")


class CatalogError(RuntimeError):
    """The catalog cannot be read."""


def skeleton(product: str) -> dict:
    return {"product": product, "modules": [], "capabilities": [], "interfaces": [], "data": []}


def load(platform: Path) -> dict:
    path = platform / "catalog" / "product.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CatalogError(f"{path}: {exc}") from exc
    if not isinstance(data, dict):
        raise CatalogError(f"{path}: must be a JSON object")
    return data


def _resolve(platform: Path, modules: dict[str, dict], ref: str) -> tuple[str, Path | None]:
    """('', path) for a platform-relative path; (module, path or None) for '<module>:<path>'."""
    if ":" in ref:
        module, rel = ref.split(":", 1)
        repo = modules.get(module, {}).get("repo", "")
        checkout = platform.parent / repo.rsplit("/", 1)[-1] if repo else None
        return module, (checkout / rel) if checkout and checkout.is_dir() else None
    return "", platform / ref


def check(platform: Path) -> list[str]:
    data = load(platform)
    problems: list[str] = []
    for kind in KINDS:
        if not isinstance(data.get(kind, []), list):
            problems.append(f"'{kind}' must be a list")
    seen: set[str] = set()
    for kind in KINDS:
        for entry in data.get(kind, []):
            eid = entry.get("id", "")
            if not eid:
                problems.append(f"{kind}: an entry has no id")
            elif eid in seen:
                problems.append(f"{kind}: duplicated id '{eid}'")
            seen.add(eid)
    modules = {m.get("id"): m for m in data.get("modules", [])}

    def need_module(where: str, mid: str) -> None:
        if mid not in modules:
            problems.append(f"{where}: unknown module '{mid}'")

    def need_path(where: str, ref: str) -> None:
        module, path = _resolve(platform, modules, ref)
        if module:
            need_module(where, module)
        if path is not None and not path.exists():
            problems.append(f"{where}: '{ref}' does not exist")

    for cap in data.get("capabilities", []):
        where = f"capability '{cap.get('id')}'"
        need_module(where, cap.get("owner", ""))
        for mid in cap.get("modules", []):
            need_module(where, mid)
        for ref in cap.get("specs", []):
            need_path(where, ref)
    for itf in data.get("interfaces", []):
        where = f"interface '{itf.get('id')}'"
        need_module(where, itf.get("provider", ""))
        for mid in itf.get("consumers", []):
            need_module(where, mid)
        if not itf.get("contract"):
            problems.append(f"{where}: no contract")
        else:
            need_path(where, itf["contract"])
    for asset in data.get("data", []):
        where = f"data '{asset.get('id')}'"
        need_module(where, asset.get("owner", ""))
        for mid in [*asset.get("writers", []), *asset.get("readers", [])]:
            need_module(where, mid)
    return problems


def impact(platform: Path, target: str) -> dict[str, list[str]]:
    """Everything that references `target` (a module, capability, interface, data or contract id), by kind."""
    data = load(platform)
    found: dict[str, list[str]] = {k: [] for k in (*KINDS, "specs", "contracts")}
    interfaces = data.get("interfaces", [])
    related_modules = {target}
    for itf in interfaces:
        if itf.get("id") == target or target in itf.get("contract", ""):
            related_modules.update([itf.get("provider", ""), *itf.get("consumers", [])])
    for mod in data.get("modules", []):
        if mod.get("id") in related_modules:
            found["modules"].append(mod["id"])
    for cap in data.get("capabilities", []):
        if cap.get("id") == target or related_modules & {cap.get("owner"), *cap.get("modules", [])}:
            found["capabilities"].append(cap["id"])
            found["specs"].extend(cap.get("specs", []))
    for itf in interfaces:
        if itf.get("id") == target or target in itf.get("contract", "") or \
                related_modules & {itf.get("provider"), *itf.get("consumers", [])}:
            found["interfaces"].append(itf["id"])
            found["contracts"].append(itf.get("contract", ""))
    for asset in data.get("data", []):
        if asset.get("id") == target or related_modules & {asset.get("owner"), *asset.get("writers", []),
                                                           *asset.get("readers", [])}:
            found["data"].append(asset["id"])
    return {k: sorted(set(v)) for k, v in found.items() if v}
