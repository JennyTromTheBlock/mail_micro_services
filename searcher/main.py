from fastapi import FastAPI, HTTPException, Query
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.future import select
from sqlalchemy.orm import sessionmaker
from sqlalchemy import Integer, String, Column
from sqlmodel import SQLModel, Field
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from typing import List
from collections import Counter
import re
from fastapi.middleware.cors import CORSMiddleware  # Import CORS middleware
import logging
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry import trace
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter


# Database URL (erstat med dine egne databaseoplysninger)
DATABASE_URL = "mysql+aiomysql://myuser:mypassword@mariadb_container:3306/WordOccurrencesDB"

# FastAPI app initialisering
app = FastAPI()

# Tilføj CORS middleware for at tillade anmodninger fra alle oprindelser
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tillader anmodninger fra alle oprindelser
    allow_credentials=True,
    allow_methods=["*"],  # Tillader alle HTTP-metoder (GET, POST, etc.)
    allow_headers=["*"],  # Tillader alle headers
)

# Tracing setup with OpenTelemetry
trace_provider = TracerProvider()
trace_exporter = OTLPSpanExporter(endpoint="http://otel-collector:4317", insecure=True)
trace_provider.add_span_processor(BatchSpanProcessor(trace_exporter))

# FastAPI instrumentation for tracing
FastAPIInstrumentor.instrument_app(app, tracer_provider=trace_provider)

# Setup for OpenTelemetry logging exporter
log_exporter = OTLPLogExporter(endpoint="http://otel-collector:4317", insecure=True)

# Logger provider setup
logger_provider = LoggerProvider()
logger_provider.add_log_record_processor(BatchLogRecordProcessor(log_exporter))

# Logger setup
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Example log handler (this could be a custom handler if necessary)
log_handler = logging.StreamHandler()  # or any other handler
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log_handler.setFormatter(formatter)
logger.addHandler(log_handler)

# Opret en AsyncEngine
engine = create_async_engine(DATABASE_URL, echo=True)

# Opret en AsyncSession
SessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Word(SQLModel, table=True):
    __tablename__ = 'Word'
    word_id: int = Field(default=None, primary_key=True)
    word: str = Field(max_length=255, unique=True)


# Definer databasemodeller
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

# Pydantic model til at returnere data
class WordOccurrence(BaseModel):
    file_id: int
    count: int

    class Config:
        orm_mode = True

# Funktion til at hente ordforekomster fra databasen
async def get_word_occurrences(word: str, session: AsyncSession) -> List[WordOccurrence]:
    stmt = (
        select(File.file_id, Occurrence.count)
        .join(Occurrence, File.file_id == Occurrence.file_id)
        .join(Word, Word.word_id == Occurrence.word_id)
        .filter(Word.word == word)
        .order_by(Occurrence.count.desc())
    )
    result = await session.execute(stmt)
    occurrences = result.fetchall()
    return [WordOccurrence(file_id=occ[0], count=occ[1]) for occ in occurrences]

# Endpoint til at hente ordforekomster
@app.get("/word_occurrences/", response_model=List[WordOccurrence])
async def read_word_occurrences(word: str = Query(..., min_length=1)):
    async with SessionLocal() as session:
        occurrences = await get_word_occurrences(word, session)
        return occurrences

# Pydantic-model til API-respons
class FileResponse(SQLModel):
    file_id: int
    file_name: str
    content: str  # Dekodet filindhold

# Endpoint to get the file content as a string
@app.get("/file/{file_id}", response_model=FileResponse)
async def get_file(file_id: int):
    # Start a new trace for the endpoint execution
    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span("get_file-span"):
        logger.info(f"Fetching file with ID {file_id}")

        # Fetch file from the database
        async with SessionLocal() as session:
            result = await session.execute(select(File).where(File.file_id == file_id))
            file = result.scalars().first()

            if not file:
                logger.warning(f"File with ID {file_id} not found")
                raise HTTPException(status_code=404, detail="File not found")

            # Decode the file content
            try:
                file_content = file.content.decode("utf-8")  # If the file is text-based
            except UnicodeDecodeError:
                logger.error(f"File with ID {file_id} is not a valid UTF-8 text file")
                raise HTTPException(status_code=400, detail="File is not a valid UTF-8 text file")

            logger.info(f"Successfully fetched file with ID {file_id}")
            return FileResponse(file_id=file.file_id, file_name=file.file_name, content=file_content)