"""
BioLinker - Firestore DB singleton
Centralised Firestore client so routers can import `db` without
re-running initialisation logic that lives in main.py.

Usage:
    from firestore_db import db
"""
import os
import firebase_admin
from firebase_admin import firestore
from services.logging_config import get_logger

log = get_logger("biolinker.firestore_db")

db = None

try:
    if not firebase_admin._apps:
        cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "./serviceAccountKey.json")
        if os.path.exists(cred_path):
            cred = firebase_admin.credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)

    if firebase_admin._apps:
        db = firestore.client()
    else:
        log.warning("firebase_not_initialized", detail="Firestore disabled")
except Exception as e:
    db = None
    log.error("firestore_init_failed", error=str(e))
