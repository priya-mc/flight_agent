"""
Database module for flight search sessions.

This module handles all SQLite database operations for storing and managing
flight search sessions, including session data, conversation history, and results.
"""

import sqlite3
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional


# Database configuration
DB_PATH = "flight_searches.db"


def init_database():
    """Initialize the SQLite database for storing search sessions."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create sessions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS search_sessions (
            session_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            step TEXT DEFAULT 'input',
            messages TEXT,
            research_brief TEXT,
            flight_results TEXT,
            chat_messages TEXT,
            status TEXT DEFAULT 'active',
            token_count INTEGER DEFAULT 0,
            is_summarized BOOLEAN DEFAULT FALSE,
            summarized_at TIMESTAMP,
            original_token_count INTEGER,
            summarized_token_count INTEGER,
            current_agent TEXT DEFAULT 'flight_agent',
            last_handoff TEXT
        )
    ''')
    
    # Add new columns to existing table if they don't exist
    try:
        cursor.execute('ALTER TABLE search_sessions ADD COLUMN token_count INTEGER DEFAULT 0')
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        cursor.execute('ALTER TABLE search_sessions ADD COLUMN is_summarized BOOLEAN DEFAULT FALSE')
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        cursor.execute('ALTER TABLE search_sessions ADD COLUMN summarized_at TIMESTAMP')
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        cursor.execute('ALTER TABLE search_sessions ADD COLUMN original_token_count INTEGER')
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        cursor.execute('ALTER TABLE search_sessions ADD COLUMN summarized_token_count INTEGER')
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        cursor.execute('ALTER TABLE search_sessions ADD COLUMN current_agent TEXT DEFAULT "flight_agent"')
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        cursor.execute('ALTER TABLE search_sessions ADD COLUMN last_handoff TEXT')
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    conn.commit()
    conn.close()


def save_session_to_db(session_id: str, session_data: Dict):
    """
    Save session data to database.
    
    Args:
        session_id: Unique identifier for the session
        session_data: Dictionary containing session information
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Convert lists/dicts to JSON strings
    messages_json = json.dumps(session_data.get('messages', []))
    chat_messages_json = json.dumps(session_data.get('chat_messages', []))
    
    cursor.execute('''
        INSERT OR REPLACE INTO search_sessions 
        (session_id, title, updated_at, step, messages, research_brief, flight_results, chat_messages, status,
         token_count, is_summarized, summarized_at, original_token_count, summarized_token_count, current_agent, last_handoff)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        session_id,
        session_data.get('title', f'Flight Search {session_id[:8]}'),
        datetime.now().isoformat(),
        session_data.get('step', 'input'),
        messages_json,
        session_data.get('research_brief', ''),
        session_data.get('flight_results', ''),
        chat_messages_json,
        session_data.get('status', 'active'),
        session_data.get('token_count', 0),
        session_data.get('is_summarized', False),
        session_data.get('summarized_at'),
        session_data.get('original_token_count'),
        session_data.get('summarized_token_count'),
        session_data.get('current_agent', 'flight_agent'),
        json.dumps(session_data.get('last_handoff')) if session_data.get('last_handoff') else None
    ))
    
    conn.commit()
    conn.close()


def load_session_from_db(session_id: str) -> Optional[Dict]:
    """
    Load session data from database.
    
    Args:
        session_id: Unique identifier for the session
        
    Returns:
        Dictionary containing session data or None if not found
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT title, step, messages, research_brief, flight_results, chat_messages, status, created_at, updated_at,
               token_count, is_summarized, summarized_at, original_token_count, summarized_token_count, current_agent, last_handoff
        FROM search_sessions WHERE session_id = ?
    ''', (session_id,))
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            'title': row[0],
            'step': row[1],
            'messages': json.loads(row[2]) if row[2] else [],
            'research_brief': row[3],
            'flight_results': row[4],
            'chat_messages': json.loads(row[5]) if row[5] else [],
            'status': row[6],
            'created_at': row[7],
            'updated_at': row[8],
            'token_count': row[9] or 0,
            'is_summarized': bool(row[10]) if row[10] is not None else False,
            'summarized_at': row[11],
            'original_token_count': row[12],
            'summarized_token_count': row[13],
            'current_agent': row[14] or 'flight_agent',
            'last_handoff': json.loads(row[15]) if row[15] else None
        }
    return None


def get_all_sessions() -> List[Dict]:
    """
    Get all search sessions from database.
    
    Returns:
        List of dictionaries containing session metadata
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT session_id, title, step, status, created_at, updated_at, token_count, is_summarized
        FROM search_sessions 
        ORDER BY updated_at DESC
    ''')
    
    rows = cursor.fetchall()
    conn.close()
    
    return [
        {
            'session_id': row[0],
            'title': row[1],
            'step': row[2],
            'status': row[3],
            'created_at': row[4],
            'updated_at': row[5],
            'token_count': row[6] or 0,
            'is_summarized': bool(row[7]) if row[7] is not None else False
        }
        for row in rows
    ]


def delete_session_from_db(session_id: str):
    """
    Delete a session from database.
    
    Args:
        session_id: Unique identifier for the session to delete
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM search_sessions WHERE session_id = ?', (session_id,))
    conn.commit()
    conn.close()


def update_session_title(session_id: str, new_title: str):
    """
    Update the title of an existing session.
    
    Args:
        session_id: Unique identifier for the session
        new_title: New title for the session
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE search_sessions 
        SET title = ?, updated_at = ?
        WHERE session_id = ?
    ''', (new_title, datetime.now().isoformat(), session_id))
    
    conn.commit()
    conn.close()


def get_session_count() -> int:
    """
    Get the total number of sessions in the database.
    
    Returns:
        Total count of sessions
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM search_sessions')
    count = cursor.fetchone()[0]
    
    conn.close()
    return count


def get_sessions_by_status(status: str) -> List[Dict]:
    """
    Get sessions filtered by status.
    
    Args:
        status: Status to filter by ('active', 'completed', etc.)
        
    Returns:
        List of sessions with the specified status
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT session_id, title, step, status, created_at, updated_at
        FROM search_sessions 
        WHERE status = ?
        ORDER BY updated_at DESC
    ''', (status,))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [
        {
            'session_id': row[0],
            'title': row[1],
            'step': row[2],
            'status': row[3],
            'created_at': row[4],
            'updated_at': row[5]
        }
        for row in rows
    ]


def cleanup_old_sessions(days_old: int = 30):
    """
    Delete sessions older than specified days.
    
    Args:
        days_old: Number of days after which sessions should be deleted
        
    Returns:
        Number of sessions deleted
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cutoff_date = datetime.now() - timedelta(days=days_old)
    
    cursor.execute('''
        DELETE FROM search_sessions 
        WHERE created_at < ?
    ''', (cutoff_date.isoformat(),))
    
    deleted_count = cursor.rowcount
    conn.commit()
    conn.close()
    
    return deleted_count


# Initialize database when module is imported
init_database()
