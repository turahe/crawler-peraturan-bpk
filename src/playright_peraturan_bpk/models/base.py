from sqlalchemy import BigInteger, Integer
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


PRIMARY_KEY_TYPE = BigInteger().with_variant(Integer, "sqlite")
