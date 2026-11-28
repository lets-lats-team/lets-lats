"""roles/*/module.py의 MODULE을 찾아 등록한다 (AI 설계 11.4 '폴더와 테스트').

임시본 (2026-11-25). 없는 역할은 감독이 건너뛴다. 계약 주 번호가 다른 모듈은 등록하지 않는다.
"""
from __future__ import annotations

import importlib
from pathlib import Path

from .contract import CONTRACT_VERSION, RoleModule

ROOT = Path(__file__).resolve().parent


def _major(v: str) -> str:
    return v.split(".")[0]


def discover() -> dict[str, RoleModule]:
    out: dict[str, RoleModule] = {}
    for f in sorted(ROOT.glob("*/module.py")):
        mod = importlib.import_module(f"{__package__}.{f.parent.name}.module")
        m = getattr(mod, "MODULE", None)
        if m is None or not isinstance(m, RoleModule):
            continue
        if _major(m.contract_version) != _major(CONTRACT_VERSION):
            continue
        out[m.role] = m
    return out


def module_files() -> dict[str, Path]:
    """역할 패키지 폴더 이름 → module.py 경로 (계약 적합성 AST 검사용)."""
    return {f.parent.name: f for f in sorted(ROOT.glob("*/module.py"))}
