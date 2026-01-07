from jose import jwt, JWTError

SECRET_KEY = "super-secret-key"
ALGORITHM = "HS256"


def decode_jwt(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None
