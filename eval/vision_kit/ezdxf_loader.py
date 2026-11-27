"""ezdxf를 불러온다.

설치돼 있으면 그것을 쓰고, 없으면 환경변수 EZDXF_PATH 또는
<LETS_DATA_ROOT 또는 lets-lats 상위>/04_도구_DWG변환/C_파이썬 (ezdxf 1.4.5 묶음)을 경로에 추가한다.
`pip install ezdxf==1.4.5`로 설치해도 된다.
"""
import os
import sys
from pathlib import Path

try:
    import ezdxf  # noqa: F401
except ImportError:
    candidates = []
    if os.environ.get("EZDXF_PATH"):
        candidates.append(Path(os.environ["EZDXF_PATH"]))
    # lets-lats/eval/vision_kit → 실전프로젝트
    candidates.append(Path(os.environ.get("LETS_DATA_ROOT") or Path(__file__).resolve().parents[3]) / "04_도구_DWG변환" / "C_파이썬")
    for c in candidates:
        if (c / "ezdxf").is_dir():
            # 뒤에 붙여서, 이미 설치된 numpy 등은 그대로 쓰게 한다.
            sys.path.append(str(c))
            break
    import ezdxf  # noqa: E402

__all__ = ["ezdxf"]
