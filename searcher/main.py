from fastapi import FastAPI, HTTPException, Query
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry import trace
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.future import select
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel, Field
from typing import List
import logging
from fastapi.middleware.cors import CORSMiddleware

# Database URL
DATABASE_URL = "mysql+aiomysql://myuser:mypassword@mariadb_container1:3306/WordOccurrencesDB"

# FastAPI app initialization
app = FastAPI()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Tracing setup with OpenTelemetry
trace_provider = TracerProvider()
trace.set_tracer_provider(trace_provider)

from opentelemetry.exporter.zipkin.proto.http import ZipkinExporter
zipkin_exporter = ZipkinExporter(endpoint="http://zipkin:9411/api/v2/spans")
trace_provider.add_span_processor(BatchSpanProcessor(zipkin_exporter))


# Logging setup with OpenTelemetry
log_exporter = OTLPLogExporter(endpoint="http://otel-collector:4318", insecure=True)
logger_provider = LoggerProvider()
logger_provider.add_log_record_processor(BatchLogRecordProcessor(log_exporter))

# Setup OpenTelemetry logging handler
otel_handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)
logging.root.addHandler(otel_handler)

# Standard Python logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# FastAPI instrumentation for tracing
FastAPIInstrumentor.instrument_app(app)

# Database engine and session
engine = create_async_engine(DATABASE_URL, echo=True)
SessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

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

class WordOccurrence(SQLModel):
    file_id: int
    count: int

    class Config:
        orm_mode = True

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

@app.get("/word_occurrences/", response_model=List[WordOccurrence])
async def read_word_occurrences(word: str = Query(..., min_length=1)):
    async with SessionLocal() as session:
        occurrences = await get_word_occurrences(word, session)
        return occurrences

class FileResponse(SQLModel):
    file_id: int
    file_name: str
    content: str

@app.get("/file/{file_id}", response_model=FileResponse)
async def get_file(file_id: int):
    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span("get_file-span"):
        logger.info(f"Fetching file with ID {file_id}")

        async with SessionLocal() as session:
            result = await session.execute(select(File).where(File.file_id == file_id))
            file = result.scalars().first()

            if not file:
                logger.warning(f"File with ID {file_id} not found")
                raise HTTPException(status_code=404, detail="File not found")

            try:
                file_content = file.content.decode("utf-8")
            except UnicodeDecodeError:
                logger.error(f"File with ID {file_id} is not a valid UTF-8 text file")
                raise HTTPException(status_code=400, detail="File is not a valid UTF-8 text file")

            logger.info(f"Successfully fetched file with ID {file_id}")
            return FileResponse(file_id=file.file_id, file_name=file.file_name, content=file_content)
