import sqlalchemy as sa
import sqlalchemy.orm as so
from sqlalchemy.orm import Mapped

Base = so.declarative_base()




class Master(Base):
    __tablename__ = "master"
    id: so.Mapped[int] = so.mapped_column(primary_key=True, autoincrement=True)
    username: so.Mapped[str] = so.mapped_column(unique=True)
    hash_pass: so.Mapped[str] = so.mapped_column(unique=True)


class Password(Base):
    __tablename__ = "password"