from xmlrpc.server import SimpleXMLRPCServer
from pymongo import MongoClient
from cryptography.fernet import Fernet
from hashlib import sha256
from datetime import datetime

client = MongoClient("mongodb://localhost:27017")
db = client.message_buffer
users = db.users
messages = db.messages
groups = db.groups

cipher = Fernet(b'5Gimyni-XZiHb88wmXggl9_6CUguMlDffo0I3DQBrpM=')

# --- Utilisateurs ---
def register(username, password):
    if users.find_one({"username": username}):
        return "Utilisateur déjà existant"
    users.insert_one({
        "username": username,
        "password": sha256(password.encode()).hexdigest()
    })
    return "Compte créé"

def authenticate(username, password):
    return users.find_one({
        "username": username,
        "password": sha256(password.encode()).hexdigest()
    }) is not None

# --- Messages ---
def production(sender, content, recipient):
    messages.insert_one({
        "sender": sender,
        "recipient": recipient,
        "content": cipher.encrypt(content.encode()).decode(),
        "timestamp": datetime.utcnow().isoformat()
    })
    return "Message envoyé"

def consommateur(recipient):
    inbox = list(messages.find({"recipient": recipient}))
    messages.delete_many({"recipient": recipient})
    return [{
        "sender": m["sender"],
        "content": m["content"],
        "timestamp": m["timestamp"]
    } for m in inbox]

# --- Groupes ---
def create_group(owner, name):
    if groups.find_one({"name": name}):
        return "Groupe existant"
    groups.insert_one({"name": name, "owner": owner, "members": [owner]})
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
    for m in grp["members"]:
        if m != sender:
            production(sender, content, m)
    return "Message groupe envoyé"

# --- RPC ---
server = SimpleXMLRPCServer(("0.0.0.0", 9000), allow_none=True)
for f in [
    register, authenticate, production, consommateur,
    create_group, add_member, remove_member,
    list_members, is_group, send_group_message
]:
    server.register_function(f)

print("Serveur Mongo RPC actif (9000)")
server.serve_forever()
