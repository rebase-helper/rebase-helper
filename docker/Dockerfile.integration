FROM python:3

COPY docker/integration.py /integration.py
COPY docker/cert.pem /cert.pem

RUN pip install --no-cache-dir pyftpdlib six

EXPOSE 2100/TCP 2101/TCP 8000/TCP 8001/TCP 4430/TCP 4431/TCP

WORKDIR /srv
COPY docker/integration_data .

CMD ["python", "/integration.py"]
