# app.py
import streamlit as st
import xmlrpc.client
from cryptography.fernet import Fernet, InvalidToken
from datetime import datetime
import json
import streamlit.components.v1 as components

# -------------------------------
# 1. Clé Fernet
# -------------------------------
key = b'5Gimyni-XZiHb88wmXggl9_6CUguMlDffo0I3DQBrpM='
cipher = Fernet(key)

# -------------------------------
# 2. Connexion RPC
# -------------------------------
server_ip = st.sidebar.text_input("IP du serveur RPC", "127.0.0.1")
mongo = xmlrpc.client.ServerProxy(f"http://{server_ip}:9000/")
mysql = xmlrpc.client.ServerProxy(f"http://{server_ip}:9001/")

# -------------------------------
# Charger le CSS Streamlit pour les autres pages
# -------------------------------
with open("style.css") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# -------------------------------
# 3. Page d'accueil HTML indépendante
# -------------------------------
if "auth_ok" not in st.session_state:
    st.session_state.auth_ok = False

    # Affichage HTML autonome pour l'accueil
    with open("home.html", "r", encoding="utf-8") as f:
        home = f.read()
    components.html(home, height=700, scrolling=False)

# -------------------------------
# 4. Authentification
# -------------------------------
if not st.session_state.auth_ok:
    username_input = st.sidebar.text_input("ID utilisateur")
    password_input = st.sidebar.text_input("Mot de passe", type="password")
    create_account = st.sidebar.checkbox("Créer un compte si inexistant")

    if st.sidebar.button("Se connecter"):
        if create_account:
            res = mongo.register(username_input, password_input)
            try:
                mysql.create_user(username_input, password_input)
            except Exception as e:
                st.warning(f"Impossible de répliquer utilisateur sur MySQL : {e}")
            st.sidebar.success(res)

        if not mongo.authenticate(username_input, password_input):
            st.sidebar.error("Authentification échouée")
        else:
            st.sidebar.success(f"Connecté en tant que {username_input}")
            st.session_state.auth_ok = True
            st.session_state.username = username_input

# -------------------------------
# 5. Interface principale
# -------------------------------
if st.session_state.get("auth_ok", False):
    username = st.session_state.username

    if st.sidebar.button("Déconnexion"):
        st.session_state.auth_ok = False
        st.session_state.username = ""
        st.rerun()

    tabs = st.tabs(["Envoyer message", "Gestion des groupes", "Historique", "Messages reçus"])

    # --- Envoyer message ---
    with tabs[0]:
        st.header("Envoyer un message")
        dest = st.text_input("Destinataire ou groupe")
        msg = st.text_area("Message")

        if st.button("Envoyer"):
            timestamp = datetime.utcnow().isoformat()
            try:
                if mongo.is_group(dest):
                    res_mongo = mongo.send_group_message(username, dest, msg)
                else:
                    res_mongo = mongo.production(username, msg, dest)

                # Chiffrement et réplication MySQL
                try:
                    content_chiffre = cipher.encrypt(msg.encode()).decode()
                    if mongo.is_group(dest):
                        for member in mongo.list_members(dest):
                            if member != username:
                                mysql.store_message(username, member, content_chiffre, timestamp)
                    else:
                        mysql.store_message(username, dest, content_chiffre, timestamp)
                except Exception as e:
                    st.warning(f"Impossible de répliquer sur MySQL : {e}")

                # Historique local
                try:
                    with open(f"historique_{username}.json", "r") as f:
                        historique = json.load(f)
                except:
                    historique = []

                historique.append({"to": dest, "content": msg})
                with open(f"historique_{username}.json", "w") as f:
                    json.dump(historique, f, indent=2)

                st.success(res_mongo)
            except Exception as e:
                st.error(f"Erreur RPC : {e}")

    # --- Gestion des groupes ---
    with tabs[1]:
        st.header("Gestion des groupes")
        grp_name = st.text_input("Nom du groupe")
        add_member_input = st.text_input("Ajouter membre")
        remove_member_input = st.text_input("Supprimer membre")

        col1, col2, col3 = st.columns(3)
        if col1.button("Créer groupe"):
            st.success(mongo.create_group(username, grp_name))
            try:
                mysql.store_group(grp_name, username)
            except Exception as e:
                st.warning(f"Impossible de répliquer groupe sur MySQL : {e}")

        if col2.button("Ajouter membre"):
            st.success(mongo.add_member(username, grp_name, add_member_input))
        if col3.button("Supprimer membre"):
            st.success(mongo.remove_member(username, grp_name, remove_member_input))

        if st.button("Lister membres"):
            members = mongo.list_members(grp_name)
            # Nettoyage : supprimer les vides
            members = [m.strip() for m in members if m and m.strip()]
            st.subheader("👥 Membres du groupe")
            if members:
                st.markdown("\n".join([f"- **{m}**" for m in members]))
            else:
                st.info("Aucun membre dans ce groupe.")

    # --- Historique ---
    with tabs[2]:
        st.header("Historique des messages envoyés")
        try:
            with open(f"historique_{username}.json", "r") as f:
                historique = json.load(f)
            for msg in historique:
                st.write(f"À {msg['to']} : {msg['content']}")
        except:
            st.info("Historique vide")

    # --- Messages reçus ---
    with tabs[3]:
        st.header("Messages reçus")
        if st.button("🔄 Rafraîchir"):
            try:
                messages = mongo.consommateur(username)
                if not messages:
                    st.info("📭 Aucun message")
                else:
                    for m in messages:
                        content_chiffre = m.get("content", "")
                        sender = m.get("sender", "Inconnu")
                        timestamp = m.get("timestamp", "")
                        try:
                            decrypted = cipher.decrypt(content_chiffre.encode()).decode()
                            st.success(f"{timestamp} - De {sender} : {decrypted}")
                        except InvalidToken:
                            st.warning(f"{timestamp} - De {sender} : message illisible")
            except Exception as e:
                st.error(f"Erreur RPC : {e}")
