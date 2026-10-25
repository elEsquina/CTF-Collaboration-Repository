from datetime import datetime
from enum import Enum
from typing import Generic, TypeVar
from pydantic import BaseModel, ConfigDict, Field, field_validator

class Category(str, Enum):
    web = 'web'
    pwn = 'pwn'
    reverse = 'reverse-engineering'
    crypto = 'cryptography'
    forensics = 'forensics'
    osint = 'osint'
    misc = 'miscellaneous'

class Metadata(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=100000)
    flag: str = Field(min_length=1, max_length=4096)
    category: Category
    requires_docker: bool

    @field_validator('name', 'description', 'flag')
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError('This field cannot be blank.')
        return value

class MetadataPatch(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str | None = None
    description: str | None = None
    flag: str | None = None
    category: Category | None = None
    requires_docker: bool | None = None

class Summary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: str
    category: Category
    requires_docker: bool
    original_filename: str
    created_at: datetime
    updated_at: datetime

class Detail(Summary):
    flag: str

class Login(BaseModel):
    password: str = Field(max_length=4096)

T = TypeVar('T')

class Envelope(BaseModel, Generic[T]):
    data: T

class SessionInfo(BaseModel):
    authenticated: bool
    csrf_token: str | None = None

class Stats(BaseModel):
    total: int
    categories: int
    docker: int
    static: int

class ChallengeList(Envelope[list[Summary]]):
    stats: Stats
