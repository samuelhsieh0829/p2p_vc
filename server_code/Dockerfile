FROM python:3.11.10-slim
WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir -r requirements.txt
EXPOSE 10001
CMD ["python", "server.py"]