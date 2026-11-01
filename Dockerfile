FROM python:3.11-slim

# ffmpeg: video frames for YOLO; libgl1/libglib2.0-0: OpenCV, pulled in by ultralytics
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# CPU-only torch first, otherwise ultralytics pulls the multi-GB CUDA build
COPY requirements.txt .
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
COPY frontend ./frontend
COPY weight ./weight

ENV SUDHAAR_DATA=/data \
    SUDHAAR_YOLO_MODELS=weight/best.pt,weight/pothole2v.pt \
    YOLO_CONFIG_DIR=/tmp/ultralytics \
    PYTHONUNBUFFERED=1

# World-writable because hosted platforms may run the container as a non-root user
RUN mkdir -p /data && chmod 777 /data

EXPOSE 7860
CMD ["sh", "-c", "exec python -m uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
