# syntax=docker/dockerfile:1.7
# ---------------------------------------------------------------------------
# Cybersecurity Panel — single-container HuggingFace Spaces image.
#
# Mirrors the structural choices used by the working HF Spaces deployments
# CCAI-Vibe-Demo and CU-Student-AIProject-Helper:
#   * multi-stage Node frontend build → Python+SPA bundle
#   * non-root user uid 1000, port 7860 (HF Spaces convention)
#   * persistence on the HF Storage Bucket mount at /data (SQLite shim)
#   * REACT_APP_API_URL is set to the empty string at build time so the SPA
#     issues relative URLs and shares the FastAPI origin
#
# Build context: repo root (this file).
# ---------------------------------------------------------------------------

# ---- 1. Frontend build (CRA) ----------------------------------------------
FROM node:20-bookworm AS frontend-build
WORKDIR /app/frontend

COPY phd-advisor-frontend/package.json phd-advisor-frontend/package-lock.json* ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci

COPY phd-advisor-frontend/ ./

# Empty REACT_APP_API_URL → CRA inlines '' so every fetch() hits the same
# origin as the SPA (the FastAPI server below).
ENV REACT_APP_API_URL=""
RUN npm run build

# ---- 2. Python runtime + SPA bundle ---------------------------------------
FROM python:3.12-slim-bookworm

# ffmpeg is required by the /api/voice/transcribe endpoint
# (browser WebM/Opus → WAV for Whisper). Kept on the runtime image only,
# not on the build image, so we don't pay the apt cost during incremental
# code rebuilds.
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

# HF Spaces runs the container as uid 1000 and expects the app to do the
# same; with a non-root user we cannot bind privileged ports, but :7860 is
# fine.
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    CORS_ORIGINS=* \
    DATA_DIR=/data \
    CONFIG_PATH=/home/user/app/cybersecurity_config.yaml

WORKDIR $HOME/app

# ---- Python deps (cached unless requirements.txt changes) -----------------
COPY --chown=user multi_llm_chatbot_backend/requirements.txt ./
RUN --mount=type=cache,target=/home/user/.cache/pip,uid=1000,gid=1000 \
    pip install --no-cache-dir --user -r requirements.txt

# ---- Backend source -------------------------------------------------------
COPY --chown=user multi_llm_chatbot_backend/ ./

# ---- Top-level configuration files (config.yaml + persona definitions) ----
COPY --chown=user cybersecurity_config.yaml ./cybersecurity_config.yaml
COPY --chown=user phd_config.yaml ./phd_config.yaml
COPY --chown=user undergrad_config.yaml ./undergrad_config.yaml
COPY --chown=user personas/ ./personas/

# ---- Frontend bundle ------------------------------------------------------
# main.py mounts $HOME/app/static at "/" so the SPA is served same-origin
# with the API.
COPY --chown=user --from=frontend-build /app/frontend/build ./static

ENV PYTHONPATH=$HOME/app

EXPOSE 7860
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
