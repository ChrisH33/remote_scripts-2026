"""
file_mover.py
-------------
Helpers for uploading files to Google Drive and moving them to a
local "Processed" directory afterwards.
"""

import os
import shutil
import errno
from config import logger
from googleapiclient.http import MediaFileUpload


def is_file_ready(file_path: str) -> bool:
    """
    Return True if the file can be opened for reading (i.e. it exists and
    is not locked by another process).  Returns False on permission/busy
    errors, re-raises anything unexpected.
    """
    try:
        with open(file_path, 'rb'):
            return True
    except OSError as e:
        if e.errno in (errno.EACCES, errno.EBUSY):
            return False
        raise


def move_to_processed(file_path: str, dir: str) -> bool:
    """
    Move `file_path` into `dir`.  Returns True on success, False on failure.
    Checks the file is ready (not locked) before attempting the move.
    """
    if not is_file_ready(file_path):
        return False
    try:
        file_name = os.path.basename(file_path)
        # BUG FIX: `os.path.join(dir, os.path.join(file_name))` had a
        # pointless inner os.path.join call that did nothing.
        dest_path = os.path.join(dir, file_name)
        shutil.move(file_path, dest_path)
        logger.info(f"Moved {file_name} → {dir}")
        return True
    except Exception as e:
        logger.error(f"Failed to move {file_path} to processed: {e}")
        return False


def upload_file_to_google(file_path: str, FOLDER_ID: str, service) -> bool:
    """
    Upload `file_path` to the given Google Drive folder.

    If a file with the same name already exists in the folder, appends a
    numeric suffix (e.g. `report_(1).pdf`) until a unique name is found.

    Returns True on success, False on failure.
    """
    if not is_file_ready(file_path):
        return False

    try:
        base_name = os.path.basename(file_path)
        name, ext = os.path.splitext(base_name)
        new_name  = base_name

        def _escape(n: str) -> str:
            # BUG FIX: original code used replace("'", "\\") which produces a
            # bare backslash instead of \' — making the Drive query malformed.
            # Google Drive query strings require single quotes escaped as \'.
            return n.replace("'", "\\'")

        def _name_exists(candidate: str) -> bool:
            query = (
                f"'{FOLDER_ID}' in parents "
                f"and name = '{_escape(candidate)}' "
                f"and trashed = false"
            )
            results = service.files().list(
                q=query, spaces='drive', fields='files(id, name)'
            ).execute()
            return bool(results.get('files'))

        # Find a unique filename in the destination folder
        counter = 1
        while _name_exists(new_name):
            new_name = f"{name}_({counter}){ext}"
            counter += 1

        # Upload with the unique name
        file_metadata = {'name': new_name, 'parents': [FOLDER_ID]}
        media = MediaFileUpload(file_path, resumable=True)
        uploaded = service.files().create(
            body=file_metadata, media_body=media, fields='id'
        ).execute()

        logger.info(f"Uploaded '{base_name}' as '{new_name}' (ID: {uploaded.get('id')})")
        return True

    except Exception as e:
        logger.error(f"Failed to upload {file_path}: {e}")
        return False