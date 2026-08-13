FROM python:3.11-slim
WORKDIR /usr/src/app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python3", "-u", "-m", "uvicorn", "app:app", "--host=0.0.0.0", "--port=80"]
