FROM python-3.13.0
WORKDIR /bot

RUN apt-get update && apt-get -y install locales && apt-get -y upgrade && \
	localedef -f UTF-8 -i ja_JP ja_JP.UTF-8
ENV LANG ja_JP.UTF-8
ENV LANGUAGE ja_JP:ja
ENV LC_ALL ja_JP.UTF-8
ENV TZ Asia/Tokyo
ENV TERM xterm


COPY requirements.txt /bot/
RUN pip install -r requirements.txt
COPY . /bot

EXPOSE 8080
CMD python bot.py
