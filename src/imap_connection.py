import imaplib
import os
import logging
import yaml
from typing import List, Dict, Any
import email
from email.header import decode_header

class IMAPConnectionError(Exception):
    """Raised when IMAP connection fails."""
    pass

def connect_imap(host: str, user: str, password: str, port: int = 993):
    try:
        imap = imaplib.IMAP4_SSL(host, port)
        imap.login(user, password)
        logging.info(f"IMAP connection established with {host} as {user}.")
        return imap
    except imaplib.IMAP4.error as e:
        logging.error(f"IMAP login failed: {e}")
        raise IMAPConnectionError(f"IMAP login failed: {e}")
    except Exception as e:
        logging.error(f"IMAP connection failed: {e}")
        raise IMAPConnectionError(f"IMAP connection failed: {e}")

def load_imap_queries(config_path: str = "config/config.yaml"):
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    queries = config.get('imap_queries')
    if not queries:
        query = config.get('imap_query')
        if query:
            queries = [query]
        else:
            raise ValueError("No 'imap_queries' or 'imap_query' found in config.")
    if not isinstance(queries, list):
        raise ValueError("'imap_queries' must be a list of IMAP search strings.")
    for q in queries:
        if not isinstance(q, str) or len(q.strip()) == 0:
            raise ValueError(f"IMAP query must be a non-empty string: {q}")
    logging.info(f"Loaded IMAP queries: {queries}")
    return queries

def search_emails_excluding_processed(imap, queries: List[str], processed_tag: str = '[AI-Processed]') -> List[bytes]:
    try:
        imap.select('INBOX')
        all_ids = set()
        for q in queries:
            status, data = imap.search(None, f'{q} NOT KEYWORD "{processed_tag}"')
            if status != 'OK':
                logging.error(f"IMAP search failed on query: {q}")
                continue
            ids = data[0].split()
            all_ids.update(ids)
        logging.info(f"Found {len(all_ids)} unprocessed emails matching queries.")
        return list(all_ids)
    except Exception as e:
        logging.error(f"IMAP search failed: {e}")
        raise IMAPConnectionError(f"IMAP search failed: {e}")

def decode_mime_header(header) -> str:
    if not header:
        return ''
    parts = decode_header(header)
    decoded = ''
    for part, enc in parts:
        if isinstance(part, bytes):
            decoded += part.decode(enc or 'utf-8', errors='replace')
        else:
            decoded += str(part)
    return decoded

def fetch_and_parse_emails(imap, msg_ids: List[bytes]) -> List[Dict[str, Any]]:
    parsed = []
    for msg_id in msg_ids:
        typ, data = imap.fetch(msg_id, '(RFC822)')
        if typ != 'OK':
            logging.error(f'Failed to fetch msg id {msg_id}: {data}')
            continue
        raw_email = data[0][1]
        msg = email.message_from_bytes(raw_email)
        subject = decode_mime_header(msg.get('Subject'))
        sender = decode_mime_header(msg.get('From'))
        date = decode_mime_header(msg.get('Date'))
        # Parse body, handling multipart
        body = ''
        if msg.is_multipart():
            for part in msg.walk():
                ctype = part.get_content_type()
                disp = part.get('Content-Disposition')
                if ctype == 'text/plain' and disp != 'attachment':
                    charset = part.get_content_charset() or 'utf-8'
                    body = part.get_payload(decode=True).decode(charset, errors='replace')
                    break
        else:
            charset = msg.get_content_charset() or 'utf-8'
            body = msg.get_payload(decode=True)
            if isinstance(body, bytes):
                body = body.decode(charset, errors='replace')
            elif not isinstance(body, str):
                body = ''
        parsed.append({
            'id': msg_id,
            'subject': subject,
            'sender': sender,
            'body': body,
            'date': date,
        })
    logging.info(f"Parsed {len(parsed)} emails.")
    return parsed
