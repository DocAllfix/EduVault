FROM python:3.12-slim-bookworm

WORKDIR /app

# Dipendenze C per WeasyPrint + cairosvg + font per branding +
# Azure Speech SDK runtime deps.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libcairo2-dev \
    libpango1.0-dev \
    libgdk-pixbuf2.0-dev \
    libffi-dev \
    shared-mime-info \
    fonts-dejavu-core \
    fonts-open-sans \
    unzip \
    fontconfig \
    libreoffice-impress \
    libreoffice-core \
    poppler-utils \
    libasound2 \
    ca-certificates \
    wget \
    && rm -rf /var/lib/apt/lists/*

# F-AUDIO-FIX 2026-06-01 v3: simbolico libssl 3 -> libssl 1.1 path.
# Azure Speech SDK 1.50 supporta libssl 3 ma cerca libssl.so.1.1 esplicito.
# Crea symlink dal libssl.so.3 (disponibile) verso il path atteso libssl.so.1.1.
RUN ln -sf /usr/lib/x86_64-linux-gnu/libssl.so.3 /usr/lib/x86_64-linux-gnu/libssl.so.1.1 \
    && ln -sf /usr/lib/x86_64-linux-gnu/libcrypto.so.3 /usr/lib/x86_64-linux-gnu/libcrypto.so.1.1

# Montserrat (non nei repo Debian — copia manuale da assets committati in git)
COPY assets/fonts/Montserrat/ /usr/share/fonts/truetype/montserrat/
RUN fc-cache -fv

COPY pyproject.toml .
COPY README.md .
# hatchling needs the package source present to build the wheel
# (pyproject.toml declares packages = ["app"]).
COPY app/ ./app/
RUN pip install --no-cache-dir .

COPY . .

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
