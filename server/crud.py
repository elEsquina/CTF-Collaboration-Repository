import shutil
from sqlalchemy import select
from fastapi import HTTPException
from .models import Challenge
from .archive import slug

def get(db, challenge_id):
    challenge = db.get(Challenge, challenge_id)
    if not challenge:
        raise HTTPException(404, 'Challenge not found.')
    return challenge

def list_challenges(db, category=None, search=None):
    query = select(Challenge)
    if category:
        query = query.where(Challenge.category == category)
    if search:
        query = query.where(Challenge.name.icontains(search, autoescape=True))
    return db.scalars(query.order_by(Challenge.created_at.desc(), Challenge.id.desc())).all()

def create(db, metadata, filename, staged, storage):
    destination = None
    moved = False
    try:
        challenge = Challenge(**metadata.model_dump(), folder_path='', original_filename=filename)
        db.add(challenge)
        db.flush()
        challenge.folder_path = f'{challenge.id:03d}_{slug(challenge.name)}'
        destination = storage / challenge.folder_path
        staged.rename(destination)
        moved = True
        db.commit()
        return challenge
    except Exception:
        db.rollback()
        if moved and destination.exists():
            shutil.rmtree(destination)
        raise

def update(db, challenge, metadata):
    try:
        for key, value in metadata.model_dump().items():
            setattr(challenge, key, value)
        db.commit()
        return challenge
    except Exception:
        db.rollback()
        raise

def replace(db, challenge, metadata, filename, staged, storage):
    # New immutable generation: one database commit switches the active folder.
    # A failed commit leaves the old folder untouched.
    import uuid
    old = storage / challenge.folder_path
    new_name = f'{challenge.id:03d}_{slug(metadata.name)}_{uuid.uuid4().hex[:12]}'
    destination = storage / new_name
    moved = False
    try:
        staged.rename(destination)
        moved = True
        for key, value in metadata.model_dump().items():
            setattr(challenge, key, value)
        challenge.folder_path = new_name
        challenge.original_filename = filename
        db.commit()
    except Exception:
        db.rollback()
        if moved and destination.exists():
            shutil.rmtree(destination)
        raise
    shutil.rmtree(old, ignore_errors=True)
    return challenge
