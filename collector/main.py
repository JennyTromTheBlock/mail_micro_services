import os
import time
import pika
import json
from fastapi import FastAPI, BackgroundTasks

# Konfiguration
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_QUEUE = "file_paths"
BATCH_SIZE = 1000
EMAIL_DIR = "./maildir"


app = FastAPI()


# RabbitMQ forbindelse
def get_rabbitmq_connection():
    connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
    return connection.channel()


# Indeksering af filers sti og sending til RabbitMQ
def index_files(directory: str):
    print("Starter filindeksering...")
    file_paths = []

    for root, _, files in os.walk(directory):
        for file in files:
            file_paths.append(os.path.join(root, file))

            # Send batch, hvis vi har nok filer
            if len(file_paths) >= BATCH_SIZE:
                send_to_rabbitmq(file_paths)
                file_paths = []

    # Send resterende filer
    if file_paths:
        send_to_rabbitmq(file_paths)

    print("Indeksering færdig!")


# Sender filer i batches til RabbitMQ
def send_to_rabbitmq(paths):
    channel = get_rabbitmq_connection()
    message = json.dumps(paths)
    channel.basic_publish(exchange='', routing_key=RABBITMQ_QUEUE, body=message)
    channel.close()


@app.get("/start-indexing")
def start_indexing(background_tasks: BackgroundTasks):
    background_tasks.add_task(index_files, EMAIL_DIR)
    return {"message": "Indeksering startet i baggrunden!"}
