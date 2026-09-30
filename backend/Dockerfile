FROM python:3.11-slim

WORKDIR /workspace

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# CPU-only torch, installed BEFORE requirements.txt so the later pass sees torch
# already satisfied and never reaches for the default wheel.
#
# That default drags in the whole CUDA runtime - torch 555MB, cuDNN 553MB, plus
# cuBLAS/cuFFT/cuSOLVER/cuSPARSE/nvrtc and friends, around 4GB - none of which this
# image can use. Generation runs in Ollama on the host; torch is here only so
# sentence-transformers can embed with BAAI/bge-small-en, which is CPU work.
#
# To move this image to a GPU host with the NVIDIA container runtime, delete this
# line and the CUDA wheels come back on their own.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

RUN pip install --no-cache-dir -r requirements.txt
RUN python -m spacy download en_core_web_sm

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
