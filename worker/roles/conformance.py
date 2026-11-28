"""계약 적합성 검사 (AI 설계 11.4 '폴더와 테스트'). 모든 역할 모듈의 테스트가 이 함수들을 부른다.

임시본 (2026-11-25). 각 함수는 문제 목록(빈 목록이면 통과)을 돌려준다.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

from typing import get_args

from .contract import CONTRACT_VERSION, AITask, DocRole, DocumentRef, RoleContext, RoleModule

# 역할 모듈이 import하면 안 되는 것: 공통 엔진, DB 드라이버, 네트워크, 모델 SDK
FORBIDDEN_IMPORTS = {"gateway", "providers", "psycopg", "psycopg2", "asyncpg", "sqlalchemy", "requests", "httpx",
                     "urllib", "urllib3", "socket", "aiohttp", "http", "openai", "anthropic", "boto3", "botocore"}
# 스키마 허용 범위: Luna strict와 Haiku 도구 강제가 함께 받는 부분 (description은 의미 없는 주석이라 허용)
SCHEMA_KEYS = {"type", "enum", "items", "properties", "required", "additionalProperties", "description"}
SCHEMA_TYPES = {"object", "array", "string", "number", "integer", "boolean"}


def check_imports(package_dir: Path) -> list[str]:
    """패키지 안 .py (tests 제외)의 import와 os.environ·os.getenv 사용을 AST로 검사."""
    probs = []
    pkg = package_dir.name
    for f in sorted(package_dir.rglob("*.py")):
        if "tests" in f.relative_to(package_dir).parts:
            continue
        tree = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                if node.level >= 2 and mod and mod.split(".")[0] not in ("contract",):
                    probs.append(f"{f.name}: 다른 역할 패키지 import ({'.' * node.level}{mod})")
                names = [mod] if node.level == 0 else []
            for n in names:
                parts = n.split(".")
                if parts[0] in FORBIDDEN_IMPORTS or (len(parts) > 1 and parts[0] == "worker" and parts[1] == "gateway"):
                    probs.append(f"{f.name}: 금지 import {n}")
                if n.startswith("worker.roles.") and parts[2] not in ("contract", pkg):
                    probs.append(f"{f.name}: 다른 역할 패키지 import {n}")
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "os" \
                    and node.attr in ("environ", "getenv", "putenv"):
                probs.append(f"{f.name}: os.{node.attr} 사용")
    return probs


def check_schema(schema: dict, path: str = "$") -> list[str]:
    probs = []
    extra = set(schema) - SCHEMA_KEYS
    if extra:
        probs.append(f"{path}: 허용 밖 키워드 {sorted(extra)}")
    t = schema.get("type")
    if t not in SCHEMA_TYPES:
        probs.append(f"{path}: type {t!r}")
    if t == "object":
        props = schema.get("properties", {})
        if set(schema.get("required", [])) != set(props):
            probs.append(f"{path}: required가 모든 속성과 같지 않음")
        if schema.get("additionalProperties") is not False:
            probs.append(f"{path}: additionalProperties가 false가 아님")
        for k, v in props.items():
            probs += check_schema(v, f"{path}.{k}")
    if t == "array":
        probs += check_schema(schema.get("items", {}), f"{path}[]")
    return probs


def check_tasks(tasks: list[AITask], ctx: RoleContext, module: RoleModule) -> list[str]:
    probs = []
    keys = [t.target_key for t in tasks]
    if len(keys) != len(set(keys)):
        probs.append("target_key 중복")
    limit = ctx.limits().max_prompt_tokens
    for t in tasks:
        if t.role != module.role:
            probs.append(f"{t.target_key}: role {t.role}")
        text = "".join(p.text or "" for p in t.parts)
        if "\x00" in text:
            probs.append(f"{t.target_key}: parts에 바이너리")
        if any(p.kind == "image" and not p.image_key for p in t.parts):
            probs.append(f"{t.target_key}: 이미지 조각에 image_key 없음")
        if ctx.count_tokens(module.system_prompt + text) > limit:
            probs.append(f"{t.target_key}: 프롬프트 토큰이 max_prompt_tokens({limit}) 초과")
        if t.private and json.dumps(t.private, ensure_ascii=False, sort_keys=True) in text:
            probs.append(f"{t.target_key}: private이 parts에 그대로 들어감")
        if t.source is None:
            probs.append(f"{t.target_key}: source 없음 (문서 역할은 원본 위치가 있어야 함)")
    return probs


def check_document_roles(module) -> list[str]:
    """계약 1.1: document_roles는 비어 있지 않은 DocRole 튜플. 1.0의 document_role(단수)이 남아 있으면 문제."""
    probs = []
    roles = getattr(module, "document_roles", None)
    if hasattr(module, "document_role"):
        probs.append("document_role(단수)은 계약 1.1에서 document_roles로 바뀜")
    if not isinstance(roles, tuple) or not roles:
        probs.append(f"document_roles {roles!r}: 비어 있지 않은 튜플이어야 함")
    else:
        bad = [r for r in roles if r not in get_args(DocRole)]
        if bad:
            probs.append(f"document_roles에 없는 문서 역할 {bad}")
        if len(set(roles)) != len(roles):
            probs.append("document_roles 중복")
    return probs


def check_prepare_deterministic(module: RoleModule, ctx: RoleContext, doc: DocumentRef) -> list[str]:
    a = [t.model_dump() for t in module.prepare(ctx, doc)]
    b = [t.model_dump() for t in module.prepare(ctx, doc)]
    return [] if a == b else ["같은 입력으로 prepare 결과가 다름 (G6)"]


def check_module(module: RoleModule, package_dir: Path, ctx: RoleContext, docs: list[DocumentRef]) -> list[str]:
    """한 역할 모듈의 계약 적합성 전부."""
    probs = []
    if not isinstance(module, RoleModule):
        probs.append("RoleModule 속성·메서드 부족")
    probs += check_document_roles(module)
    if str(getattr(module, "contract_version", "")).split(".")[0] != CONTRACT_VERSION.split(".")[0]:
        probs.append(f"contract_version {getattr(module, 'contract_version', None)!r}: 주 번호가 {CONTRACT_VERSION}과 다름")
    probs += check_imports(package_dir)
    probs += check_schema(module.schema)
    for d in docs:
        if d.role not in getattr(module, "document_roles", ()):
            continue
        probs += check_prepare_deterministic(module, ctx, d)
        probs += check_tasks(module.prepare(ctx, d), ctx, module)
    return probs
