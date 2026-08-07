FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    HOME=/app

RUN pip install --no-cache-dir \
    confluent-kafka==2.15.0 \
    boto3==1.43.46 \
    python-docx==1.1.2 \
    reportlab==4.2.5 \
    openpyxl==3.1.5

WORKDIR /app
COPY produce.py .

RUN chgrp -R 0 /app && chmod -R g=u /app

USER 1001

CMD ["python", "produce.py"]
