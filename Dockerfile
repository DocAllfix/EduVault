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

# F-AUDIO-FIX 2026-06-01: Azure Cognitive Services Speech SDK Python
# linka libssl1.1 (NON libssl 3.x default Debian 12 Bookworm).
# Senza libssl1.1, SpeechSynthesizer.speak_ssml() segfault al primo
# dlopen(). Workaround documentato Microsoft:
# https://learn.microsoft.com/en-us/azure/ai-services/speech-service/quickstarts/setup-platform
# Scarico .deb da snapshot.debian.org (URL stabile) per Debian 11 Bullseye.
RUN wget -q https://snapshot.debian.org/archive/debian/20240101T000000Z/pool/main/o/openssl/libssl1.1_1.1.1n-0%2Bdeb11u5_amd64.deb \
    -O /tmp/libssl1.1.deb \
    && dpkg -i /tmp/libssl1.1.deb \
    && rm /tmp/libssl1.1.deb

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
