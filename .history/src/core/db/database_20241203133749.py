#!/usr/bin/env python3
"""
Database module for storing processed invoice data
"""

import sqlite3
import json
import hashlib
from pathlib import Path
from typing import Optional, Dict, Tuple
from termcolor import colored

# Constants
DATABASE_FILE = "invoice_data.db"
SCHEMA_VERSION = 1

def get_file_hash(file_content: bytes) -> str:
    """Calculate SHA-256 hash of file content"""
    return hashlib.sha256(file_content).hexdigest()

class InvoiceDB:
    def __init__(self, db_path: str = DATABASE_FILE):
        """Initialize database connection and create tables if they don't exist"""
        try:
            self.db_path = db_path
            self.conn = sqlite3.connect(db_path)
            self.conn.row_factory = sqlite3.Row
            self.cursor = self.conn.cursor()
            self._create_tables()
            print(colored(f"✓ Connected to database: {db_path}", "green"))
        except Exception as e:
            print(colored(f"Error initializing database: {str(e)}", "red"))
            raise

    def _create_tables(self):
        """Create necessary tables if they don't exist"""
        try:
            self.cursor.executescript("""
                CREATE TABLE IF NOT EXISTS processed_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_hash TEXT UNIQUE NOT NULL,
                    filename TEXT NOT NULL,
                    pdf_content BLOB,
                    text_content TEXT,
                    json_result TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_file_hash ON processed_files(file_hash);
            """)
            self.conn.commit()
        except Exception as e:
            print(colored(f"Error creating tables: {str(e)}", "red"))
            raise

    def check_file_exists(self, file_content: bytes) -> Optional[Dict]:
        """
        Check if file has been processed before
        Returns the processed result if exists, None otherwise
        """
        try:
            file_hash = get_file_hash(file_content)
            self.cursor.execute(
                "SELECT * FROM processed_files WHERE file_hash = ?",
                (file_hash,)
            )
            row = self.cursor.fetchone()
            
            if row:
                return {
                    'id': row['id'],
                    'filename': row['filename'],
                    'text_content': row['text_content'],
                    'json_result': json.loads(row['json_result']) if row['json_result'] else None,
                    'created_at': row['created_at']
                }
            return None
        except Exception as e:
            print(colored(f"Error checking file existence: {str(e)}", "red"))
            raise

    def save_file(self, filename: str, file_content: bytes, text_content: Optional[str] = None, 
                 json_result: Optional[Dict] = None) -> Tuple[str, bool]:
        """
        Save or update file information in database
        Returns tuple of (file_hash, is_new)
        """
        try:
            file_hash = get_file_hash(file_content)
            
            # Check if file exists
            self.cursor.execute(
                "SELECT id, text_content, json_result FROM processed_files WHERE file_hash = ?",
                (file_hash,)
            )
            existing = self.cursor.fetchone()
            
            if existing:
                # Update existing record if new data is provided
                updates = []
                params = []
                
                if text_content and not existing['text_content']:
                    updates.append("text_content = ?")
                    params.append(text_content)
                
                if json_result and not existing['json_result']:
                    updates.append("json_result = ?")
                    params.append(json.dumps(json_result))
                
                if updates:
                    updates.append("updated_at = CURRENT_TIMESTAMP")
                    query = f"UPDATE processed_files SET {', '.join(updates)} WHERE file_hash = ?"
                    params.append(file_hash)
                    self.cursor.execute(query, params)
                    self.conn.commit()
                
                return file_hash, False
            else:
                # Insert new record
                self.cursor.execute("""
                    INSERT INTO processed_files (file_hash, filename, pdf_content, text_content, json_result)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    file_hash,
                    filename,
                    file_content,
                    text_content,
                    json.dumps(json_result) if json_result else None
                ))
                self.conn.commit()
                return file_hash, True
                
        except Exception as e:
            print(colored(f"Error saving file: {str(e)}", "red"))
            self.conn.rollback()
            raise

    def get_text_content(self, file_hash: str) -> Optional[str]:
        """Get text content for a file by hash"""
        try:
            self.cursor.execute(
                "SELECT text_content FROM processed_files WHERE file_hash = ?",
                (file_hash,)
            )
            row = self.cursor.fetchone()
            return row['text_content'] if row else None
        except Exception as e:
            print(colored(f"Error retrieving text content: {str(e)}", "red"))
            raise

    def get_json_result(self, file_hash: str) -> Optional[Dict]:
        """Get JSON result for a file by hash"""
        try:
            self.cursor.execute(
                "SELECT json_result FROM processed_files WHERE file_hash = ?",
                (file_hash,)
            )
            row = self.cursor.fetchone()
            return json.loads(row['json_result']) if row and row['json_result'] else None
        except Exception as e:
            print(colored(f"Error retrieving JSON result: {str(e)}", "red"))
            raise

    def __del__(self):
        """Close database connection"""
        try:
            if hasattr(self, 'conn'):
                self.conn.close()
        except Exception as e:
            print(colored(f"Error closing database connection: {str(e)}", "red")) 