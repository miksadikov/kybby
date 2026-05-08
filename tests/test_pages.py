from fastapi.testclient import TestClient
from uuid import uuid4

from app.main import app


client = TestClient(app)


def test_landing_page() -> None:
    response = client.get('/')
    assert response.status_code == 200
    assert 'Создайте бренд-стиль за минуты' in response.text


def test_register_get() -> None:
    response = client.get('/register')
    assert response.status_code == 200
    assert 'Регистрация' in response.text


def test_register_post_success() -> None:
    response = client.post(
        '/register',
        data={
            'name': 'Test User',
            'email': f'{uuid4().hex}@example.com',
            'password': 'strongpass123',
            'password_confirm': 'strongpass123',
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers['location'] == '/login?registered=1'


def test_register_login_logout_login_again() -> None:
    email = f"{uuid4().hex}@example.com"

    register_response = client.post(
        '/register',
        data={
            'name': 'Persistent User',
            'email': email,
            'password': 'strongpass123',
            'password_confirm': 'strongpass123',
        },
        follow_redirects=False,
    )
    assert register_response.status_code == 303

    login_response_1 = client.post(
        '/login',
        data={
            'email': email,
            'password': 'strongpass123',
        },
        follow_redirects=False,
    )
    assert login_response_1.status_code == 303
    assert login_response_1.headers['location'] == '/dashboard'

    logout_response = client.get('/logout', follow_redirects=False)
    assert logout_response.status_code == 303

    login_response_2 = client.post(
        '/login',
        data={
            'email': email,
            'password': 'strongpass123',
        },
        follow_redirects=False,
    )
    assert login_response_2.status_code == 303
    assert login_response_2.headers['location'] == '/dashboard'
