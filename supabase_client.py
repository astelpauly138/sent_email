import os
from supabase import create_client, Client

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    raise Exception("Supabase environment variables not set")

supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_SERVICE_KEY
)
