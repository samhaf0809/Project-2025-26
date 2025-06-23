import sqlalchemy as sa
from models import Base

# Create an engine
engine = sa.create_engine('sqlite:///password_manager.db', echo=True)
Base.metadata.drop_all(engine)
Base.metadata.create_all(engine)



