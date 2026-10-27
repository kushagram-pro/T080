from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str

    #JWT
    SECRET_KEY: str
    REFRESH_SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    PASSWORD_RESET_EXPIRE_MINUTES: int = 30

    #SendGrid
    SENDGRID_API_KEY: str
    SENDGRID_FROM_EMAIL: str = "kushagra.m5022@gmail.com"

    #App
    ALLOWED_EMAIL_DOMAIN: str = "lnmiit.ac.in"
    FRONTEND_ORIGIN: str = "http://localhost:5173"
    COOKIE_SECURE: bool = False  # set True in production (HTTPS only)

    class Config:
        env_file = ".env"

settings = Settings()
