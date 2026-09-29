FROM python:3.12-slim
WORKDIR /repo
COPY pyproject.toml ./
COPY src ./src
COPY apps/research-ui/backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -e '.[quant]' && pip install --no-cache-dir -r /tmp/requirements.txt
CMD ["uvicorn","apps.research-ui.backend.app:app","--host","0.0.0.0","--port","8000"]