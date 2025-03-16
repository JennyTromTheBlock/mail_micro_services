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
def get_rabbitmq_connection(retries=5, base_delay=2):
    for attempt in range(retries):
        try:
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(host=RABBITMQ_HOST)
            )
            print("RabbitMQ connection established.")
            return connection.channel()
        except pika.exceptions.AMQPConnectionError as e:
            wait_time = base_delay ** attempt
            print(f"RabbitMQ connection failed: {e}. Retrying in {wait_time} seconds...")
            time.sleep(wait_time)

    raise Exception("Failed to connect to RabbitMQ after multiple retries.")


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
    channel.basic_publish(
        exchange='',
        routing_key=RABBITMQ_QUEUE,
        body=message,
        properties=pika.BasicProperties(delivery_mode=2)
    )
    channel.close()


@app.get("/start-indexing")
def start_indexing(background_tasks: BackgroundTasks):
    background_tasks.add_task(index_files, EMAIL_DIR)
    return {"message": "Indeksering startet i baggrunden!"}

@app.get("/health")
async def health_check():
    """Health check endpoint for RabbitMQ."""
    # Check RabbitMQ connection
    try:
        channel = get_rabbitmq_connection()
        channel.close()
    except Exception as e:
        return {"status": "unhealthy", "rabbitmq": "down", "error": str(e)}

    return {"status": "healthy"}
