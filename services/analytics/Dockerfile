FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY mapping ./mapping
COPY forecasting ./forecasting
COPY equity ./equity

EXPOSE 8501

CMD ["streamlit", "run", "app/Home.py", "--server.address=0.0.0.0", "--server.port=8501"]
