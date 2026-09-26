FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py .
COPY static ./static
COPY templates ./templates
ENV PORT=80
EXPOSE 80
CMD ["python", "main.py"]
