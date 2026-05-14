FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt uuid6
# Patch uuid.uuid7 into the stdlib uuid module (uuid7 is not yet in stdlib)
RUN python -c "import pathlib; pathlib.Path('/usr/local/lib/python3.12/site-packages/sitecustomize.py').write_text('import uuid\\ntry:\\n    from uuid6 import uuid7\\n    uuid.uuid7 = uuid7\\nexcept ImportError:\\n    pass\\n')"
COPY producer.py .
ENTRYPOINT ["python", "producer.py"]
