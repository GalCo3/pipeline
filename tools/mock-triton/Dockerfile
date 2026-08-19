# 3.12, not 3.13: tritonclient 2.56.0 pins numpy<2, and numpy 1.x ships no
# cp313 wheels — on 3.13 pip finds no resolution at all.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    HOME=/app

# tritonclient is here for its generated protobuf/gRPC stubs, not to call
# anything: implementing GRPCInferenceService against the client package's own
# service_pb2_grpc is what guarantees the mock's gRPC surface matches the
# clients that will talk to it. Pinned to the server version prod reports
# (2.56.0) so the two never drift.
RUN pip install --no-cache-dir \
    "tritonclient[grpc]==2.56.0" \
    numpy==1.26.4

WORKDIR /app
COPY contract.json classify.py embed.py rerank.py text_embed.py server.py ./

RUN chgrp -R 0 /app && chmod -R g=u /app

USER 1001

EXPOSE 8000 8001 8002

CMD ["python", "server.py"]
