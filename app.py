# app.py
import streamlit as st
import xmlrpc.client
from cryptography.fernet import Fernet
from datetime import datetime
import json
import time
import streamlit.components.v1 as components
from config import Config

# --- CONFIGURATION PAGE ---
st.set_page_config(
    page_title="RPC Messenger",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -------------------------------
# 1. Configuration & Sécurité
# -------------------------------
key = Config.FERNET_KEY
cipher = Fernet(key)

# -------------------------------
# Load CSS (Dynamic Theme)
# -------------------------------
if "theme" not in st.session_state:
    st.session_state.theme = "Sombre"

# Cette partie sera déplacée dans la sidebar, mais on charge le CSS ici
css_file = "style_light.css" if st.session_state.theme == "Clair" else "style_dark.css"
try:
    with open(css_file) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
except FileNotFoundError:
    # Fallback
    pass

# -------------------------------
# 2. Logic & Helpers
# -------------------------------
def get_history(username):
    try:
        with open(f"historique_{username}.json", "r") as f:
            return json.load(f)
    except:
        return []

def save_history(username, history):
    with open(f"historique_{username}.json", "w") as f:
        json.dump(history, f, indent=2)

def get_contacts(history):
    # Extraire les contacts uniques de l'historique
    contacts = set()
    for h in history:
        if h.get("from") == st.session_state.username:
            contacts.add(h.get("to"))
        else:
            contacts.add(h.get("from"))
    return sorted(list(contacts - {None, ""}))

# -------------------------------
# 3. Sidebar Auth & Config
# -------------------------------
if "auth_ok" not in st.session_state:
    st.session_state.auth_ok = False

if not st.session_state.auth_ok:
    # --- LOGIN SCREEN ---
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.title("💬 RPC Messenger")
        st.markdown("""
        ### Communication Sécurisée & Décentralisée
        
        Bienvenue sur votre nouvelle messagerie.

        
        Connectez-vous via la barre latérale &larr; pour commencer.
        """)
        
        st.info("HPC")

    with col2:
        # Placeholder pour une image ou une animation Lottie si on en avait une
        # Pour l'instant on met un grand icon ou un spacer
        st.markdown("<div style='font-size: 15rem; text-align: center;'>🌐</div>", unsafe_allow_html=True)

    with st.sidebar:
        st.title("🔐 Connexion")
        username_input = st.text_input("Identifiant")
        password_input = st.text_input("Mot de passe", type="password")
        create_account = st.checkbox("Nouveau compte ?")
        
        # Config Avancée (Cachée)
        with st.expander("⚙️ Configuration & Thème"):
             # Theme Selector
            new_theme = st.radio("Thème", ["Sombre", "Clair"], index=0 if st.session_state.theme == "Sombre" else 1, horizontal=True)
            if new_theme != st.session_state.theme:
                st.session_state.theme = new_theme
                st.rerun()
            
            st.divider()

            # Fix pour éviter 0.0.0.0 coté client (Windows ne supporte pas la connexion vers 0.0.0.0)
            default_ip = "127.0.0.1" if Config.RPC_HOST == "0.0.0.0" else Config.RPC_HOST
            server_ip = st.text_input("IP RPC", default_ip)

        if st.button("Se connecter / Inscription", use_container_width=True):
            try:
                # Connexion RPC temporaire pour auth
                mongo_auth = xmlrpc.client.ServerProxy(f"http://{server_ip}:{Config.RPC_PORT}/RPC2")
                
                if create_account:
                    res = mongo_auth.register(username_input, password_input)
                    st.success(res)
                
                if mongo_auth.authenticate(username_input, password_input):
                    st.session_state.auth_ok = True
                    st.session_state.username = username_input
                    st.session_state.server_ip = server_ip # Persist IP
                    st.rerun()
                else:
                    st.error("Identifiants incorrects")
            except Exception as e:
                st.error(f"Erreur connexion: {e}")

else:
    # --- MAIN APP ---
    username = st.session_state.username
    server_ip = st.session_state.get("server_ip", "127.0.0.1")
    mongo = xmlrpc.client.ServerProxy(f"http://{server_ip}:{Config.RPC_PORT}/RPC2")

    # --- SIDEBAR: CONTACTS & MENU ---
    with st.sidebar:
        st.header(f"👤 {username}")
        
        # Theme Toggle (Main App)
        c_theme, c_refresh = st.columns(2)
        with c_theme:
            # Petite astuce pour changer le theme
            if st.button("🌓 Thème"):
                st.session_state.theme = "Clair" if st.session_state.theme == "Sombre" else "Sombre"
                st.rerun()
        with c_refresh:
            auto_refresh = st.toggle("Sync", value=True)
            
        st.markdown("---")
        st.markdown("---")
        
        # 1. Récupération des données
        full_hist = get_history(username)
        contacts = get_contacts(full_hist) # Ce sont les utilisateurs avec qui on a parlé
        
        try:
            my_groups = mongo.get_groups_for_user(username)
        except Exception as e:
            st.error(f"Erreur chargement groupes: {e}")
            my_groups = []

        # 2. Construction de la liste unifiée avec icônes
        # On exclut les groupes de la liste des contacts "simples" si jamais ils y étaient
        direct_contacts = [c for c in contacts if c not in my_groups]
        
        nav_options = ["➕ Nouvelle discussion", "👥 Créer un groupe"]
        
        # Section Groupes
        if my_groups:
            nav_options.append("---")
            nav_options.extend([f"👥 {g}" for g in my_groups])
            
        # Section Directs
        if direct_contacts:
            nav_options.append("---")
            nav_options.extend([f"👤 {c}" for c in direct_contacts])

        st.subheader("Navigation")
        selection = st.radio("Vers", nav_options, label_visibility="collapsed")
        
        # Reset state on change
        if "last_selection" not in st.session_state:
            st.session_state.last_selection = selection
        
        if st.session_state.last_selection != selection:
            st.session_state.last_selection = selection
            # Force rerurn to clear specific UI states if needed
            st.rerun()
        
        st.markdown("---")
        if st.button("Déconnexion", use_container_width=True):
            st.session_state.auth_ok = False
            st.rerun()

    # --- MAIN CONTENT ---
    
    # Nettoyage de la sélection (enlever les emojis)
    if selection == "➕ Nouvelle discussion":
        dest = ""
        mode = "new_chat"
    elif selection == "👥 Créer un groupe":
        dest = ""
        mode = "create_group"
    elif selection == "---":
        dest = ""
        mode = "none"
    else:
        # Enlever l'emoji (2 chars: emoji + space)
        dest = selection[2:] 
        mode = "chat"

    # 1. Affichage selon le mode
    if mode == "new_chat":
        st.header("Nouvelle Conversation")
        dest = st.text_input("Saisir le nom du destinataire")
        is_new = True
        
    elif mode == "create_group":
        st.header("👥 Créer un nouveau groupe")
        with st.container(border=True):
            new_grp_name = st.text_input("Nom du groupe")
            if st.button("Valider la création"):
                if new_grp_name:
                    try:
                        res = mongo.create_group(username, new_grp_name)
                        if "créé" in res:
                            st.toast(f"✅ {res}")
                            st.rerun()
                        else:
                            st.warning(res)
                    except Exception as e:
                        st.error(f"Erreur: {e}")
        is_new = False # On n'affiche pas le chat en dessous
        
    elif mode == "chat":
        # Status Header
        status_text = ""
        if not selection.startswith("👥"): # Seulement pour privés
            try:
                status = mongo.get_user_status(dest)
                status_text = f"<span style='font-size:0.8rem; color:#00adb5;'>{status}</span>"
            except: pass
        
        st.markdown(f"## {selection[:1]} {dest} {status_text}", unsafe_allow_html=True)
        
        # --- INFOS GROUPE 
        if selection.startswith("👥"):
            with st.expander(f"ℹ️ Infos du groupe", expanded=False):
                try:
                    details = mongo.get_group_details(dest)
                    if details:
                        owner = details.get("owner")
                        members = details.get("members", [])
                        
                        st.markdown(f"**{len(members)} participants**")
                        
                        # Liste des membres
                        for m in members:
                            role = "Administrateur" if m == owner else ""
                            is_you = " (Vous)" if m == username else ""
                            st.caption(f"👤 **{m}** {is_you} {role}")
                        
                        st.divider()
                        
                        # Actions
                        if username == owner:
                            c1, c2 = st.columns([2, 1])
                            new_m = c1.text_input("Ajouter un participant", placeholder="Nom d'utilisateur")
                            if c2.button("Ajouter"):
                                st.toast(f"ℹ️ {mongo.add_member(username, dest, new_m)}")
                                st.rerun()
                        else:
                            if st.button("Quitter le groupe", type="primary"):
                                res = mongo.leave_group(username, dest)
                                if "quitté" in res:
                                    st.toast(f"⚠️ {res}")
                                    st.rerun()
                                else:
                                    st.error(res)
                except Exception as e:
                    st.error(f"Erreur info groupe: {e}")
                    
        is_new = False
    else:
        st.info("Sélectionnez une conversation.")
        is_new = False

    # 2. Zone de Chat (Seulement si mode valide et destinataire défini)
    if mode in ["chat", "new_chat"] and dest:
        chat_container = st.container(height=500, border=True)
        
        with chat_container:
            # Filtrer messages
            target_group = None
            if selection.startswith("👥"):
                target_group = selection[2:] # "👥 Devs" -> "Devs"
                
                # Messages du groupe (Reçus pour ce groupe OU Envoyés par moi vers ce groupe)
                conversation = [h for h in full_hist if h.get("group") == target_group]
                
            else:
                # Messages Privés (Pas de groupe ET (de/vers le contact))
                conversation = [h for h in full_hist if 
                                not h.get("group") and 
                                ((h.get("to") == dest and h.get("from") == username) or 
                                 (h.get("from") == dest and h.get("to") == username))]
            
            if not conversation and not is_new:
                st.info("Aucun message pour le moment.")
        
            last_date = None
            for chat in conversation:
                # Date Separator
                ts_iso = chat.get('timestamp', '')
                try:
                    msg_date = ts_iso[:10] # YYYY-MM-DD
                    if msg_date != last_date:
                        st.markdown(f"<div style='text-align:center; font-size:0.75rem; opacity:0.6; margin: 10px 0;'>📅 {msg_date}</div>", unsafe_allow_html=True)
                        last_date = msg_date
                except: pass
    
                is_me = chat.get("from") == username
                css_class = "bubble-user" if is_me else "bubble-other"
                sender_display = "Moi" if is_me else chat.get("from", dest)
                ts = chat.get('timestamp', '')[11:16]
                
                st.markdown(f"""
                <div class="chat-bubble {css_class}">
                    <div style="font-size:0.75rem; font-weight:bold; opacity:0.8">{sender_display}</div>
                    <div style="font-size:1rem;">{chat['content']}</div>
                    <div class="timestamp">{ts}</div>
                </div>
                """, unsafe_allow_html=True)

        # 3. Input Zone (Fixe en bas relative au flux)
        with st.form(f"chat_input_{dest}", clear_on_submit=True):
            col_in, col_btn = st.columns([6, 1])
            msg_txt = col_in.text_input("Message...", label_visibility="collapsed", placeholder="Écrivez votre message...")
            sent = col_btn.form_submit_button("Envoyer", use_container_width=True)
            
            if sent and msg_txt and dest:
                try:
                    # RPC Send
                    if mongo.is_group(dest):
                        res = mongo.send_group_message(username, dest, msg_txt)
                    else:
                        res = mongo.production(username, msg_txt, dest)
                    
                    # Local Save (Sent)
                    now = datetime.utcnow().isoformat()
                    # Si c'est un groupe, on met 'group': dest
                    grp_ctx = dest if mongo.is_group(dest) else None
                    new_msg = {"to": dest, "from": username, "content": msg_txt, "timestamp": now, "type": "sent", "group": grp_ctx}
                    
                    full_hist.append(new_msg)
                    save_history(username, full_hist)
                    
                    st.rerun() # Refresh pour afficher le message
                except Exception as e:
                    st.error(f"Erreur envoi: {e}")

        # 4. Auto-Refresh Logic (Invisible)
        if auto_refresh:
            # Check nouveaux messages sans bloquer l'UI
            try:
                msgs = mongo.get_unread_messages(username)
                if msgs:
                    new_items = []
                    ids_to_ack = []
                    for m in msgs:
                        try:
                            decrypted = cipher.decrypt(m["content"].encode()).decode()
                            new_items.append({
                                "to": username, 
                                "from": m["sender"], 
                                "content": decrypted, 
                                "timestamp": m["timestamp"], 
                                "type": "received",
                                "group": m.get("group")
                            })
                            ids_to_ack.append(m["id"])
                        except: pass
                    
                    if new_items:
                        full_hist.extend(new_items)
                        save_history(username, full_hist)
                        mongo.ack_messages(username, ids_to_ack)
                        st.toast(f"📬 {len(new_items)} nouveaux messages!", icon="🔔")
                        st.rerun()
                
                # Simple polling delay
                time.sleep(2) 
                st.rerun()
            except:
                # En cas d'erreur de connexion (offline), on attend juste
                time.sleep(5)
                st.rerun()


