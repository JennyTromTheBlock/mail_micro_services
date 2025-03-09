import os
from typing import List

import pika
import json

from dotenv import load_dotenv
from fastapi import FastAPI, BackgroundTasks, HTTPException

EMAIL_DIR = "./maildir"

def scan_and_send(rabbitmq_host: str):
    """ Scanner en mappe for emails og sender dem til RabbitMQ """
    connection = pika.BlockingConnection(pika.ConnectionParameters(host=rabbitmq_host))
    channel = connection.channel()
    channel.queue_declare(queue="email_queue", durable=True)

    for filename in os.listdir(EMAIL_DIR):
        file_path = os.path.join(EMAIL_DIR, filename)

        if filename.endswith(".txt"):
            with open(file_path, "r", encoding="utf-8") as file:
                email_content = file.read()

            email_data = {
                "email_id": filename,
                "body": email_content,
            }

            channel.basic_publish(
                exchange="",
                routing_key="email_queue",
                body=json.dumps(email_data),
                properties=pika.BasicProperties(delivery_mode=2),
            )
            print(f"Sent to queue: {filename}")

    connection.close()


load_dotenv()  # Indlæs konfigurationsvariabler fra .env

app = FastAPI()

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")

@app.get("/")
def read_root():
    return {"message": "Cleaner Service is running!"}

@app.post("/scan-emails")
def scan_emails(background_tasks: BackgroundTasks):
    """ Trigger scanning af emails i en baggrundsopgave """
    background_tasks.add_task(scan_and_send, RABBITMQ_HOST)
    return {"message": "Scanning started in the background"}


# Funktion til at liste alle mapper i maildir
def list_folders_in_maildir():
    folders = []
    # Iterere gennem mapperne i maildir
    for folder in os.listdir(EMAIL_DIR):
        folder_path = os.path.join(EMAIL_DIR, folder)

        # Hvis det er en mappe, tilføj den til listen
        if os.path.isdir(folder_path):
            folders.append(folder)

    # Hvis der ikke er nogen mapper, kast en HTTPException
    if not folders:
        raise HTTPException(status_code=404, detail="Ingen mapper fundet i maildir")

    return folders


# FastAPI endpoint for at liste mapper i maildir
@app.get("/list_folders", response_model=List[str])
async def list_folders():
    try:
        folders = list_folders_in_maildir()
        return {"folders": folders}
    except HTTPException as e:
        raise e


# Funktion til at finde den første fil i '_sent_mail' mappen og læse dens indhold
def get_first_file_content():
    # Iterere gennem mapperne i maildir
    for folder in os.listdir(EMAIL_DIR):
        folder_path = os.path.join(EMAIL_DIR, folder)

        # Hvis det ikke er en mappe, spring over den
        if not os.path.isdir(folder_path):
            raise HTTPException(status_code=404, detail="Mappe ikke fundet")

        # Kig efter '_sent_mail' mappen inde i den aktuelle mappe
        sent_mail_path = os.path.join(folder_path, '_sent_mail')

        if os.path.isdir(sent_mail_path):
            # Hvis vi finder '_sent_mail' mappen, itererer vi over filerne
            for file_name in os.listdir(sent_mail_path):
                file_path = os.path.join(sent_mail_path, file_name)

                # Hvis det ikke er en fil, spring over
                if not os.path.isfile(file_path):
                    raise HTTPException(status_code=404, detail=f"Ikke en fil: {file_path}")

                # Læs indholdet af den første fil, der findes
                with open(file_path, 'r', encoding='utf-8') as file:
                    return file.read()  # Returner filens indhold

    # Hvis ingen fil findes, kast en undtagelse
    raise HTTPException(status_code=404, detail="Ingen fil fundet i _sent_mail mappen")


# FastAPI endpoint for at hente indholdet af den første fil i '_sent_mail'
@app.get("/open_first_file")
async def open_first_file():
    try:
        file_content = get_first_file_content()
        return {"content": file_content}
    except HTTPException as e:
        raise e