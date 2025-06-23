import sqlalchemy as sa
import sqlalchemy.orm as so
from models import Master, Password
from test_folder.enc_test import hasher



def write(db_engine):
    session = so.Session(db_engine)
    username_1 = str(input("Enter username: "))
    email_1 = str(input("Enter email: "))
    password_1 = str(input("Enter password: "))
    hashed_pass = hasher(password_1)
    user = Master(username=username_1, email=email_1, hash_pass=hashed_pass)
    session.add(user)
    session.commit()



if __name__ == "__main__":
    engine = sa.create_engine('sqlite:///password_manager.db', echo=True)
    write(engine)