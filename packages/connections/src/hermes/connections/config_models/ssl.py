from pydantic import BaseModel, FilePath


class SSL(BaseModel, frozen=True):
    ca_path: FilePath
    cert_path: FilePath
    key_path: FilePath
