import os
from dotenv import load_dotenv

# Charger les variables depuis .env s'il existe
load_dotenv()

class Config:
    # MongoDB
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "message_buffer")

    # MySQL
    MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
    MYSQL_USER = os.getenv("MYSQL_USER", "rpc_user")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "rpc_password")
    MYSQL_DB_NAME = os.getenv("MYSQL_DB_NAME", "message_buffer")
    MYSQL_RPC_PORT = int(os.getenv("MYSQL_RPC_PORT", 9001))

    # Security
    FERNET_KEY = os.getenv("FERNET_KEY", "5Gimyni-XZiHb88wmXggl9_6CUguMlDffo0I3DQBrpM=").encode()
    
    # RPC
    RPC_HOST = os.getenv("RPC_HOST", "0.0.0.0")
    RPC_PORT = int(os.getenv("RPC_PORT", 9000))
