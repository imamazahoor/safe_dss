from .database import SessionLocal
from .models import User


def run():
    db = SessionLocal()
    try:
        if db.query(User).count() == 0:
            db.add_all(
                [
                    User(name="ICU Nurse A", role="nurse"),
                    User(name="Physician B", role="physician"),
                    User(name="Admin C", role="admin"),
                ]
            )
            db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    run()
