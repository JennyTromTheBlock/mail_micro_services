from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.future import select
from sqlalchemy.orm import sessionmaker
from sqlalchemy import Integer, String, Column
from sqlmodel import SQLModel, Field
from typing import List
from collections import Counter
import re
from fastapi.middleware.cors import CORSMiddleware  # Import CORS middleware

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

# Endpoint til at hente filen som en string
@app.get("/file/{file_id}", response_model=FileResponse)
async def get_file(file_id: int):
    async with SessionLocal() as session:
        result = await session.execute(select(File).where(File.file_id == file_id))
        file = result.scalars().first()

        if not file:
            raise HTTPException(status_code=404, detail="File not found")

        # Dekod filens indhold til string
        try:
            file_content = file.content.decode("utf-8")  # Hvis filen er tekstbaseret
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="File is not a valid UTF-8 text file")

        return FileResponse(file_id=file.file_id, file_name=file.file_name, content=file_content)