from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from ..deps import get_current_user
from ..supabase_client import db_insert, db_select, db_update, db_delete
from ..gemini_client import embed_text
from ..file_processing import extract_text, chunk_text, format_embedding_for_pg, MAX_FILE_SIZE_BYTES

router = APIRouter(prefix="/api/notes", tags=["notes"])

ALLOWED_TYPES = {"pdf", "docx", "txt"}


@router.post("")
async def upload_note(
    file: UploadFile = File(...),
    title: str | None = Form(None),
    user: dict = Depends(get_current_user),
):
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported file type '.{ext}'. Please upload PDF, DOCX, or TXT.")

    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="File is too large. Please keep uploads under 8 MB.")

    try:
        text = extract_text(file_bytes, ext)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read this file: {e}")

    if not text.strip():
        raise HTTPException(status_code=400, detail="No readable text was found in this file (it may be a scanned image with no text layer).")

    note_title = (title or file.filename).strip()

    # 1. Create the note row up front, marked "processing"
    note_rows = await db_insert("notes", {
        "user_id": user["id"],
        "title": note_title,
        "filename": file.filename,
        "file_type": ext,
        "content_text": text,
        "status": "processing",
    })
    note = note_rows[0]
    note_id = note["id"]

    # 2. Chunk the text
    chunks = chunk_text(text)
    if not chunks:
        await db_update("notes", {"id": f"eq.{note_id}", "user_id": f"eq.{user['id']}"}, {"status": "error"})
        raise HTTPException(status_code=400, detail="This file's text could not be split into chunks.")

    # 3. Embed each chunk and prepare rows for bulk insert
    chunk_rows = []
    for idx, chunk in enumerate(chunks):
        try:
            embedding = await embed_text(chunk, task_type="RETRIEVAL_DOCUMENT")
        except Exception as e:
            await db_update("notes", {"id": f"eq.{note_id}", "user_id": f"eq.{user['id']}"}, {"status": "error"})
            raise HTTPException(status_code=502, detail=f"Embedding failed on chunk {idx + 1}/{len(chunks)}: {e}")

        chunk_rows.append({
            "note_id": note_id,
            "user_id": user["id"],
            "chunk_index": idx,
            "content": chunk,
            "embedding": format_embedding_for_pg(embedding),
        })

    await db_insert("note_chunks", chunk_rows)
    await db_update("notes", {"id": f"eq.{note_id}", "user_id": f"eq.{user['id']}"}, {"status": "ready"})

    return {
        "note_id": note_id,
        "title": note_title,
        "chunk_count": len(chunks),
        "status": "ready",
    }


@router.get("")
async def list_notes(user: dict = Depends(get_current_user)):
    return await db_select("notes", {
        "user_id": f"eq.{user['id']}",
        "select": "id,title,filename,file_type,status,created_at",
        "order": "created_at.desc",
    })


@router.delete("/{note_id}")
async def delete_note(note_id: str, user: dict = Depends(get_current_user)):
    await db_delete("notes", {"id": f"eq.{note_id}", "user_id": f"eq.{user['id']}"})
    return {"deleted": True}
