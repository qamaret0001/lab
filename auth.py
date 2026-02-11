import streamlit as st
from db import get_connection

def login_screen():
    st.title("Laboratory Management System")
    st.subheader("Login")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        conn = get_connection()
        cur = conn.cursor()

        # 1️⃣ Authenticate user
        cur.execute("""
            SELECT user_id, user_name
            FROM users
            WHERE user_name = ? AND passward = ?
        """, (username, password))

        user = cur.fetchone()

        if not user:
            st.error("Invalid username or password")
            return

        # 2️⃣ Get role
        cur.execute("""
            SELECT TOP 1
                ur.role_id,
                r.role_name
            FROM user_rights ur
            JOIN user_role r ON ur.role_id = r.role_id
            WHERE ur.user_id = ?
        """, (user.user_id,))

        role = cur.fetchone()

        # 3️⃣ Get Lab info
        cur.execute("""
            SELECT TOP 1 ID, LabName
            FROM LabInfo
        """)
        lab = cur.fetchone()

        # 4️⃣ Load user rights
        cur.execute("""
            SELECT 
                uf.form_code,
                uf.form_name,
                uf.module,
                ur.[Insert],
                ur.[Update],
                ur.[Delete],
                ur.[Select],
                ur.[Open],
                ur.[Print]
            FROM user_rights ur
            JOIN user_forms uf ON ur.form_id = uf.form_id
            WHERE ur.user_id = ?
        """, (user.user_id,))

        rows = cur.fetchall()

        # helper to convert Yes/No to boolean
        def yn(val):
            return str(val).strip().lower() == "yes"

        st.session_state.rights = {
            r.form_code: {
                "form_name": r.form_name,
                "module": r.module,
                "Insert": yn(r.Insert),
                "Update": yn(r.Update),
                "Delete": yn(r.Delete),
                "Select": yn(r.Select),
                "Open": yn(r.Open),
                "Print": yn(r.Print),
            }
            for r in rows
        }

        # 5️⃣ Store session
        st.session_state.logged_in = True
        st.session_state.user_id = user.user_id
        st.session_state.username = user.user_name
        st.session_state.role_id = role.role_id if role else None
        st.session_state.role_name = role.role_name if role else "User"
        st.session_state.lab_id = lab.ID
        st.session_state.lab_name = lab.LabName

        st.success(f"Welcome {user.user_name}")
        st.rerun()
