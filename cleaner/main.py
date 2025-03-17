import os
import time
import pika
import json
import re
import threading
from fastapi import FastAPI


# Konfiguration
RABBITMQ_HOST = "rabbitmq"
RABBITMQ_QUEUE = "file_paths"
RABBITMQ_CLEANED_QUEUE = "cleaned_file"  # Ny kø til de rensede filer

app = FastAPI()

# Global RabbitMQ forbindelse og kanal
rabbitmq_channel = None

# Opret og gem RabbitMQ-forbindelsen og kanalen
def get_rabbitmq_connection(retries=5, base_delay=2):
    global rabbitmq_channel
    if rabbitmq_channel is None:
        for attempt in range(retries):
            try:
                connection = pika.BlockingConnection(
                    pika.ConnectionParameters(host=RABBITMQ_HOST)
                )
                rabbitmq_channel = connection.channel()
                rabbitmq_channel.queue_declare(queue=RABBITMQ_QUEUE, durable=True)
                rabbitmq_channel.queue_declare(queue=RABBITMQ_CLEANED_QUEUE, durable=True)
                print("RabbitMQ connection established and channel created.")
                return rabbitmq_channel
            except pika.exceptions.AMQPConnectionError as e:
                wait_time = base_delay ** attempt
                print(f"RabbitMQ connection failed: {e}. Retrying in {wait_time} seconds...")
                time.sleep(wait_time)

        raise Exception("Failed to connect to RabbitMQ after multiple retries.")

    return rabbitmq_channel


def clean_email_header(file_path):
    """
    Åbner en e-mailfil, fjerner alle header-linjer (alt før den første tomme linje),
    og returnerer indholdet af e-mailen uden headers.

    :param file_path: Stien til e-mail filen
    :return: E-mailens indhold uden headers
    """
    with open(file_path, 'r', encoding='utf-8') as file:
        # Læs filens indhold
        email_content = file.read()

    # Brug regulær udtryk til at fjerne alt før den første tomme linje (hele headeren)
    cleaned_email = re.sub(r'^(.*?)(\r?\n\r?\n)', '', email_content, flags=re.DOTALL)

    # Returner den rensede e-mail uden headers
    return cleaned_email


# Forbruger, der lytter på RabbitMQ og behandler nye beskeder
def callback(ch, method, properties, body):
    # Modtager path fra RabbitMQ
    paths = json.loads(body)

    # Print paths modtaget
    for path in paths:
        print(f"Modtaget of cleaner filepath: {path}")
        clean_email = clean_email_header(path)

        # Hent filnavnet fra stien
        file_name = os.path.basename(path)

        # Opret en dictionary, der inkluderer både filnavn og den rensede e-mail
        message = {
            'file_name': file_name,
            'cleaned_email': clean_email
        }

        # Send kun den rensede version til den nye RabbitMQ-kø
        ch.basic_publish(
            exchange='',
            routing_key=RABBITMQ_CLEANED_QUEUE,
            body=json.dumps(message),  # Send kun den rensede e-mail (uden sti)
            properties=pika.BasicProperties(delivery_mode=2)
        )
    # Bekræft modtagelse af beskeden
    ch.basic_ack(delivery_tag=method.delivery_tag)


# Starter RabbitMQ lytteren
def listen_for_paths():
    channel = get_rabbitmq_connection()

    # Lyt på køen og kald callback når beskeder modtages
    channel.basic_consume(queue=RABBITMQ_QUEUE, on_message_callback=callback, auto_ack=False)

    print("Lytter på RabbitMQ for nye paths...")
    channel.start_consuming()


@app.on_event("startup")
def startup_event():
    # Kald RabbitMQ-læseren i en baggrundstråd, så det ikke blokkerer FastAPI
    print("Starter RabbitMQ consumer i baggrund...")
    thread = threading.Thread(target=listen_for_paths)
    thread.daemon = True  # Gør tråden til en daemon, så den afsluttes når serveren stopper
    thread.start()

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
