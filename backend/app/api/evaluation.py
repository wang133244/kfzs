from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..eval.runner_v2 import load_eval_cases, run_evaluation, write_report
from .deps import get_current_staff

router = APIRouter(tags=["evaluation"])


@router.post("/evaluation/run")
async def run_eval(user=Depends(get_current_staff)) -> dict:
    cases = load_eval_cases()
    result = await run_evaluation(cases)
    write_report(result)
    return result


@router.get("/evaluation/latest")
async def latest_eval(user=Depends(get_current_staff)) -> dict:
    from pathlib import Path
    report_path = Path("artifacts/evaluation/latest.json")
    if not report_path.exists():
        raise HTTPException(404, "暂无评测结果，请先运行评测")
    import json
    return json.loads(report_path.read_text(encoding="utf-8"))


@router.get("/evaluation/cases")
async def list_cases(user=Depends(get_current_staff)) -> list[dict]:
    return load_eval_cases()
