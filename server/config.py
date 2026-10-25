from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / '.env', extra='ignore')
    ctf_shared_password: str = Field(min_length=1)
    session_secret: str = Field(min_length=32)
    cookie_secure: bool = False
    session_max_age: int = Field(default=43200, gt=0)
    allowed_origins: str = 'http://localhost:5173,http://127.0.0.1:5173'
    data_dir: Path = BASE_DIR
    max_upload_bytes: int = Field(default=50 * 1024 * 1024, gt=0)
    max_extracted_bytes: int = Field(default=250 * 1024 * 1024, gt=0)
    max_file_bytes: int = Field(default=100 * 1024 * 1024, gt=0)
    max_zip_members: int = Field(default=5000, gt=0)
    max_compression_ratio: int = Field(default=200, gt=0)

    @property
    def root(self):
        return (BASE_DIR / self.data_dir).resolve()
