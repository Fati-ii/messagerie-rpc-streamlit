# mongo.py
import xmlrpc.client
from xmlrpc.server import SimpleXMLRPCServer, SimpleXMLRPCRequestHandler
from pymongo import MongoClient
from cryptography.fernet import Fernet
from hashlib import sha256
from datetime import datetime
import os
from config import Config

# connexion DB
client = MongoClient(Config.MONGO_URI)
db = client[Config.MONGO_DB_NAME]
users = db.users
messages = db.messages
groups = db.groups

cipher = Fernet(Config.FERNET_KEY)

# Client RPC vers MySQL (Secondaire pour redondance)
# On utilise localhost car généralement sur même réseau, ou via Config
mysql_rpc = xmlrpc.client.ServerProxy(f"http://localhost:{Config.MYSQL_RPC_PORT}/")

# --- Helpers ---
def hash_password(password, salt=None):
    if not salt:
        salt = os.urandom(16).hex()
    # Sha256(salt + password)
    hashed = sha256((salt + password).encode()).hexdigest()
    return f"{salt}${hashed}"

def verify_password(stored_password, provided_password):
    try:
        salt, hash_val = stored_password.split('$')
        return hash_password(provided_password, salt) == stored_password
    except ValueError:
        # Fallback pour anciens mots de passe (pas de $)
        return sha256(provided_password.encode()).hexdigest() == stored_password

# --- Utilisateurs ---
def register(username, password):
    if users.find_one({"username": username}):
        return "Utilisateur déjà existant"
    
    hashed_pw = hash_password(password)
    users.insert_one({
        "username": username,
        "password": hashed_pw
    })
    
    # Replication MySQL
    try:
        mysql_rpc.create_user(username, hashed_pw)
    except Exception as e:
        print(f"WARNING: Echec replication MySQL (create_user): {e}")

    return "Compte créé"

def update_last_seen(username):
    users.update_one({"username": username}, {"$set": {"last_seen": datetime.utcnow().isoformat()}})

def authenticate(username, password):
    user = users.find_one({"username": username})
    if not user:
        return False
    
    if verify_password(user["password"], password):
        update_last_seen(username)
        return True
    return False

def get_user_status(username):
    user = users.find_one({"username": username})
    if not user or "last_seen" not in user:
        return "Hors ligne"
    
    last = datetime.fromisoformat(user["last_seen"])
    diff = (datetime.utcnow() - last).total_seconds()
    
    if diff < 30: # Considéré en ligne si activité < 30s
        return "En ligne"
    else:
        # Format HH:MM
        ts_str = last.strftime("%H:%M")
        return f"Vu à {ts_str}"

# --- Messages ---
def production(sender, content, recipient, group_id=None):
    encrypted_content = cipher.encrypt(content.encode()).decode()
    timestamp = datetime.utcnow().isoformat()
    
    # 1. Sauvegarde Mongo
    doc = {
        "sender": sender,
        "recipient": recipient,
        "content": encrypted_content,
        "timestamp": timestamp,
        "read": False, # Pour ACK
        "group": group_id
    }
    msg_id = messages.insert_one(doc).inserted_id

    # 2. Replication MySQL (Best Effort)
    try:
        # Envoie le contenu chiffré pour stockage
        mysql_rpc.store_message(sender, recipient, encrypted_content, timestamp)
    except Exception as e:
        print(f"WARNING: Echec replication MySQL (store_message): {e}")

    return "Message envoyé"

def get_unread_messages(recipient):
    update_last_seen(recipient)
    # Lecture sans suppression (Peek)
    inbox = list(messages.find({"recipient": recipient}))
    # On renvoie l'ID pour que le client puisse ACK
    return [{
        "id": str(m["_id"]),
        "sender": m["sender"],
        "content": m["content"],
        "timestamp": m["timestamp"],
        "group": m.get("group")
    } for m in inbox]

def ack_messages(recipient, message_ids):
    # Suppression effective des messages après confirmation de réception
    from bson.objectid import ObjectId
    try:
        ids = [ObjectId(mid) for mid in message_ids]
        result = messages.delete_many({"_id": {"$in": ids}, "recipient": recipient})
        return f"{result.deleted_count} messages supprimés"
    except Exception as e:
        return f"Erreur ACK: {e}"

# --- Groupes ---
def create_group(owner, name):
    if groups.find_one({"name": name}):
        return "Groupe existant"
    groups.insert_one({"name": name, "owner": owner, "members": [owner]})
    
    # Replication MySQL
    try:
        mysql_rpc.store_group(name, owner)
    except Exception as e:
        print(f"WARNING: Echec replication MySQL (store_group): {e}")

    return "Groupe créé"

def add_member(owner, name, member):
    grp = groups.find_one({"name": name})
    if not grp or grp["owner"] != owner:
        return "Action interdite"
    if member in grp["members"]:
        return "Déjà membre"
    groups.update_one({"name": name}, {"$push": {"members": member}})
    return "Membre ajouté"

def remove_member(owner, name, member):
    grp = groups.find_one({"name": name})
    if not grp or grp["owner"] != owner:
        return "Action interdite"
    groups.update_one({"name": name}, {"$pull": {"members": member}})
    return "Membre supprimé"

def list_members(name):
    grp = groups.find_one({"name": name})
    return grp["members"] if grp else []

def is_group(name):
    return groups.find_one({"name": name}) is not None

def send_group_message(sender, name, content):
    grp = groups.find_one({"name": name})
    if not grp:
        return "Groupe inconnu"
        
    count = 0
    for m in grp["members"]:
        if m != sender:
            # On utilise production() pour bénéficier de la logique de chiffrement et réplication mysql
            # FIX: Appel unique + ajout context groupe
            production(sender, content, m, group_id=name)
            count += 1
    return f"Message envoyé à {count} membres"

def get_groups_for_user(username):
    # Retourne la liste des groupes dont l'utilisateur est membre
    user_groups = list(groups.find({"members": username}, {"_id": 0, "name": 1}))
    return [g["name"] for g in user_groups]

def leave_group(username, group_name):
    grp = groups.find_one({"name": group_name})
    if not grp:
        return "Groupe introuvable"
    
    if username == grp["owner"]:
        return "Le propriétaire ne peut pas quitter le groupe (supprimez-le si nécessaire)"
        
    if username not in grp["members"]:
        return "Vous n'êtes pas membre"
        
    groups.update_one({"name": group_name}, {"$pull": {"members": username}})
    return "Vous avez quitté le groupe"

def get_group_details(group_name):
    # Retourne infos complètes pour display
    grp = groups.find_one({"name": group_name}, {"_id": 0})
    if not grp:
        return {}
    return {
        "name": grp["name"],
        "owner": grp["owner"],
        "members": grp["members"],
        "count": len(grp["members"])
    }

# --- RPC ---
class RequestHandler(SimpleXMLRPCRequestHandler):
    rpc_paths = ('/RPC2',)

server = SimpleXMLRPCServer((Config.RPC_HOST, Config.RPC_PORT), requestHandler=RequestHandler, allow_none=True)
server.register_introspection_functions()

# Enregistrement des fonctions
for f in [
    register, authenticate, production, get_unread_messages, ack_messages,
    create_group, add_member, remove_member,
    list_members, is_group, send_group_message, get_groups_for_user,
    leave_group, get_group_details, get_user_status
]:
    server.register_function(f)

print(f"Serveur Mongo Gateway RPC actif ({Config.RPC_HOST}:{Config.RPC_PORT})")
server.serve_forever()
