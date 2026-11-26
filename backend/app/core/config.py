"""Application configuration with production fail-closed validation."""
import os


class Settings:
    @property
    def ENV(self) -> str:
        return os.environ.get("ENV", "development").lower()

    @property
    def SECRET_KEY(self) -> str:
        return os.environ.get("SECRET_KEY", "dev-secret-change-me-in-production")

    @property
    def DATABASE_URL(self) -> str:
        return os.environ.get("DATABASE_URL", "sqlite:///./data/campusconnect.db")

    @property
    def SESSION_EXPIRE_MINUTES(self) -> int:
        return int(os.environ.get("SESSION_EXPIRE_MINUTES", "1440"))

    @property
    def DEBUG(self) -> bool:
        return os.environ.get("DEBUG", "true").lower() == "true"

    @property
    def COOKIE_SECURE(self) -> bool:
        val = os.environ.get("COOKIE_SECURE", "")
        if val:
            return val.lower() == "true"
        return self.ENV == "production"

    @property
    def ALLOWED_ORIGIN(self) -> str:
        return os.environ.get("ALLOWED_ORIGIN", "").rstrip("/")

    @property
    def EXPOSE_RESET_TOKEN_FOR_TESTS(self) -> bool:
        return (
            self.ENV == "test"
            and os.environ.get("EXPOSE_RESET_TOKEN_FOR_TESTS", "false").lower() == "true"
        )

    @property
    def SUPPORT_EMAIL(self) -> str:
        return os.environ.get("SUPPORT_EMAIL", "support@campusconnect.local")

    def validate_production_settings(self) -> None:
        """Fail closed if production is misconfigured."""
        if self.ENV != "production":
            return
        weak_defaults = {
            "",
            "dev-secret-change-me-in-production",
            "change-me-to-a-random-string",
            "dev-only-change-me-32-chars-minimum-secret",
        }
        if self.SECRET_KEY in weak_defaults or len(self.SECRET_KEY) < 32:
            raise RuntimeError(
                "Production startup blocked: SECRET_KEY must be at least 32 characters and not a default value."
            )
        if self.DEBUG:
            raise RuntimeError("Production startup blocked: DEBUG must be false in production.")
        if not self.COOKIE_SECURE:
            raise RuntimeError("Production startup blocked: COOKIE_SECURE must be true in production.")


settings = Settings()
