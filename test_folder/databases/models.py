import sqlalchemy as sa
import sqlalchemy.orm as so
from sqlalchemy.orm import Mapped

Base = so.declarative_base()




class Master(Base):
    __tablename__ = "master"
    id: so.Mapped[int] = so.mapped_column(primary_key=True, autoincrement=True)
    username: so.Mapped[str] = so.mapped_column(unique=True)
    email: so.Mapped[str] = so.mapped_column(unique=True)
    hash_pass: so.Mapped[str]


class Password(Base):
    __tablename__ = "passwords"
    id: so.Mapped[int] = so.mapped_column(primary_key=True, autoincrement=True)
    app: so.Mapped[str]
    email: so.Mapped[str|None]
    phone_number: so.Mapped[str | None]
    username: so.Mapped[str]
    enc_pass: so.Mapped[str]




