FROM python:3

COPY docker/webhooks.py /webhooks.py

RUN pip install --no-cache-dir GitPython six twine

EXPOSE 80/TCP

CMD ["python", "/webhooks.py"]
