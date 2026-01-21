# mysql_secondary_server.py
from xmlrpc.server import SimpleXMLRPCServer
import mysql.connector
from config import Config

def get_db_connection():
    return mysql.connector.connect(
        host=Config.MYSQL_HOST,
        user=Config.MYSQL_USER,
        password=Config.MYSQL_PASSWORD,
        database=Config.MYSQL_DB_NAME
    )

# Initial connection to test
try:
    db = get_db_connection()
    db.close()
except Exception as e:
    print(f"Erreur de connexion MySQL au démarrage: {e}")

def store_message(sender, recipient, content, timestamp):
    try:
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO messages (sender, recipient, content, timestamp) VALUES (%s,%s,%s,%s)",
            (sender, recipient, content, timestamp)
        )
        db.commit()
        cursor.close()
        db.close()
        return True
    except Exception as e:
        print(f"MYSQL ERROR store_message: {e}")
        return False

def create_user(username, password_hash):
    try:
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO users (username, password) VALUES (%s, %s)",
            (username, password_hash)
        )
        db.commit()
        cursor.close()
        db.close()
        return True
    except mysql.connector.errors.IntegrityError:
        return "Utilisateur MySQL déjà existant"
    except Exception as e:
        print(f"MYSQL ERROR create_user: {e}")
        return False

def store_group(name, owner):
    try:
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO chat_groups (name, owner) VALUES (%s,%s)",
            (name, owner)
        )
        db.commit()
        cursor.close()
        db.close()
        return "Groupe enregistré "
    except mysql.connector.errors.IntegrityError:
        return "Groupe déjà existant "
    except Exception as e:
        print(f"MYSQL ERROR store_group: {e}")
        return str(e)


server = SimpleXMLRPCServer((Config.RPC_HOST, Config.MYSQL_RPC_PORT), allow_none=True)
server.register_function(store_message)
server.register_function(store_group)
server.register_function(create_user)
print(f"Serveur MySQL RPC actif ({Config.RPC_HOST}:{Config.MYSQL_RPC_PORT})")
server.serve_forever()
