"""
Underwrite — Python FastAPI Worker
Orchestrates the AI analysis pipeline for STR investment properties.
Deploy on Railway.
"""

import asyncio
import os
import httpx
from fastapi import FastAPI, Header, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional

from pipeline import run_analysis_pipeline

app = FastAPI(title="Underwrite Worker", version="1.0.0")

WORKER_SECRET = os.environ["WORKER_SECRET"]
NEXT_APP_URL = os.environ["NEXT_APP_URL"]


class AnalysisRequest(BaseModel):
    analysisId: str
    propertyUrl: str
    propertyType: Optional[str] = "Single Family"
    strategy: Optional[str] = "Buy & Hold STR"
    renovationBudget: Optional[int] = None
    notes: Optional[str] = None


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/analyze")
async def analyze(
    req: AnalysisRequest,
    background_tasks: BackgroundTasks,
    x_worker_secret: str = Header(...),
):
    if x_worker_secret != WORKER_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Mark analysis as PROCESSING immediately
    await _update_analysis(req.analysisId, {"status": "PROCESSING", "startedAt": _now()})

    # Kick off pipeline in background so we return 202 immediately
    background_tasks.add_task(_run_pipeline, req)

    return {"analysisId": req.analysisId, "status": "PROCESSING"}


async def _run_pipeline(req: AnalysisRequest):
    try:
        result = await run_analysis_pipeline(
            analysis_id=req.analysisId,
            property_url=req.propertyUrl,
            property_type=req.propertyType or "Single Family",
            strategy=req.strategy or "Buy & Hold STR",
            renovation_budget=req.renovationBudget,
            notes=req.notes,
        )
        await _update_analysis(req.analysisId, {
            "status": "COMPLETE",
            "completedAt": _now(),
            **result,
        })
    except Exception as e:
        print(f"[PIPELINE ERROR] {req.analysisId}: {e}")
        await _update_analysis(req.analysisId, {"status": "FAILED"})


async def _update_analysis(analysis_id: str, data: dict):
    url = f"{NEXT_APP_URL}/api/worker/callback"
    print(f"[{analysis_id}] Callback POST {url} → status={data.get('status')}")
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            resp = await client.post(
                url,
                json={"analysisId": analysis_id, **data},
                headers={"x-worker-secret": WORKER_SECRET},
                timeout=15,
            )
            print(f"[{analysis_id}] Callback response: {resp.status_code}")
            if resp.status_code >= 400:
                print(f"[{analysis_id}] Callback body: {resp.text[:500]}")
    except Exception as e:
        print(f"[{analysis_id}] Callback FAILED: {e}")


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
