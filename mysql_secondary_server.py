from xmlrpc.server import SimpleXMLRPCServer
import mysql.connector

db = mysql.connector.connect(
    host="localhost",
    user="rpc_user",
    password="rpc_password",
    database="message_buffer"
)
cursor = db.cursor()

def store_message(sender, recipient, content, timestamp):
    cursor.execute(
        "INSERT INTO messages (sender, recipient, content, timestamp) VALUES (%s,%s,%s,%s)",
        (sender, recipient, content, timestamp)
    )
    db.commit()
    return True

# def store_group(name, owner):
#     cursor.execute(
#         "INSERT INTO chat_groups (name, owner) VALUES (%s,%s)",
#         (name, owner)
#     )
#     db.commit()
#     return True
def store_group(name, owner):
    try:
        cursor.execute(
            "INSERT INTO chat_groups (name, owner) VALUES (%s,%s)",
            (name, owner)
        )
        db.commit()
        return "Groupe enregistré "
    except mysql.connector.errors.IntegrityError:
        return "Groupe déjà existant "


server = SimpleXMLRPCServer(("0.0.0.0", 9001), allow_none=True)
server.register_function(store_message)
server.register_function(store_group)

print("Serveur MySQL RPC actif (9001)")
server.serve_forever()
