FROM python:3.9-alpine

ARG http_proxy
ARG https_proxy

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN mkdir /root/app
ADD text-analyzer.py /root/app
ADD requirements.txt /root/app

RUN python3.9 -m pip install --no-cache-dir -r /root/app/requirements.txt --upgrade pip

ENTRYPOINT ["kopf", "run", "/root/app/text-analyzer.py"]
CMD [ "-n", "default" ]
