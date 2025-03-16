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

@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=2, max=10))
async def create_file_with_words(mail_name: str, mail_body: str):
    """Processes an email and saves it to the database with retries on failure."""
    async for session in SessionManager.get_session():
        try:
            async with session.begin():  # Transaction starts here
                # Insert file record
                file = File(file_name=mail_name, content=mail_body.encode('utf-8'))
                session.add(file)
                await session.flush()  # Ensure file_id is available

                # Extract words from email body
                words_in_body = re.findall(r'\b\w+\b', mail_body.lower())
                word_count = Counter(words_in_body)

                # Process each word
                for word, count in word_count.items():
                    result = await session.execute(select(Word).filter(Word.word == word))
                    existing_word = result.scalars().first()

                    if not existing_word:
                        new_word = Word(word=word)
                        session.add(new_word)
                        await session.flush()

                    occurrence = Occurrence(word_id=new_word.word_id, file_id=file.file_id, count=count)
                    session.add(occurrence)

            # Commit all changes if no errors occur
            await session.commit()
            logging.info(f"Successfully processed {mail_name}")

        except SQLAlchemyError as e:
            await session.rollback()  # Rollback on failure
            logging.error(f"Database error while processing {mail_name}: {e}")
            raise  # Triggers retry mechanism


def callback(ch, method, properties, body):
    """Handles messages from RabbitMQ, ensuring database failures don't discard data."""
    print("Received cleaned email.")
    cleaned_email = json.loads(body)
    mail_name = cleaned_email["file_name"]
    mail_body = cleaned_email["cleaned_email"]

    try:
        # Process the email and insert into DB
        create_file_with_words_sync(mail_name, mail_body)

        # Acknowledge message only if processing succeeds
        ch.basic_ack(delivery_tag=method.delivery_tag)
        print(f"Successfully processed {mail_name}")

    except Exception as e:
        print(f"Error processing {mail_name}: {e}")
        # Do NOT acknowledge the message, so it can be retried



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

def get_rabbitmq_connection(retries=5, base_delay=2):
    """Establish a RabbitMQ connection with retry logic and exponential backoff."""
    for attempt in range(retries):
        try:
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(host=RABBITMQ_HOST)
            )
            channel = connection.channel()
            channel.queue_declare(queue=RABBITMQ_QUEUE, durable=True)
            print("RabbitMQ connection established and channel created.")
            return channel
        except pika.exceptions.AMQPConnectionError as e:
            wait_time = base_delay ** attempt
            print(f"RabbitMQ connection failed: {e}. Retrying in {wait_time} seconds...")
            time.sleep(wait_time)

    raise Exception("Failed to connect to RabbitMQ after multiple retries.")

@app.get("/health")
async def health_check():
    """Health check endpoint for database and RabbitMQ."""
    # Check database connection
    async for session in SessionManager.get_session():
        try:
            await session.execute("SELECT 1")  # Simple DB check
        except Exception as e:
            return {"status": "unhealthy", "database": "down", "error": str(e)}

    # Check RabbitMQ connection
    try:
        channel = get_rabbitmq_connection()
        channel.close()
    except Exception as e:
        return {"status": "unhealthy", "rabbitmq": "down", "error": str(e)}

    return {"status": "healthy"}
