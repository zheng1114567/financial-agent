import os
from dotenv import load_dotenv

def get_env(env_file='.env'):
    load_dotenv(env_file)
    API_KEY = os.getenv("DEEPSEEK_API_KEY")
    BASE_URL = os.getenv("DEEPSEEK_BASE_URL")
    return API_KEY, BASE_URL
api_key, base_url = get_env()