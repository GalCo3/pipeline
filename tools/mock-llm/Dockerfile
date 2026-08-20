FROM python:3.14-slim
WORKDIR /app
RUN pip install --no-cache-dir fastapi uvicorn
COPY server.py .
EXPOSE 8081
CMD ["python", "server.py"]
