from slowapi import Limiter
from slowapi.util import get_remote_address

# In-memory store: fine for a single uvicorn process. Use a Redis storage_uri if scaled out.
limiter = Limiter(key_func=get_remote_address)
