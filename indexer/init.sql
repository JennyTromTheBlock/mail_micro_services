CREATE DATABASE IF NOT EXISTS WordOccurrencesDB;
USE WordOccurrencesDB;

-- Opretter Word-tabellen
CREATE TABLE IF NOT EXISTS Word (
    word_id INT PRIMARY KEY AUTO_INCREMENT,
    word NVARCHAR(255) UNIQUE NOT NULL
);

-- Opretter File-tabellen
CREATE TABLE IF NOT EXISTS File (
    file_id INT PRIMARY KEY AUTO_INCREMENT,
    file_name VARCHAR(255) NOT NULL,
    content BLOB
);

-- Opretter Occurrence-tabellen
CREATE TABLE IF NOT EXISTS Occurrence (
    word_id INT,
    file_id INT,
    count INT NOT NULL,
    PRIMARY KEY (word_id, file_id),
    FOREIGN KEY (word_id) REFERENCES Word(word_id) ON DELETE CASCADE,
    FOREIGN KEY (file_id) REFERENCES File(file_id) ON DELETE CASCADE
);
