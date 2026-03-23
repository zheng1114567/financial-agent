import os
from dotenv import load_dotenv

def deepseek_get_env(env_file=r'C:\Users\Administrator\Desktop\app\utils\.env'):
    load_dotenv(env_file)
    API_KEY = os.getenv("DEEPSEEK_API_KEY")
    BASE_URL = os.getenv("DEEPSEEK_BASE_URL")
    return API_KEY, BASE_URL
deepseek_api_key, deepseek_base_url = deepseek_get_env()

def qwen_get_env(env_file=r'C:\Users\Administrator\Desktop\app\utils\.env'):
    load_dotenv(env_file)
    API_KEY = os.getenv("QWEN_API_KEY")
    BASE_URL = os.getenv("QWEN_BASE_URL")
    return API_KEY, BASE_URL
qwen_api_key, qwen_base_url = qwen_get_env()


