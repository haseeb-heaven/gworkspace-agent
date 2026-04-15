FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN printf '#!/bin/sh\necho gws stub\n' > /usr/local/bin/gws && chmod +x /usr/local/bin/gws

RUN touch .env

ENV GWS_BINARY_PATH=/usr/local/bin/gws
ENV LLM_PROVIDER=openrouter
ENV LANGCHAIN_ENABLED=true
ENV CODE_EXECUTION_ENABLED=true
ENV CODE_EXECUTION_BACKEND=restricted_subprocess

EXPOSE 8080

CMD sh -c "echo LLM_PROVIDER=$LLM_PROVIDER > .env && echo OPENROUTER_API_KEY=$OPENROUTER_API_KEY >> .env && echo OPENROUTER_MODEL=${OPENROUTER_MODEL:-openai/gpt-4o-mini} >> .env && echo OPENROUTER_BASE_URL=${OPENROUTER_BASE_URL:-https://openrouter.ai/api/v1} >> .env && echo LANGCHAIN_ENABLED=${LANGCHAIN_ENABLED:-true} >> .env && echo CODE_EXECUTION_ENABLED=${CODE_EXECUTION_ENABLED:-true} >> .env && echo CODE_EXECUTION_BACKEND=${CODE_EXECUTION_BACKEND:-restricted_subprocess} >> .env && echo GWS_BINARY_PATH=/usr/local/bin/gws >> .env && python gws_gradio.py --host 0.0.0.0 --port ${PORT:-8080}"
