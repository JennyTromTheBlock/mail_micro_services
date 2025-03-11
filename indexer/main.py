import asyncio
import json
import re
import threading
from collections import Counter
from fastapi import FastAPI, HTTPException
from sqlmodel import Field, SQLModel, create_engine, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import pika
import concurrent.futures

# Load environment variables from .env file
load_dotenv()

# RabbitMQ connection details
RABBITMQ_HOST = "rabbitmq"
RABBITMQ_QUEUE = "cleaned_file"  # New queue for cleaned files

# Database URL (use your MariaDB credentials here)
DATABASE_URL = "mysql+aiomysql://myuser:mypassword@mariadb_container:3306/WordOccurrencesDB"

# FastAPI app initialization
app = FastAPI()
# Create an AsyncEngine (async engine)
engine = create_async_engine(DATABASE_URL, echo=False)

# Create an AsyncSession
SessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

class SessionManager:
    """A simple session manager to get database sessions."""
    @staticmethod
    async def get_session() -> AsyncSession:
        """Get a session from the connection pool."""
        async with SessionLocal() as session:
            yield session

class Word(SQLModel, table=True):
    __tablename__ = 'Word'
    word_id: int = Field(default=None, primary_key=True)
    word: str = Field(max_length=255, unique=True)

class File(SQLModel, table=True):
    __tablename__ = 'File'
    file_id: int = Field(default=None, primary_key=True)
    file_name: str = Field(max_length=255, unique=True)
    content: bytes = Field(default=None)

class Occurrence(SQLModel, table=True):
    __tablename__ = 'Occurrence'
    word_id: int = Field(foreign_key="Word.word_id", primary_key=True)
    file_id: int = Field(foreign_key="File.file_id", primary_key=True)
    count: int

def create_file_with_words_sync(mail_name: str, mail_body: str):
    """Run the database operations synchronously."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(create_file_with_words(mail_name, mail_body))
    loop.close()
    return result

async def create_file_with_words(mail_name: str, mail_body: str):
    async for session in SessionManager.get_session():
        try:
            # Step 1: Create a new file record
            file = File(file_name=mail_name, content=mail_body.encode('utf-8'))
            session.add(file)
            await session.commit()

            # Step 2: Process the mail body to get unique words (ignoring case, punctuation)
            words_in_body = re.findall(r'\b\w+\b', mail_body.lower())
            word_count = Counter(words_in_body)

            # Step 3: For each unique word, create a Word record if it doesn't already exist
            for word, count in word_count.items():
                existing_word = await session.execute(
                    select(Word).filter(Word.word == word)
                )
                existing_word = existing_word.scalars().first()

                if not existing_word:
                    new_word = Word(word=word)
                    session.add(new_word)
                    await session.commit()
                    existing_word = new_word  # Use the newly created word

                # Step 4: Create an Occurrence record for the word in the file
                occurrence = Occurrence(word_id=existing_word.word_id, file_id=file.file_id, count=count)
                session.add(occurrence)

            # Step 5: Commit the changes for occurrences
            await session.commit()

            return file

        except Exception as e:
            await session.rollback()
            raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")


def callback(ch, method, properties, body):
    """Handles messages from RabbitMQ"""
    print("✅ Done processing the cleaned email.")
    cleaned_email = json.loads(body)
    mail_name = cleaned_email["file_name"]
    mail_body = cleaned_email["cleaned_email"]

    # Run the task in a background thread to avoid blocking the main process
    with concurrent.futures.ThreadPoolExecutor() as executor:
        executor.submit(create_file_with_words_sync, mail_name, mail_body)

    ch.basic_ack(delivery_tag=method.delivery_tag)  # Acknowledge message


@app.on_event("startup")
def startup_event():
    # Start the RabbitMQ consumer in a background thread so it doesn't block FastAPI
    print("Starting RabbitMQ consumer in the background...")
    thread = threading.Thread(target=listen_for_paths)
    thread.daemon = True  # Daemon thread will exit when the main program exits
    thread.start()


def listen_for_paths():
    channel = get_rabbitmq_connection()

    # Consume messages and call the callback function when messages are received
    channel.basic_consume(queue=RABBITMQ_QUEUE, on_message_callback=callback, auto_ack=False)

    print("Listening for RabbitMQ messages...")
    channel.start_consuming()


# Create and store the RabbitMQ connection and channel
def get_rabbitmq_connection():
    connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
    channel = connection.channel()
    channel.queue_declare(queue=RABBITMQ_QUEUE)
    print("RabbitMQ connection established and channel created.")
    return channel
