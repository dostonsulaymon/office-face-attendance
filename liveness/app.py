"""Liveness / anti-spoofing microservice.

Server-side only: the kiosk never asserts liveness itself. The backend calls
POST /check-liveness with a captured frame BEFORE running recognition.
"""
from contextlib import asynccontextmanager

import cv2
import numpy as np
from fastapi import FastAPI, File, HTTPException, UploadFile

from predictor import LivenessPredictor

state = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    state["predictor"] = LivenessPredictor()
    yield
    state.clear()


app = FastAPI(title="Liveness (Silent-Face-Anti-Spoofing)", version="1.0", lifespan=lifespan)


@app.get("/health")
def health():
    predictor = state.get("predictor")
    return {
        "status": "ok" if predictor else "loading",
        "models": [m["name"] for m in predictor.models] if predictor else [],
    }


@app.post("/check-liveness")
async def check_liveness(file: UploadFile = File(...)):
    predictor = state.get("predictor")
    if predictor is None:
        raise HTTPException(status_code=503, detail="model not loaded")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="empty file")
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(status_code=400, detail="invalid image")
    return predictor.predict(img)
