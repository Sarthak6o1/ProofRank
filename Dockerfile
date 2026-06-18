FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u 1000 user

WORKDIR /app

COPY --chown=user requirements.txt .
USER user
ENV PATH="/home/user/.local/bin:$PATH"
RUN pip install --no-cache-dir --user -r requirements.txt

COPY --chown=user . /app

EXPOSE 7860

CMD ["streamlit", "run", "app.py", "--server.port=7860", "--server.address=0.0.0.0", "--server.headless=true"]
