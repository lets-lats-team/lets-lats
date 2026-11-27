"""L2(내역서)·L3(시방서) 정답셋 v0.1 세팅.

03_수집_3년의 공사 폴더에서 고른 세트의 내역서·시방서를 복사하고, 사람이 정답을 달 양식을 만든다.
정답 칸은 비워 둔다 (사람이 채움). 원본 폴더는 바꾸지 않는다.

  python prepare_text_kit.py            # 기본 5세트
  python prepare_text_kit.py --force    # 이미 있는 세트도 다시 만듦 (정답 양식은 덮어쓰지 않음)

결과: data/text_v0.1/
  manifest.json
  LABELING_GUIDE.md                  (손으로 관리)
  sets/<공고번호>/boq/  spec/  spec_text/
  labels/<공고번호>/l2_sheets.csv  l2_columns.csv  l2_rows.csv  l3_rules.csv
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

HERE = Path(__file__).resolve().parent
COLLECT = Path(os.environ.get("LETS_DATA_ROOT") or HERE.parents[1]) / "03_수집_3년"   # 환경 변수 LETS_DATA_ROOT, 없으면 lets-lats의 상위 폴더

# (공고번호, 구간 폴더, 고른 이유)
SETS = [
    ("R26BK01755909", "2026", "내역서 xlsx(관경별 총길이) + 시방서 HWP + DWG 있음. 나중에 도면까지 세 문서 대조 가능"),
    ("R26BK01598247", "2026", "시방서가 글자층 있는 PDF(5쪽). 내역서 xlsx(관경별 총길이)"),
    ("R26BK01667231", "2026", "내역서가 관경별(구간 반복) 형태. 교육청 양식. 시방서 HWP"),
    ("R26BK01551859", "2026", "시방서가 HWPX. 내역서 xlsx(관경별 총길이)"),
    ("R26BK01538810", "2026", "내역서가 옛 형식 .xls (openpyxl로 못 읽음). 시방서 HWP"),
]

BOQ_EXT = {".xlsx", ".xls"}
SPEC_EXT = {".hwp", ".hwpx", ".pdf"}
HEADER_KEYS = ("품명", "명칭", "공종")  # 내역서 머리글은 "품       명"처럼 글자 사이 공백이 많아 공백을 지우고 비교
UNIT_KEYS = ("단위",)
PREVIEW_COLS = 12


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def find_folder(notice: str, year: str) -> Path:
    hits = list((COLLECT / year).glob(f"{notice}_*"))
    if not hits:
        raise SystemExit(f"공사 폴더를 찾지 못함: {year}/{notice}_*")
    return hits[0]


def copy_unique(files: list[Path], dest: Path) -> list[dict]:
    """같은 내용(해시)의 중복 파일은 한 번만 복사한다."""
    dest.mkdir(parents=True, exist_ok=True)
    seen, out = set(), []
    for p in sorted(files):
        h = sha256(p)
        if h in seen:
            continue
        seen.add(h)
        target = dest / p.name
        shutil.copyfile(p, target)
        out.append({"file": p.name, "sha256": h, "bytes": p.stat().st_size, "source": str(p.relative_to(COLLECT))})
    return out


# ---------- 시방서 글자 추출 (정답 달 때 보는 참고용) ----------

def hwp_text(p: Path) -> str:
    r = subprocess.run(["hwp5txt", str(p)], capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.decode("utf-8", "replace")[:300])
    return r.stdout.decode("utf-8", "replace")


def hwpx_text(p: Path) -> str:
    lines = []
    with zipfile.ZipFile(p) as z:
        names = sorted(n for n in z.namelist() if re.match(r"Contents/section\d+\.xml$", n))
        for n in names:
            root = ET.fromstring(z.read(n))
            for para in root.iter():
                if para.tag.endswith("}p"):
                    t = "".join(x.text or "" for x in para.iter() if x.tag.endswith("}t"))
                    if t.strip():
                        lines.append(t)
    return "\n".join(lines)


def pdf_text(p: Path) -> str:
    import pymupdf
    doc = pymupdf.open(p)
    return "\n".join(f"===== {i + 1}쪽 =====\n{doc[i].get_text()}" for i in range(doc.page_count))


def extract_spec_text(p: Path) -> tuple[str, str | None]:
    ext = p.suffix.lower()
    try:
        if ext == ".hwp":
            return hwp_text(p), None
        if ext == ".hwpx":
            return hwpx_text(p), None
        if ext == ".pdf":
            return pdf_text(p), None
    except Exception as e:  # noqa: BLE001 - 추출 실패는 기록만 하고 계속
        return "", f"{type(e).__name__}: {str(e)[:200]}"
    return "", "지원하지 않는 형식"


# ---------- 내역서 읽기 ----------

def read_workbook(p: Path) -> dict[str, list[list[str]]]:
    """시트명 → 행 목록(셀 문자열). 수식은 저장된 계산값으로 읽는다."""
    sheets: dict[str, list[list[str]]] = {}
    if p.suffix.lower() == ".xlsx":
        import openpyxl
        wb = openpyxl.load_workbook(p, data_only=True, read_only=True)
        for ws in wb.worksheets:
            rows = []
            for r in ws.iter_rows(values_only=True):
                rows.append(["" if v is None else str(v).strip() for v in r])
            sheets[ws.title] = rows
        wb.close()
    else:
        import xlrd
        wb = xlrd.open_workbook(str(p))
        for ws in wb.sheets():
            rows = []
            for i in range(ws.nrows):
                rows.append([_xls_cell(ws.cell(i, j)) for j in range(ws.ncols)])
            sheets[ws.name] = rows
    # 끝쪽 빈 행 제거
    for k, rows in sheets.items():
        while rows and not any(rows[-1]):
            rows.pop()
    return sheets


def _xls_cell(c) -> str:
    v = c.value
    if v in (None, ""):
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def col_letter(i: int) -> str:
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def detect_header_row(rows: list[list[str]]) -> int | None:
    """품명·단위가 같은 행에 있는 첫 행 (1부터 셈). 양식 작성을 돕는 추정일 뿐 정답이 아니다."""
    for i, r in enumerate(rows[:40]):
        cells = [re.sub(r"\s+", "", c) for c in r]
        if any(c in HEADER_KEYS for c in cells) and any(c in UNIT_KEYS for c in cells):
            return i + 1
    return None


def write_csv(path: Path, header: list[str], rows: list[list], overwrite: bool) -> bool:
    if path.exists() and not overwrite:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    return True


def build_l2_templates(set_id: str, boq_dir: Path, label_dir: Path) -> dict:
    sheet_rows, col_rows, row_rows = [], [], []
    stats = {"workbooks": 0, "sheets": 0, "candidate_sheets": 0, "rows_listed": 0, "errors": []}
    for wbp in sorted(boq_dir.iterdir()):
        try:
            sheets = read_workbook(wbp)
        except Exception as e:  # noqa: BLE001
            stats["errors"].append(f"{wbp.name}: {type(e).__name__}: {str(e)[:150]}")
            continue
        stats["workbooks"] += 1
        for name, rows in sheets.items():
            stats["sheets"] += 1
            ncols = max((len(r) for r in rows), default=0)
            preview = " / ".join(" ".join(c for c in r if c)[:60] for r in rows[:6] if any(r))[:300]
            hdr = detect_header_row(rows)
            sheet_rows.append([wbp.name, name, len(rows), ncols, hdr or "", preview, "", ""])
            if hdr is None:
                continue
            stats["candidate_sheets"] += 1
            header = rows[hdr - 1]
            for j in range(min(ncols, 30)):
                text = header[j] if j < len(header) else ""
                col_rows.append([wbp.name, name, hdr, col_letter(j), text, ""])
            for i in range(hdr, len(rows)):
                r = rows[i]
                if not any(r):
                    continue
                cells = [(r[j] if j < len(r) else "")[:40] for j in range(PREVIEW_COLS)]
                row_rows.append([wbp.name, name, i + 1, ""] + cells)
                stats["rows_listed"] += 1
    write_csv(label_dir / "l2_sheets.csv",
              ["workbook", "sheet", "rows", "cols", "header_row_guess", "preview", "sheet_role", "note"],
              sheet_rows, overwrite=False)
    write_csv(label_dir / "l2_columns.csv",
              ["workbook", "sheet", "header_row", "col", "header_text", "col_role"], col_rows, overwrite=False)
    write_csv(label_dir / "l2_rows.csv",
              ["workbook", "sheet", "row", "row_role"] + [col_letter(j) for j in range(PREVIEW_COLS)],
              row_rows, overwrite=False)
    return stats


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=HERE / "data" / "text_v0.1")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    manifest = {"kit": "text_v0.1", "source_root": "실전프로젝트/03_수집_3년", "sets": []}
    for notice, year, reason in SETS:
        folder = find_folder(notice, year)
        set_dir = args.out / "sets" / notice
        label_dir = args.out / "labels" / notice
        if set_dir.exists() and args.force:
            shutil.rmtree(set_dir)
        boq_files = [p for p in (folder / "02_내역서").rglob("*") if p.suffix.lower() in BOQ_EXT]
        spec_files = [p for p in (folder / "03_시방서_과업").rglob("*") if p.suffix.lower() in SPEC_EXT]
        boq = copy_unique(boq_files, set_dir / "boq")
        spec = copy_unique(spec_files, set_dir / "spec")

        for s in spec:
            text, err = extract_spec_text(set_dir / "spec" / s["file"])
            s["text_chars"] = len(text)
            s["text_error"] = err
            tdir = set_dir / "spec_text"
            tdir.mkdir(parents=True, exist_ok=True)
            (tdir / (s["file"] + ".txt")).write_text(text, encoding="utf-8")

        l2 = build_l2_templates(notice, set_dir / "boq", label_dir)
        write_csv(label_dir / "l3_rules.csv",
                  ["spec_file", "clause_no", "item", "attribute", "operator", "value", "unit", "quote", "note"],
                  [], overwrite=False)

        title = folder.name.split("_", 2)[-1]
        org = folder.name.split("_", 2)[1] if folder.name.count("_") >= 2 else ""
        manifest["sets"].append({"id": notice, "org": org, "title": title, "reason": reason,
                                 "source_folder": str(folder.relative_to(COLLECT)),
                                 "boq": boq, "spec": spec, "l2_template": l2})
        print(f"[{notice}] 내역서 {len(boq)} · 시방서 {len(spec)} · 시트 {l2['sheets']} "
              f"(품명·단위 머리글 추정 {l2['candidate_sheets']}) · 행 {l2['rows_listed']}"
              + (f" · 오류 {l2['errors']}" if l2["errors"] else ""))
        for s in spec:
            print(f"    시방서 {s['file']}: 글자 {s['text_chars']}" + (f" · 추출 실패 {s['text_error']}" if s["text_error"] else ""))

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"완료: {args.out}")


if __name__ == "__main__":
    sys.exit(main())
