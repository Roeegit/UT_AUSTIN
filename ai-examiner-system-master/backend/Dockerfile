FROM python:3.11-slim

WORKDIR /app

# Without this, print() goes to a block-buffered stdout and startup diagnostics
# ([prompts], [session:start]) only reach Cloud Run once 8 KB has accumulated —
# so a low-traffic service looks like it logged nothing at all.
ENV PYTHONUNBUFFERED=1

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# The backend itself.
COPY backend/ .

# Per-course rendered prompts (config.COURSE_ID). Sample PDFs and POC tooling are
# excluded by .dockerignore. Harmless when COURSE_ID is unset — nothing reads it.
COPY courses/ ./courses/

EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
