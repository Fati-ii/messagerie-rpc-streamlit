import streamlit as st
import xmlrpc.client
from cryptography.fernet import Fernet, InvalidToken
from datetime import datetime
import json
import streamlit.components.v1 as components

# -------------------------------
# Configuration
# -------------------------------
FERNET_KEY = b'5Gimyni-XZiHb88wmXggl9_6CUguMlDffo0I3DQBrpM='
cipher = Fernet(FERNET_KEY)

# -------------------------------
# Connexion RPC
# -------------------------------
server_ip = st.sidebar.text_input("IP du serveur RPC", "127.0.0.1")
mongo = xmlrpc.client.ServerProxy(f"http://{server_ip}:9000/", allow_none=True)
mysql = xmlrpc.client.ServerProxy(f"http://{server_ip}:9001/", allow_none=True)

# -------------------------------
# CSS / Home
# -------------------------------


if "auth_ok" not in st.session_state:
    st.session_state.auth_ok = False
    with open("home.html", encoding="utf-8") as f:
        components.html(f.read(), height=700)

with open("style.css") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# -------------------------------
# Authentification
# -------------------------------
if not st.session_state.auth_ok:
    username = st.sidebar.text_input("ID utilisateur")
    password = st.sidebar.text_input("Mot de passe", type="password")
    create_account = st.sidebar.checkbox("Créer un compte si inexistant")

    if st.sidebar.button("Se connecter"):
        if not username or not password:
            st.sidebar.error("Champs obligatoires")
            st.stop()

        if create_account:
            st.sidebar.info(mongo.register(username, password))

        if mongo.authenticate(username, password):
            st.session_state.auth_ok = True
            st.session_state.username = username
            st.sidebar.success("Connexion réussie")
            st.rerun()
        else:
            st.sidebar.error("Authentification échouée")

# -------------------------------
# Interface principale
# -------------------------------
if st.session_state.auth_ok:
    username = st.session_state.username

    if st.sidebar.button("Déconnexion"):
        st.session_state.clear()
        st.rerun()

    tabs = st.tabs([
        "Envoyer message",
        "Gestion des groupes",
        "Messages reçus",
        "Historique local"
    ])

    # --- Envoi message ---
    with tabs[0]:
        dest = st.text_input("Destinataire ou groupe")
        msg = st.text_area("Message")

        if st.button("Envoyer"):
            try:
                if mongo.is_group(dest):
                    res = mongo.send_group_message(username, dest, msg)
                else:
                    res = mongo.production(username, msg, dest)

                mysql.store_message(username, dest, msg, datetime.utcnow().isoformat())

                fname = f"historique_{username}.json"
                try:
                    hist = json.load(open(fname))
                except:
                    hist = []

                hist.append({"to": dest, "content": msg})
                json.dump(hist, open(fname, "w"), indent=2)

                st.success(res)
            except Exception as e:
                st.error(e)

    # --- Groupes ---
    with tabs[1]:
        grp = st.text_input("Nom du groupe")
        member = st.text_input("Utilisateur")

        c1, c2, c3 = st.columns(3)

        # if c1.button("Créer"):
        #     st.success(mongo.create_group(username, grp))
        #     mysql.store_group(grp, username)
        if c1.button("Créer"):
            es_mongo = mongo.create_group(username, grp)
            res_mysql = mysql.store_group(grp, username)

            st.success(es_mongo)
            st.info(res_mysql)

        if c2.button("Ajouter"):
            st.success(mongo.add_member(username, grp, member))

        if c3.button("Supprimer"):
            st.success(mongo.remove_member(username, grp, member))

        if st.button("Lister membres"):

    # Récupération depuis MongoDB
            members = mongo.list_members(grp)

            st.subheader("👥 Membres du groupe")

    # Nettoyage : supprimer les chaînes vides ou espaces
            members = [m.strip() for m in members if m and m.strip()]

            if members:
        # Affichage en liste avec puces
                st.markdown("\n".join([f"- **{m}**" for m in members]))
            else:
                st.info("Aucun membre dans ce groupe.")



    # --- Messages reçus ---
    with tabs[2]:
        if st.button("Rafraîchir"):
            msgs = mongo.consommateur(username)
            if not msgs:
                st.info("Aucun message")
            for m in msgs:
                try:
                    text = cipher.decrypt(m["content"].encode()).decode()
                    st.success(f"{m['timestamp']} | {m['sender']} : {text}")
                except InvalidToken:
                    st.warning("Message illisible")

    # --- Historique ---
    with tabs[3]:
        try:
            hist = json.load(open(f"historique_{username}.json"))
            for h in hist:
                st.write(f"À {h['to']} : {h['content']}")
        except:
            st.info("Historique vide")
