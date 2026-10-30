FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000 JITD_PROFILE=enterprise JITD_DATA_DIR=/app/data JITD_MAX_MODEL_CALLS=0
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd -m -u 10001 app && mkdir -p /app/data && chown app:app /app/data
COPY . .
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s CMD python -c "import os,urllib.request;urllib.request.urlopen('http://127.0.0.1:%s/api/health' % os.environ.get('PORT','8000'))" || exit 1
CMD ["python", "-m", "jitd.launch", "--host", "0.0.0.0"]
