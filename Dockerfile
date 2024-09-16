FROM ubuntu:latest

WORKDIR workdir

RUN apt update
RUN apt install python3 -y
RUN apt install python3-pip -y

COPY requirements.txt .

# RUN pip install --progress-bar off -r requirements.txt

COPY data .

COPY simulate.py .

# CMD [ "python3", "simulate.py" ]
