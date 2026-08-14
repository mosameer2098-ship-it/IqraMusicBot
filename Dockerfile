FROM nikolaik/python-nodejs:python3.13-nodejs20

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg curl unzip \
    && curl -fsSL https://deno.land/install.sh | sh \
    && ln -sf /root/.deno/bin/deno /usr/local/bin/deno \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ENV PATH="/root/.deno/bin:${PATH}"

WORKDIR /app

COPY . .

RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir --upgrade -r requirements.txt

CMD ["bash", "start"]
