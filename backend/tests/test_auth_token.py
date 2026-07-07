from fastapi.testclient import TestClient
from app.main import app
from app.db.database import get_db, Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import pytest
from app.services.users import UserService

# Setup SQLite in-memory database for testing
engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(name="db_session")
def fixture_db_session():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)

@pytest.fixture(name="client")
def fixture_client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()

def test_get_auth_token(client, db_session) -> None:
    # 1. Create a user
    UserService(db_session).create_user(
        name="Test User",
        email="test@example.com",
        password="testpassword123"
    )

    # 2. Login to get cookie session
    login_response = client.post(
        "/api/auth/login",
        json={"email": "test@example.com", "password": "testpassword123"}
    )
    assert login_response.status_code == 200
    login_data = login_response.json()
    assert "accessToken" in login_data

    # 3. Call GET /api/auth/token to get a new token using the cookie
    token_response = client.get("/api/auth/token")
    assert token_response.status_code == 200
    token_data = token_response.json()
    assert "accessToken" in token_data
    assert token_data["user"]["email"] == "test@example.com"
