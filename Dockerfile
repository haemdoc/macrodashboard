FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app
COPY macro_monitor.py .
COPY .streamlit/ .streamlit/

# Expose Streamlit default port
EXPOSE 8501

# Health check
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Run
ENTRYPOINT ["streamlit", "run", "macro_monitor.py", "--server.address=0.0.0.0"]
