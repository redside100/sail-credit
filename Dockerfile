FROM python:3.12.8-slim

RUN apt update && apt install -y python3-tk tk-dev

WORKDIR /app
COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt
COPY . .
CMD [ "python3", "-u", "main.py" ]
