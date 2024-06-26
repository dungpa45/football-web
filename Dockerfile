FROM python:3.8-slim-buster

WORKDIR /football-web

COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt

COPY . .
EXPOSE 80
CMD [ "python3", "app.py"]