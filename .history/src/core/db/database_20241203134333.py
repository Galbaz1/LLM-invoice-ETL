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

                CREATE TABLE IF NOT EXISTS invoice_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_id INTEGER NOT NULL,
                    invoice_number TEXT,
                    invoice_date DATE,
                    due_date DATE,
                    amount_payable DECIMAL(10,2),
                    currency TEXT,
                    recipient TEXT,
                    method_of_payment TEXT,
                    primary_supplier TEXT,
                    supplier_email TEXT,
                    supplier_address TEXT,
                    supplier_iban TEXT,
                    supplier_vat_id TEXT,
                    supplier_kvk TEXT,
                    high_tax_base DECIMAL(10,2),
                    high_tax DECIMAL(10,2),
                    low_tax_base DECIMAL(10,2),
                    low_tax DECIMAL(10,2),
                    null_tax_base DECIMAL(10,2),
                    amount_excl_tax DECIMAL(10,2),
                    total_emballage DECIMAL(10,2),
                    has_errors BOOLEAN DEFAULT FALSE,
                    error_messages TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (file_id) REFERENCES processed_files(id)
                );

                CREATE INDEX IF NOT EXISTS idx_invoice_number ON invoice_data(invoice_number);
                CREATE INDEX IF NOT EXISTS idx_invoice_date ON invoice_data(invoice_date);
                CREATE INDEX IF NOT EXISTS idx_amount_payable ON invoice_data(amount_payable);
                CREATE INDEX IF NOT EXISTS idx_supplier_vat_id ON invoice_data(supplier_vat_id);
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
                    # Save detailed invoice data
                    self.save_invoice_data(existing['id'], json_result)
                
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
                
                # If we have JSON result, save detailed invoice data
                if json_result:
                    self.save_invoice_data(self.cursor.lastrowid, json_result)
                
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

    def save_invoice_data(self, file_id: int, data: Dict):
        """Save parsed invoice data to the detailed table"""
        try:
            # Extract supplier data
            supplier_data = data.get('details_supplier', {})
            tax_data = data.get('suppliers', [{}])[0] if data.get('suppliers') else {}
            error_data = data.get('error_handling', {})
            
            # Prepare error messages if any
            error_messages = None
            if error_data.get('has_errors'):
                error_messages = json.dumps([
                    {
                        'id': error.get('id'),
                        'message': error.get('message'),
                        'analysis': error.get('analysis')
                    }
                    for error in error_data.get('errors', [])
                ])

            # Insert into invoice_data table
            self.cursor.execute("""
                INSERT INTO invoice_data (
                    file_id, invoice_number, invoice_date, due_date,
                    amount_payable, currency, recipient, method_of_payment,
                    primary_supplier, supplier_email, supplier_address,
                    supplier_iban, supplier_vat_id, supplier_kvk,
                    high_tax_base, high_tax, low_tax_base, low_tax,
                    null_tax_base, amount_excl_tax, total_emballage,
                    has_errors, error_messages
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
            """, (
                file_id,
                data.get('invoice_number'),
                data.get('invoice_date'),
                data.get('due_date'),
                data.get('amount_payable'),
                data.get('currency'),
                data.get('recipient'),
                data.get('method_of_payment'),
                data.get('primary_supplier'),
                supplier_data.get('email'),
                supplier_data.get('address'),
                supplier_data.get('iban'),
                supplier_data.get('vat_id'),
                supplier_data.get('kvk'),
                tax_data.get('high_tax_base'),
                tax_data.get('high_tax'),
                tax_data.get('low_tax_base'),
                tax_data.get('low_tax'),
                tax_data.get('null_tax_base'),
                tax_data.get('amount_excl_tax'),
                data.get('total_emballage'),
                error_data.get('has_errors', False),
                error_messages
            ))
            self.conn.commit()
            print(colored("✓ Saved detailed invoice data to database", "green"))
        except Exception as e:
            print(colored(f"Error saving invoice data: {str(e)}", "red"))
            self.conn.rollback()
            raise

    def __del__(self):
        """Close database connection"""
        try:
            if hasattr(self, 'conn'):
                self.conn.close()
        except Exception as e:
            print(colored(f"Error closing database connection: {str(e)}", "red")) 