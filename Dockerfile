FROM python:3.12-slim-bookworm

WORKDIR /app

# Dipendenze C per WeasyPrint + cairosvg + font per branding
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
