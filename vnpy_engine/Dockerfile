FROM python:3.10-slim

WORKDIR /vnpy

RUN apt-get update && apt-get install -y \
    build-essential \
    libffi-dev \
    libssl-dev \
    libxml2-dev \
    libxslt1-dev \
    python3-dev \
    git \
    curl \
    wget \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

COPY vnpy_repo /vnpy/vnpy_repo
COPY vnpy_engine/vnpy /vnpy/vnpy
COPY vnpy_engine/config /vnpy/config

RUN pip install --no-cache-dir --upgrade pip

RUN pip install --no-cache-dir \
    tzlocal>=5.3.1 \
    PySide6==6.8.2.1 \
    pyqtgraph>=0.13.7 \
    qdarkstyle>=3.2.3 \
    numpy>=2.2.3 \
    pandas>=2.2.3 \
    deap>=1.4.2 \
    pyzmq>=26.3.0 \
    plotly>=6.0.0 \
    tqdm>=4.67.1 \
    loguru>=0.7.3 \
    redis>=5.0.0 \
    fastapi>=0.110.0 \
    uvicorn>=0.27.0 \
    websockets>=12.0 \
    pydantic>=2.6.0 \
    pydantic-settings>=2.2.0 \
    python-dotenv>=1.0.0 \
    stable-baselines3>=2.2.0 \
    gymnasium>=0.29.0 \
    torch>=2.2.0 \
    scipy>=1.12.0 \
    scikit-learn>=1.4.0 \
    prometheus-client>=0.21.0 \
    python-telegram-bot>=21.0 \
    sqlalchemy>=2.0.0 \
    aiosqlite>=0.19.0 \
    psutil>=5.9.0 \
    vnpy-binance>=2.0.0

ENV PYTHONPATH=/vnpy
ENV PYTHONUNBUFFERED=1

EXPOSE 5000 5001 8000

COPY vnpy_engine/entrypoint.sh /entrypoint.sh
COPY vnpy_engine/supervisord.conf /etc/supervisor/conf.d/vnpy.conf
COPY vnpy_engine/prometheus.yml /etc/prometheus/prometheus.yml
RUN chmod +x /entrypoint.sh

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/vnpy.conf"]
