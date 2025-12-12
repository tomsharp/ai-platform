FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch==2.9.1
RUN pip install -r requirements.txt

COPY app/ .

EXPOSE 80
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80"]