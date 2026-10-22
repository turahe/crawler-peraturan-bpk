from dotenv import load_dotenv

load_dotenv()

from .models import Base  # noqa: E402

__all__ = ["Base"]
