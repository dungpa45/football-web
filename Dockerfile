FROM python:3.11-slim
WORKDIR /football-web
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 5001
CMD ["python3", "app.py"]
