FROM python:3.12-slim-bookworm

WORKDIR /app

# Dipendenze C per WeasyPrint + cairosvg + font per branding +
# Azure Speech SDK (libssl1.1, libasound2, ca-certificates).
#
# F-AUDIO-FIX 2026-06-01: Azure Cognitive Services Speech SDK linka
# libssl1.1 (NON libssl 3.x default Debian Bookworm). Senza
# libssl1.1 il processo crasha con SEGFAULT al primo
# SpeechSynthesizer.speak_ssml() (dlopen su SO mancante).
# libssl1.1 disponibile via debian-archive Bullseye snapshot.
# libasound2 = runtime audio (anche se non riproduciamo, l'SDK lo richiede).
# ca-certificates = HTTPS validation endpoint Azure.
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
    && wget -q http://security.debian.org/debian-security/pool/updates/main/o/openssl/libssl1.1_1.1.1w-0+deb11u1_amd64.deb \
    && dpkg -i libssl1.1_1.1.1w-0+deb11u1_amd64.deb \
    && rm libssl1.1_1.1.1w-0+deb11u1_amd64.deb \
    && rm -rf /var/lib/apt/lists/*

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
