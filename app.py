import streamlit as st
import pyodbc
import pandas as pd
from datetime import datetime, timedelta
import base64
from io import BytesIO
import reports  # 🔑 CRITICAL: Import report module for test reports

# -----------------------------
# DATABASE CONNECTION (SQL SERVER 2012 COMPATIBLE)
# -----------------------------
def get_connection():
    return pyodbc.connect(
        "DRIVER={ODBC Driver 17 for SQL Server};"
        "SERVER=91.239.146.172;"
        "DATABASE=Labnew;"
        "UID=labuser;"
        "PWD=janan123%%"
    )

# -----------------------------
# SESSION INITIALIZATION (ALL REQUIRED STATES)
# -----------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user" not in st.session_state:
    st.session_state.user = None
if "rights" not in st.session_state:
    st.session_state.rights = {}
if "lab_info" not in st.session_state:
    st.session_state.lab_info = None
if "current_page" not in st.session_state:
    st.session_state.current_page = "dashboard"
if "selected_tests" not in st.session_state:
    st.session_state.selected_tests = None
if "subtest_selections" not in st.session_state:
    st.session_state.subtest_selections = {}
if "selected_patient" not in st.session_state:
    st.session_state.selected_patient = None
if "action_mode" not in st.session_state:
    st.session_state.action_mode = None
if "result_inputs" not in st.session_state:
    st.session_state.result_inputs = {}
if "last_saved" not in st.session_state:
    st.session_state.last_saved = None
if "selected_report" not in st.session_state:
    st.session_state.selected_report = None
if "report_params" not in st.session_state:
    st.session_state.report_params = {}

# -----------------------------
# LOGIN SCREEN
# -----------------------------
def login_screen():
    st.title("🔬 Laboratory Management System")
    st.subheader("Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login", type="primary"):
        try:
            con = get_connection()
            cur = con.cursor()
            cur.execute("""
                SELECT user_id, user_name
                FROM users
                WHERE user_name = ? AND passward = ?
            """, (username, password))
            row = cur.fetchone()
            if row:
                st.session_state.logged_in = True
                st.session_state.user = {
                    "user_id": row[0],
                    "user_name": row[1]
                }
                # LOAD USER RIGHTS
                cur.execute("""
                    SELECT
                        uf.form_code,
                        uf.form_name,
                        uf.Module,
                        ur.[Insert],
                        ur.[Update],
                        ur.[Delete],
                        ur.[Select],
                        ur.[Open],
                        ur.[Print]
                    FROM user_rights ur
                    JOIN user_forms uf ON ur.form_id = uf.form_id
                    WHERE ur.user_id = ?
                """, (row[0],))
                rights = {}
                for r in cur.fetchall():
                    rights[r.form_code] = {
                        "form_name": r.form_name,
                        "module": r.Module,
                        "Insert": str(r.Insert).strip().lower() == "yes",
                        "Update": str(r.Update).strip().lower() == "yes",
                        "Delete": str(r.Delete).strip().lower() == "yes",
                        "Select": str(r.Select).strip().lower() == "yes",
                        "Open": str(r.Open).strip().lower() == "yes",
                        "Print": str(r.Print).strip().lower() == "yes",
                    }
                st.session_state.rights = rights
                
                # LOAD LAB INFO
                cur.execute("SELECT TOP 1 ID, LabName, Address, PhoneNo FROM LabInfo")
                lab_row = cur.fetchone()
                if lab_row:
                    st.session_state.lab_info = {
                        "id": lab_row[0],
                        "name": lab_row[1],
                        "address": lab_row[2],
                        "phone": lab_row[3]
                    }
                st.success(f"Welcome {row[1]}")
                st.rerun()
            else:
                st.error("Invalid username or password")
        except Exception as e:
            st.error(f"Database error: {str(e)}")

# -----------------------------
# SIDEBAR MENU (WITH REPORTS INTEGRATION)
# -----------------------------
def sidebar_menu():
    st.sidebar.title("📋 Main Menu")
    if st.session_state.user:
        st.sidebar.write(f"👤 {st.session_state.user['user_name']}")
    if st.session_state.lab_info:
        st.sidebar.write(f"🏢 {st.session_state.lab_info['name']}")
    st.sidebar.markdown("---")
    
    # DASHBOARD BUTTON
    if st.sidebar.button("🏠 Dashboard", use_container_width=True):
        st.session_state.current_page = "dashboard"
        st.session_state.selected_report = None
        st.session_state.report_params = {}
        st.rerun()
    
    # 🔑 REPORTS MENU BUTTON (NEW - BEFORE PATIENT MANAGEMENT)
    if st.sidebar.button("📑 Reports", use_container_width=True):
        st.session_state.current_page = "reports_menu"
        st.session_state.selected_report = None
        st.session_state.report_params = {}
        st.rerun()
    
    # NEW PATIENT BUTTON (if permission exists)
    if st.session_state.rights.get("FRM-005", {}).get("Open", False):
        if st.sidebar.button("➕ New Patient", use_container_width=True):
            st.session_state.current_page = "test_selection"
            st.session_state.selected_tests = None
            st.session_state.subtest_selections = {}
            st.session_state.selected_patient = None
            st.session_state.report_params = {}
            st.rerun()
    
    st.sidebar.markdown("---")
    
    # LOGOUT BUTTON
    if st.sidebar.button("🚪 Logout", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.user = None
        st.session_state.rights = {}
        st.session_state.lab_info = None
        st.session_state.current_page = "dashboard"
        st.session_state.selected_tests = None
        st.session_state.subtest_selections = {}
        st.session_state.selected_patient = None
        st.session_state.selected_report = None
        st.session_state.report_params = {}
        st.rerun()

# -----------------------------
# GET PATIENT TESTS (FOR RESULTS ENTRY)
# -----------------------------
def get_patient_tests(patient_id):
    """Get ALL tests for patient - returns numeric Test_ID and display number"""
    con = get_connection()
    cur = con.cursor()
    
    cur.execute("""
        SELECT 
            pt.PatientID,
            pt.Test_ID,
            pt.PaymentID,
            t.Test_Name,
            ti.Test_Display_No,
            ti.Test_Display_Name,
            ti.SRate,
            t.General_Test_Id
        FROM patient_test pt
        JOIN test t ON pt.Test_ID = t.Test_Id
        JOIN test_identity ti ON t.Id = ti.Id
        WHERE pt.PatientID = ?
        ORDER BY CAST(ti.Test_Display_No AS VARCHAR(50))
    """, (str(patient_id),))
    
    tests = []
    for row in cur.fetchall():
        tests.append({
            "patient_id": row[0],
            "test_id": int(row[1]),
            "payment_id": row[2],
            "test_name": row[3],
            "display_no": str(row[4]),
            "display_name": row[5],
            "rate": float(row[6]) if row[6] else 0.0,
            "general_test_id": row[7]
        })
    
    con.close()
    return tests

# -----------------------------
# GET TEST SUB-TESTS
# -----------------------------
def get_test_subtests(test_id):
    """Get all sub-tests for a given test ID"""
    con = get_connection()
    cur = con.cursor()
    
    cur.execute("""
        SELECT 
            t.Test_Id,
            t.Test_Name,
            ti.Test_Display_No,
            ti.SRate
        FROM test t
        JOIN test_identity ti ON t.Id = ti.Id
        WHERE t.General_Test_Id = ?
        ORDER BY CAST(ti.Test_Display_No AS VARCHAR(50))
    """, (test_id,))
    
    subtests = []
    for row in cur.fetchall():
        subtests.append({
            "test_id": row[0],
            "test_name": row[1],
            "display_no": row[2],
            "rate": float(row[3]) if row[3] else 0.0
        })
    
    con.close()
    return subtests

# -----------------------------
# GET TEST RESULTS
# -----------------------------
def get_test_results(patient_id, test_id):
    """Get results using NUMERIC Test_ID (not display number)"""
    con = get_connection()
    cur = con.cursor()
    
    cur.execute("""
        SELECT 
            Result_id,
            Patient_No,
            Test_No,
            Test_Values,
            Remarks
        FROM patient_test_results
        WHERE Patient_No = ? AND Test_No = ?
    """, (str(patient_id), int(test_id)))
    
    results = []
    for row in cur.fetchall():
        results.append({
            "result_id": row[0],
            "patient_no": row[1],
            "test_no": row[2],
            "test_values": row[3] if row[3] else "",
            "remarks": row[4] if row[4] else ""
        })
    
    con.close()
    return results

# -----------------------------
# SAVE TEST RESULT
# -----------------------------
def save_test_result(patient_id, test_id, test_values, remarks):
    """Save to EXACT schema with manual Result_id generation and numeric Test_No"""
    try:
        con = get_connection()
        cur = con.cursor()
        patient_id_str = str(patient_id)
        
        cur.execute("""
            SELECT Result_id FROM patient_test_results
            WHERE Patient_No = ? AND Test_No = ?
        """, (patient_id_str, int(test_id)))
        
        existing = cur.fetchone()
        
        if existing:
            cur.execute("""
                UPDATE patient_test_results
                SET Test_Values = ?, Remarks = ?
                WHERE Result_id = ?
            """, (test_values, remarks, existing[0]))
            con.commit()
            con.close()
            return True, "updated"
        else:
            cur.execute("SELECT ISNULL(MAX(Result_id), 0) + 1 FROM patient_test_results")
            next_result_id = cur.fetchone()[0]
            
            cur.execute("""
                INSERT INTO patient_test_results (
                    Result_id, Patient_No, Test_No, Test_Values, Remarks
                ) VALUES (?, ?, ?, ?, ?)
            """, (next_result_id, patient_id_str, int(test_id), test_values, remarks))
            con.commit()
            con.close()
            return True, "inserted"
        
    except Exception as e:
        return False, str(e)

# -----------------------------
# DASHBOARD GRID (WITH REPORT BUTTON)
# -----------------------------
def dashboard():
    lab_name = st.session_state.lab_info['name'] if st.session_state.lab_info else "Dashboard"
    st.title(f"📊 {lab_name} – Today Patients")
    st.caption(f"User: {st.session_state.user['user_name']} | Role: {st.session_state.user.get('role_name', 'User')}")
    st.divider()
    
    try:
        con = get_connection()
        df = pd.read_sql("""
            SELECT
                p.Patient_Id,
                p.LabNo,
                p.Patient_Name AS Patient,
                p.Age,
                p.Sex,
                p.Mobile_No AS Mobile,
                p.Refered_By AS DoctorID,
                d.DoctorName AS Doctor,
                STUFF((
                    SELECT ', ' + t2.Test_Name
                    FROM patient_test pt2
                    JOIN test t2 ON pt2.Test_ID = t2.Test_Id
                    WHERE pt2.PatientID = CAST(p.Patient_Id AS VARCHAR(50))
                    FOR XML PATH(''), TYPE
                ).value('.', 'NVARCHAR(MAX)'), 1, 2, '') AS Tests,
                (ISNULL(pp.TotalAmount, 0) - ISNULL(pp.AmountPaid, 0)) AS Balance,
                CASE
                    WHEN EXISTS (
                        SELECT 1
                        FROM patient_test_results r
                        WHERE r.Patient_No = CAST(p.Patient_Id AS VARCHAR(50))
                    )
                    THEN 'Ready'
                    ELSE 'Awaiting Result'
                END AS Status,
                p.Visit_Date
            FROM patient p
            LEFT JOIN doctor d ON p.Refered_By = d.DoctorID
            LEFT JOIN patientpayment pp ON CAST(p.Patient_Id AS VARCHAR(50)) = pp.PatientID
            WHERE CAST(p.Visit_Date AS DATE) = CAST(GETDATE() AS DATE)
            ORDER BY p.Patient_Id DESC
        """, con)
        
        if df.empty:
            st.info("🕗 No patients found for today. Add a new patient to get started!")
        else:
            # Summary metrics
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total Patients", len(df))
            col2.metric("Pending Results", len(df[df['Status'] == 'Awaiting Result']))
            col3.metric("Ready Reports", len(df[df['Status'] == 'Ready']))
            col4.metric("Total Balance", f"Rs. {df['Balance'].sum():,.2f}")
            st.divider()
            
            # Patient grid with action buttons
            for idx, row in df.iterrows():
                with st.expander(f"📋 Lab No: {row['LabNo']} - {row['Patient']} (Age: {row['Age']}, {row['Sex']})", expanded=False):
                    col1, col2, col3, col4 = st.columns([2, 2, 2, 2])
                    with col1:
                        st.write(f"**Patient:** {row['Patient']}")
                        st.write(f"**Age/Sex:** {row['Age']} / {row['Sex']}")
                        st.write(f"**Mobile:** {row['Mobile']}")
                    with col2:
                        st.write(f"**Doctor:** {row['Doctor']}")
                        st.write(f"**Tests:** {row['Tests']}")
                        st.write(f"**Visit:** {row['Visit_Date'].strftime('%d-%b-%Y %I:%M %p')}")
                    with col3:
                        status_color = "🟢" if row['Status'] == 'Ready' else "🟡"
                        st.write(f"**Status:** {status_color} {row['Status']}")
                        balance_color = "🔴" if row['Balance'] > 0 else "🟢"
                        st.write(f"**Balance:** {balance_color} Rs. {row['Balance']:.2f}")
                    with col4:
                        if st.button("📝 Results", key=f"results_{row['Patient_Id']}", use_container_width=True):
                            st.session_state.selected_patient = {
                                "patient_id": row['Patient_Id'],
                                "lab_no": row['LabNo'],
                                "patient_name": row['Patient'],
                                "age": row['Age'],
                                "sex": row['Sex'],
                                "mobile": row['Mobile'],
                                "doctor": row['Doctor'],
                                "tests": row['Tests'],
                                "balance": row['Balance'],
                                "status": row['Status']
                            }
                            st.session_state.current_page = "test_results"
                            st.rerun()
                        
                        # 🔑 REPORT BUTTON FOR READY PATIENTS
                        if row['Status'] == 'Ready':
                            if st.button("📄 Report", key=f"report_{row['Patient_Id']}", use_container_width=True, type="primary"):
                                st.session_state.selected_patient = {
                                    "patient_id": row['Patient_Id'],
                                    "lab_no": row['LabNo'],
                                    "patient_name": row['Patient'],
                                    "age": row['Age'],
                                    "sex": row['Sex'],
                                    "mobile": row['Mobile'],
                                    "doctor": row['Doctor'],
                                    "city": row.get('City', 'N/A'),
                                    "visit_date": row['Visit_Date']
                                }
                                st.session_state.current_page = "test_report"
                                st.rerun()
                        
                        if st.button("✏️ Update", key=f"update_{row['Patient_Id']}", use_container_width=True):
                            st.session_state.selected_patient = {
                                "patient_id": row['Patient_Id'],
                                "lab_no": row['LabNo'],
                                "patient_name": row['Patient'],
                                "age": row['Age'],
                                "sex": row['Sex'],
                                "mobile": row['Mobile'],
                                "doctor": row['Doctor']
                            }
                            st.session_state.action_mode = "update_patient"
                            st.session_state.current_page = "patient_update"
                            st.rerun()
                        
                        if st.button("🗑️ Delete", key=f"delete_{row['Patient_Id']}", use_container_width=True):
                            st.session_state.selected_patient = {
                                "patient_id": row['Patient_Id'],
                                "lab_no": row['LabNo'],
                                "patient_name": row['Patient']
                            }
                            st.session_state.action_mode = "delete_patient"
                            st.session_state.current_page = "patient_delete"
                            st.rerun()
    except Exception as e:
        st.error(f"Error loading dashboard: {str(e)}")
        st.exception(e)

# -----------------------------
# TEST SELECTION SCREEN (FULLY IMPLEMENTED)
# -----------------------------
def test_selection():
    st.title("🧪 Step 1: Select Tests")
    
    col1, col2 = st.columns(2)
    with col1:
        search_name = st.text_input("Search by Test Name")
    with col2:
        search_no = st.text_input("Search by Display No")
    
    try:
        con = get_connection()
        query = """
            SELECT
                ti.Id AS test_identity_id,
                ti.Test_Display_No,
                ti.Test_Display_Name,
                t.Test_Id,
                t.Test_Name,
                CAST(ti.SRate AS FLOAT) AS Rate
            FROM test_identity ti
            JOIN test t ON ti.Id = t.Id
            WHERE ti.Test_Display_No IS NOT NULL 
              AND LTRIM(RTRIM(ti.Test_Display_No)) <> ''
        """
        params = []
        if search_name:
            query += " AND t.Test_Name LIKE ?"
            params.append(f"%{search_name}%")
        if search_no:
            query += " AND ti.Test_Display_No LIKE ?"
            params.append(f"%{search_no}%")
        query += " ORDER BY CAST(ti.Test_Display_No AS VARCHAR(50))"
        
        df = pd.read_sql(query, con, params=params)
        
        if df.empty:
            st.warning("No tests found matching your search")
            return
        
        df["Display"] = df["Test_Display_No"].astype(str) + " - " + df["Test_Display_Name"] + " (Rs. " + df["Rate"].astype(str) + ")"
        
        preselected = []
        if st.session_state.selected_tests:
            for test in st.session_state.selected_tests:
                label = f"{test['Test_Display_No']} - {test['Test_Display_Name']} (Rs. {test['Rate']})"
                if label in df["Display"].values:
                    preselected.append(label)
        
        selected = st.multiselect(
            "Select Tests (you can select multiple)",
            options=df["Display"].tolist(),
            default=preselected
        )
        
        if selected:
            total = df[df["Display"].isin(selected)]["Rate"].sum()
            st.success(f"✅ {len(selected)} test(s) selected | Total: Rs. {total:.2f}")
        
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("➡️ Next: Enter Patient Details", type="primary"):
                if not selected:
                    st.warning("⚠️ Please select at least one test")
                    return
                
                selected_df = df[df["Display"].isin(selected)]
                st.session_state.selected_tests = selected_df[[
                    "test_identity_id", "Test_Display_No", "Test_Display_Name", 
                    "Test_Id", "Test_Name", "Rate"
                ]].to_dict("records")
                
                st.session_state.subtest_selections = {}
                st.session_state.current_page = "patient_entry"
                st.rerun()
        
        with col_btn2:
            if st.button("🏠 Back to Dashboard"):
                st.session_state.current_page = "dashboard"
                st.session_state.selected_tests = None
                st.session_state.subtest_selections = {}
                st.rerun()
            
    except Exception as e:
        st.error(f"Error loading tests: {str(e)}")
        st.exception(e)

# -----------------------------
# PATIENT ENTRY FORM (FULLY IMPLEMENTED)
# -----------------------------
def patient_entry_form():
    if not st.session_state.selected_tests:
        st.session_state.current_page = "test_selection"
        st.rerun()
        return
    
    st.title("📋 Step 2: Patient Entry")
    
    # FETCH SUB-TESTS FOR EACH MAIN TEST
    if not st.session_state.subtest_selections:
        try:
            con = get_connection()
            cur = con.cursor()
            for test in st.session_state.selected_tests:
                main_test_id = test["Test_Id"]
                cur.execute("""
                    SELECT t.Test_Id, t.Test_Name, CAST(ti.SRate AS FLOAT) AS Rate
                    FROM test t
                    JOIN test_identity ti ON t.Id = ti.Id
                    WHERE t.General_Test_Id = ?
                """, (main_test_id,))
                subtests = cur.fetchall()
                st.session_state.subtest_selections[main_test_id] = [
                    {
                        "Test_Id": row[0],
                        "Test_Name": row[1],
                        "Rate": float(row[2]) if row[2] else 0.0,
                        "selected": True
                    }
                    for row in subtests
                ]
            con.close()
        except Exception as e:
            st.error(f"Error loading sub-tests: {str(e)}")
    
    st.subheader("Selected Tests & Sub-Tests")
    tests_to_remove = []
    
    for idx, test in enumerate(st.session_state.selected_tests):
        main_test_id = test["Test_Id"]
        col1, col2, col3 = st.columns([4, 1, 1])
        
        with col1:
            st.markdown(f"**🔹 {test['Test_Display_No']} - {test['Test_Name']}** (Rs. {test['Rate']:.2f})")
            
            if main_test_id in st.session_state.subtest_selections and st.session_state.subtest_selections[main_test_id]:
                for sub_idx, sub_test in enumerate(st.session_state.subtest_selections[main_test_id]):
                    is_checked = st.checkbox(
                        f"  ▫️ {sub_test['Test_Name']} (Rs. {sub_test['Rate']:.2f})",
                        value=sub_test.get("selected", True),
                        key=f"sub_{main_test_id}_{sub_idx}",
                        label_visibility="visible"
                    )
                    st.session_state.subtest_selections[main_test_id][sub_idx]["selected"] = is_checked
            elif main_test_id in st.session_state.subtest_selections:
                st.caption("  ▫️ No sub-tests available")
        
        with col2:
            st.write("")
        
        with col3:
            if st.button("🗑️ Remove", key=f"remove_{main_test_id}_{idx}"):
                tests_to_remove.append(idx)
    
    if tests_to_remove:
        for idx in sorted(tests_to_remove, reverse=True):
            if idx < len(st.session_state.selected_tests):
                removed_test = st.session_state.selected_tests.pop(idx)
                main_id = removed_test["Test_Id"]
                if main_id in st.session_state.subtest_selections:
                    del st.session_state.subtest_selections[main_id]
        st.success(f"Removed {len(tests_to_remove)} test(s)")
        st.rerun()
    
    total_amount = 0
    for test in st.session_state.selected_tests:
        total_amount += test["Rate"]
        if test["Test_Id"] in st.session_state.subtest_selections:
            for sub in st.session_state.subtest_selections[test["Test_Id"]]:
                if sub["selected"]:
                    total_amount += sub["Rate"]
    
    if st.session_state.selected_tests:
        st.info(f"**{len(st.session_state.selected_tests)} main test(s) selected** | **Total Amount: Rs. {total_amount:.2f}**")
    else:
        st.warning("⚠️ No tests selected. Please add tests.")
        if st.button("➕ Select Tests"):
            st.session_state.current_page = "test_selection"
            st.rerun()
        return
    
    if st.button("✏️ Edit Selected Tests", type="secondary"):
        st.session_state.current_page = "test_selection"
        st.rerun()
    
    st.markdown("---")
    
    with st.form("patient_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            try:
                con = get_connection()
                cur = con.cursor()
                cur.execute("""
                    SELECT ISNULL(MAX(CASE 
                        WHEN ISNUMERIC(LabNo) = 1 THEN CAST(LabNo AS INT) 
                        ELSE 0 
                    END), 0) + 1 
                    FROM patient 
                    WHERE CAST(Visit_Date AS DATE) = CAST(GETDATE() AS DATE)
                """)
                next_labno = cur.fetchone()[0]
            except:
                next_labno = 1
            
            st.text_input("Lab No", value=str(next_labno), disabled=True)
            patient_name = st.text_input("Patient Name *", max_chars=100)
            age = st.number_input("Age", min_value=0, max_value=150, value=30)
            sex = st.selectbox("Sex", ["Male", "Female", "Other"])
            mobile = st.text_input("Mobile No", max_chars=15)
        
        with col2:
            try:
                doctors = pd.read_sql("SELECT DoctorID, DoctorName FROM doctor ORDER BY DoctorName", con)
                doctor_opts = [""] + doctors["DoctorName"].tolist()
                doctor = st.selectbox("Referred By Doctor", doctor_opts)
                doctor_id = doctors.loc[doctors["DoctorName"] == doctor, "DoctorID"].values[0] if doctor else None
            except Exception as e:
                st.error(f"Error loading doctors: {str(e)}")
                doctor = st.text_input("Referred By Doctor")
                doctor_id = None
            
            city = st.text_input("City")
            address = st.text_area("Address", height=80)
            sample_source = st.text_input("Sample Source")
        
        st.subheader("Payment Details")
        col3, col4, col5 = st.columns(3)
        with col3:
            discount = st.number_input("Discount (Rs.)", min_value=0.0, value=0.0, step=10.0)
        with col4:
            net_amount = total_amount - discount
            paid = st.number_input(
                "Amount Paid (Rs.)", 
                min_value=0.0, 
                value=float(net_amount),
                step=10.0,
                help="Automatically set to Total - Discount. Adjust if partial payment."
            )
        with col5:
            balance = net_amount - paid
            if balance > 0:
                st.metric("Balance Due", f"Rs. {balance:.2f}", delta="⚠️", delta_color="inverse")
            else:
                st.metric("Balance Due", f"Rs. {balance:.2f}", delta="✅ Paid", delta_color="normal")
        
        visit_date = datetime.now()
        return_time = st.text_input("Return Time (e.g., 5:00 PM)")
        
        submitted = st.form_submit_button("💾 Save Patient & Generate Receipt", type="primary")
        
        if submitted:
            if not patient_name.strip():
                st.error("⚠️ Patient Name is required")
                return
            
            try:
                con = get_connection()
                cur = con.cursor()
                cur.execute("BEGIN TRANSACTION")
                
                cur.execute("SELECT ISNULL(MAX(Patient_Id), 0) + 1 FROM patient")
                next_patient_id = cur.fetchone()[0]
                patient_no = f"P{next_patient_id}"
                
                cur.execute("SELECT ISNULL(MAX(PaymentID), 0) + 1 FROM patientpayment")
                next_payment_id = cur.fetchone()[0]
                
                cur.execute("""
                    INSERT INTO patient (
                        Patient_Id, PatientNo, LabNo, Patient_Name, NIC, Mobile_No, 
                        ReportedDate, Visit_Date, Age, Sex, Refered_By, 
                        City, Parent_Age_Name, SampleSource, WrongEntry, 
                        ReturnTime, Address
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    next_patient_id, patient_no, next_labno, patient_name, "", mobile,
                    visit_date, visit_date, age, sex, doctor_id,
                    city, "", sample_source, 0,
                    return_time, address
                ))
                con.commit()
                
                cur.execute("""
                    INSERT INTO patientpayment (
                        PaymentID, PatientID, TotalAmount, Discount, AmountPaid, 
                        UserID, Description, TDiscount
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    next_payment_id, str(next_patient_id), total_amount, discount, paid,
                    st.session_state.user["user_id"], "New Patient Entry", discount
                ))
                con.commit()
                
                all_tests_to_insert = []
                
                for test in st.session_state.selected_tests:
                    all_tests_to_insert.append({
                        "Test_ID": test["Test_Id"],
                        "Rate": test["Rate"]
                    })
                
                for main_test_id, subtests in st.session_state.subtest_selections.items():
                    for sub in subtests:
                        if sub["selected"]:
                            all_tests_to_insert.append({
                                "Test_ID": sub["Test_Id"],
                                "Rate": sub["Rate"]
                            })
                
                for test_item in all_tests_to_insert:
                    cur.execute("""
                        INSERT INTO patient_test (PatientID, Test_ID, PaymentID, TestRepeat)
                        VALUES (?, ?, ?, 0)
                    """, (str(next_patient_id), test_item["Test_ID"], next_payment_id))
                
                con.commit()
                
                cur.execute("SELECT ISNULL(MAX(TRN_ID), 0) FROM journal")
                base_trn_id = cur.fetchone()[0]
                
                journal_entries = [
                    (base_trn_id + 1, visit_date, 1, "Transaction Generated For Patient Entry", "Debit", paid, next_patient_id, None),
                    (base_trn_id + 2, visit_date, 3, "Transaction Generated For Patient Entry", "Credit", paid, next_patient_id, None),
                    (base_trn_id + 3, visit_date, 1, "Transaction Generated For Patient Entry", "Credit", paid, next_patient_id, None),
                    (base_trn_id + 4, visit_date, 2, "Transaction Generated For Patient Entry", "Debit", paid, next_patient_id, None)
                ]
                
                for entry in journal_entries:
                    cur.execute("""
                        INSERT INTO journal (
                            TRN_ID, TRN_date, S_ID, Description, TRN_type, 
                            TRN_amount, PatientID, DoctorFeeID
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, entry)
                
                con.commit()
                
                receipt_tests = []
                for test in st.session_state.selected_tests:
                    receipt_tests.append({
                        "display_no": test['Test_Display_No'],
                        "name": test['Test_Name'],
                        "rate": test['Rate'],
                        "is_sub": False,
                        "main_test_id": test['Test_Id']
                    })
                    if test['Test_Id'] in st.session_state.subtest_selections:
                        for sub in st.session_state.subtest_selections[test['Test_Id']]:
                            if sub['selected']:
                                receipt_tests.append({
                                    "display_no": "  ▫️ Sub",
                                    "name": sub['Test_Name'],
                                    "rate": sub['Rate'],
                                    "is_sub": True,
                                    "main_test_id": test['Test_Id']
                                })
                
                st.session_state.last_saved = {
                    "labno": next_labno,
                    "patient_no": patient_no,
                    "name": patient_name,
                    "age": age,
                    "sex": sex,
                    "mobile": mobile,
                    "doctor_name": doctor if doctor else "N/A",
                    "city": city,
                    "address": address,
                    "sample_source": sample_source,
                    "tests": receipt_tests,
                    "total": total_amount,
                    "discount": discount,
                    "paid": paid,
                    "balance": balance,
                    "date": visit_date.strftime('%d-%b-%Y %I:%M %p'),
                    "return_time": return_time,
                    "lab_info": st.session_state.lab_info.copy() if st.session_state.lab_info else {
                        "name": "Frontier Laboratory",
                        "address": "Opp:Ayub Medical Complex Abbottabad",
                        "phone": "0300-1234567"
                    }
                }
                
                st.success(f"✅ Patient saved successfully! Lab No: {next_labno} | Patient No: {patient_no}")
                st.session_state.current_page = "receipt"
                st.session_state.selected_tests = None
                st.session_state.subtest_selections = {}
                st.rerun()
                
            except Exception as e:
                cur.execute("ROLLBACK TRANSACTION")
                st.error(f"Database error: {str(e)}")
                st.exception(e)

# -----------------------------
# TEST RESULTS ENTRY (FULLY IMPLEMENTED)
# -----------------------------
def test_results_entry():
    if not st.session_state.selected_patient:
        st.session_state.current_page = "dashboard"
        st.rerun()
        return
    
    patient = st.session_state.selected_patient
    st.title(f"📝 Test Results Entry - Lab No: {patient['lab_no']} | {patient['patient_name']}")
    
    tests = get_patient_tests(patient['patient_id'])
    
    if not tests:
        st.warning("⚠️ No tests found for this patient")
        if st.button("🏠 Back to Dashboard"):
            st.session_state.current_page = "dashboard"
            st.session_state.selected_patient = None
            st.rerun()
        return
    
    all_tests = tests
    
    st.subheader(f"Test Results ({len(all_tests)} tests)")
    
    patient_key = f"results_{patient['patient_id']}"
    if patient_key not in st.session_state.result_inputs:
        st.session_state.result_inputs[patient_key] = {}
        for test in all_tests:
            existing = get_test_results(patient['patient_id'], test['test_id'])
            st.session_state.result_inputs[patient_key][test['test_id']] = {
                "test_values": existing[0]['test_values'] if existing else "",
                "remarks": existing[0]['remarks'] if existing else ""
            }
    
    with st.form(key=f"all_results_form_{patient['patient_id']}"):
        col_headers = st.columns([1, 3, 2, 3])
        with col_headers[0]:
            st.markdown("**No.**")
        with col_headers[1]:
            st.markdown("**Test Name**")
        with col_headers[2]:
            st.markdown("**Test Values**")
        with col_headers[3]:
            st.markdown("**Remarks (Normal Range/Notes)**")
        
        st.markdown("---")
        
        for idx, test in enumerate(all_tests):
            cols = st.columns([1, 3, 2, 3])
            with cols[0]:
                st.write(f"{idx+1}")
            with cols[1]:
                if test['general_test_id'] and test['general_test_id'] != 0:
                    st.write(f"  ▫️ **{test['display_no']}**<br>{test['test_name']}", unsafe_allow_html=True)
                else:
                    st.write(f"**{test['display_no']}**<br>{test['test_name']}", unsafe_allow_html=True)
            with cols[2]:
                current_val = st.session_state.result_inputs[patient_key][test['test_id']]['test_values']
                new_val = st.text_input(
                    f"values_{idx}",
                    value=current_val,
                    label_visibility="collapsed",
                    key=f"input_val_{patient['patient_id']}_{idx}"
                )
                st.session_state.result_inputs[patient_key][test['test_id']]['test_values'] = new_val
            with cols[3]:
                current_rem = st.session_state.result_inputs[patient_key][test['test_id']]['remarks']
                new_rem = st.text_input(
                    f"remarks_{idx}",
                    value=current_rem,
                    label_visibility="collapsed",
                    key=f"input_rem_{patient['patient_id']}_{idx}"
                )
                st.session_state.result_inputs[patient_key][test['test_id']]['remarks'] = new_rem
            
            if idx < len(all_tests) - 1:
                st.markdown("---")
        
        st.markdown("<br>", unsafe_allow_html=True)
        submitted = st.form_submit_button("💾 Save All Results", type="primary")
        
        if submitted:
            success_count = 0
            error_count = 0
            
            for test in all_tests:
                test_id = test['test_id']
                test_values = st.session_state.result_inputs[patient_key][test_id]['test_values']
                remarks = st.session_state.result_inputs[patient_key][test_id]['remarks']
                
                success, msg = save_test_result(patient['patient_id'], test_id, test_values, remarks)
                if success:
                    success_count += 1
                else:
                    error_count += 1
                    st.error(f"Error saving {test['test_name']}: {msg}")
            
            if success_count > 0:
                st.success(f"✅ Successfully saved {success_count} result(s)!")
            if error_count > 0:
                st.error(f"❌ Failed to save {error_count} result(s). Check errors above.")
            
            if patient_key in st.session_state.result_inputs:
                del st.session_state.result_inputs[patient_key]
            st.rerun()
    
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🏠 Back to Dashboard", use_container_width=True):
        st.session_state.current_page = "dashboard"
        st.session_state.selected_patient = None
        patient_key = f"results_{patient['patient_id']}"
        if patient_key in st.session_state.result_inputs:
            del st.session_state.result_inputs[patient_key]
        st.rerun()

# -----------------------------
# TEST REPORT VIEWER (INTEGRATED WITH reports.py)
# -----------------------------
def test_report_viewer():
    """Generate and display test report using reports.py module"""
    if not st.session_state.selected_patient:
        st.session_state.current_page = "dashboard"
        st.rerun()
        return
    
    patient = st.session_state.selected_patient
    st.title(f"📄 Test Report - Lab No: {patient['lab_no']} | {patient['patient_name']}")
    
    try:
        # 🔑 CRITICAL: Generate report using reports.py module
        report_html = reports.generate_report(patient['patient_id'], format_type="standard")
        st.session_state.report_html = report_html
        
        # Display report with controls
        st.markdown("""
        <div style="text-align: center; margin: 20px 0; padding: 15px; background: #e8f4fc; border-radius: 8px; border: 2px solid #2c3e50;">
            <h3 style="margin: 0; color: #2c3e50; font-size: 20px;">🖨️ Report Controls</h3>
            <p style="margin: 8px 0 0; font-size: 15px; color: #2c3e50;">
                💡 <strong>Tip:</strong> Use browser's <strong>Print > Save as PDF</strong> for PDF version
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        # Render report
        st.components.v1.html(report_html, height=1100, scrolling=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns([1, 1, 1])
        with col1:
            if st.button("🏠 Back to Dashboard", use_container_width=True, type="secondary"):
                st.session_state.current_page = "dashboard"
                st.session_state.selected_patient = None
                st.session_state.report_html = None
                st.rerun()
        
        with col2:
            st.download_button(
                "💾 Download HTML Report",
                report_html,
                file_name=f"LabReport_Lab{patient['lab_no']}_Patient{patient['patient_no']}.html",
                mime="text/html",
                use_container_width=True,
                help="Save report as HTML file for viewing in browser"
            )
        
        with col3:
            st.info(
                "🖨️ **Print Instructions:**\n"
                "1. Click button above to download HTML\n"
                "2. Open in browser\n"
                "3. Press Ctrl+P (or Cmd+P)\n"
                "4. Choose 'Save as PDF'",
                icon="ℹ️"
            )
    
    except Exception as e:
        st.error(f"❌ Error generating report: {str(e)}")
        st.error("Please ensure reports.py is in the same directory as app.py")
        st.exception(e)
        
        if st.button("🏠 Back to Dashboard", use_container_width=True):
            st.session_state.current_page = "dashboard"
            st.session_state.selected_patient = None
            st.rerun()

# -----------------------------
# UPDATE PATIENT INFORMATION FORM
# -----------------------------
def update_patient_form():
    if not st.session_state.selected_patient:
        st.session_state.current_page = "dashboard"
        st.rerun()
        return
    
    patient = st.session_state.selected_patient
    st.title(f"✏️ Update Patient Information - Lab No: {patient['lab_no']}")
    
    try:
        con = get_connection()
        
        with st.form("update_patient_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                patient_name = st.text_input("Patient Name *", value=patient['patient_name'], max_chars=100)
                age = st.number_input("Age", min_value=0, max_value=150, value=int(patient['age']))
                sex = st.selectbox("Sex", ["Male", "Female", "Other"], index=["Male", "Female", "Other"].index(patient['sex']))
                mobile = st.text_input("Mobile No", value=patient['mobile'], max_chars=15)
            
            with col2:
                doctors = pd.read_sql("SELECT DoctorID, DoctorName FROM doctor ORDER BY DoctorName", con)
                doctor_opts = [""] + doctors["DoctorName"].tolist()
                current_doctor = patient.get('doctor', '')
                doctor_index = doctor_opts.index(current_doctor) if current_doctor in doctor_opts else 0
                doctor = st.selectbox("Referred By Doctor", doctor_opts, index=doctor_index)
                doctor_id = doctors.loc[doctors["DoctorName"] == doctor, "DoctorID"].values[0] if doctor else None
                
                city = st.text_input("City", value=patient.get('city', ''))
                address = st.text_area("Address", value=patient.get('address', ''), height=80)
            
            submitted = st.form_submit_button("💾 Update Patient", type="primary")
            
            if submitted:
                if not patient_name.strip():
                    st.error("⚠️ Patient Name is required")
                    return
                
                try:
                    cur = con.cursor()
                    cur.execute("""
                        UPDATE patient
                        SET Patient_Name = ?, Age = ?, Sex = ?, Mobile_No = ?,
                            Refered_By = ?, City = ?, Address = ?
                        WHERE Patient_Id = ?
                    """, (patient_name, age, sex, mobile, doctor_id, city, address, patient['patient_id']))
                    con.commit()
                    
                    st.success("✅ Patient information updated successfully!")
                    st.session_state.current_page = "dashboard"
                    st.session_state.selected_patient = None
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"Database error: {str(e)}")
        
        if st.button("🏠 Cancel & Back to Dashboard"):
            st.session_state.current_page = "dashboard"
            st.session_state.selected_patient = None
            st.rerun()
            
    except Exception as e:
        st.error(f"Error loading patient data: {str(e)}")
        st.exception(e)

# -----------------------------
# DELETE PATIENT CONFIRMATION
# -----------------------------
def delete_patient_confirmation():
    if not st.session_state.selected_patient:
        st.session_state.current_page = "dashboard"
        st.rerun()
        return
    
    patient = st.session_state.selected_patient
    st.title("⚠️ Delete Patient Confirmation")
    
    st.warning(f"""
    **Are you sure you want to delete this patient?**
    
    - Lab No: {patient['lab_no']}
    - Patient Name: {patient['patient_name']}
    
    This will permanently delete:
    - Patient record
    - All test records
    - Payment records
    - Test results
    
    **This action cannot be undone!**
    """)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🗑️ Yes, Delete Patient", type="primary", use_container_width=True):
            try:
                con = get_connection()
                cur = con.cursor()
                cur.execute("BEGIN TRANSACTION")
                
                patient_id_str = str(patient['patient_id'])
                
                cur.execute("DELETE FROM patient_test_results WHERE Patient_No = ?", (patient_id_str,))
                cur.execute("DELETE FROM patient_test WHERE PatientID = ?", (patient_id_str,))
                cur.execute("DELETE FROM patientpayment WHERE PatientID = ?", (patient_id_str,))
                cur.execute("DELETE FROM patient WHERE Patient_Id = ?", (patient['patient_id'],))
                
                con.commit()
                
                st.success("✅ Patient deleted successfully!")
                st.session_state.current_page = "dashboard"
                st.session_state.selected_patient = None
                st.rerun()
                
            except Exception as e:
                cur.execute("ROLLBACK TRANSACTION")
                st.error(f"Database error: {str(e)}")
                st.exception(e)
    
    with col2:
        if st.button("🏠 No, Back to Dashboard", use_container_width=True):
            st.session_state.current_page = "dashboard"
            st.session_state.selected_patient = None
            st.rerun()

# -----------------------------
# RECEIPT PREVIEW (PATIENT RECEIPT AFTER ENTRY)
# -----------------------------
def receipt_preview():
    if "last_saved" not in st.session_state:
        st.session_state.current_page = "dashboard"
        st.rerun()
        return
    
    data = st.session_state.last_saved
    lab_info = data["lab_info"]
    
    st.title("🖨️ Patient Receipts")
    st.caption("Both receipts are designed for A4 paper (each takes half page vertically)")
    
    all_tests = data['tests']
    
    # CUSTOMER RECEIPT HTML
    customer_receipt_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            @media print {{
                body {{ margin: 0; padding: 0; }}
                .receipt {{ width: 210mm; height: 148mm; page-break-after: always; }}
            }}
            .receipt {{
                font-family: Arial, sans-serif;
                width: 100%;
                max-width: 210mm;
                min-height: 148mm;
                margin: 0 auto;
                padding: 15px;
                border: 2px solid #2c3e50;
                background: #fff;
                box-sizing: border-box;
            }}
            .header {{ text-align: center; margin-bottom: 10px; }}
            .header h2 {{ color: #2c3e50; margin: 3px 0; font-size: 18px; }}
            .header p {{ margin: 2px 0; font-size: 12px; }}
            .divider {{ border-top: 1px dashed #2c3e50; margin: 8px 0; }}
            .patient-info {{ margin: 8px 0; }}
            .patient-info p {{ margin: 3px 0; font-size: 13px; }}
            .tests-table {{ width: 100%; border-collapse: collapse; margin: 8px 0; font-size: 12px; }}
            .tests-table th {{ background: #e8f4fc; padding: 4px; text-align: left; border-bottom: 1px solid #2c3e50; }}
            .tests-table td {{ padding: 4px; border-bottom: 1px dashed #ccc; }}
            .sub-test {{ color: #555; font-size: 11px; }}
            .payment-table {{ width: 100%; margin-top: 5px; font-size: 13px; }}
            .payment-table td {{ padding: 2px 0; }}
            .balance-due {{ color: {'red' if data['balance'] > 0 else 'green'}; font-weight: bold; }}
            .footer {{ text-align: center; margin-top: 10px; font-size: 11px; color: #7f8c8d; }}
            .badge {{ background: #e8f4fc; padding: 2px 8px; border-radius: 3px; font-weight: bold; display: inline-block; margin-top: 5px; }}
        </style>
    </head>
    <body>
        <div class="receipt">
            <div class="header">
                <h2>{lab_info['name']}</h2>
                <p>{lab_info['address']}</p>
                <p>📞 {lab_info['phone']}</p>
                <div class="divider"></div>
                <h3>PATIENT RECEIPT</h3>
                <div class="badge">CUSTOMER COPY</div>
            </div>
            
            <div class="patient-info">
                <p><strong>Lab No:</strong> {data['labno']}</p>
                <p><strong>Patient No:</strong> {data['patient_no']}</p>
                <p><strong>Date:</strong> {data['date']}</p>
                <p><strong>Patient:</strong> {data['name']}</p>
                <p><strong>Age/Sex:</strong> {data['age']} / {data['sex']}</p>
                <p><strong>Mobile:</strong> {data['mobile']}</p>
                <p><strong>Doctor:</strong> {data['doctor_name']}</p>
                <p><strong>City:</strong> {data['city']}</p>
            </div>
            
            <div class="divider"></div>
            
            <table class="tests-table">
                <thead>
                    <tr>
                        <th>Test</th>
                        <th style="text-align: right;">Amount</th>
                    </tr>
                </thead>
                <tbody>
    """
    
    for test in all_tests:
        test_class = "sub-test" if test["is_sub"] else ""
        customer_receipt_html += f"""
                    <tr class="{test_class}">
                        <td>{test['display_no']} {test['name']}</td>
                        <td style="text-align: right;">Rs. {test['rate']:.2f}</td>
                    </tr>
        """
    
    customer_receipt_html += f"""
                </tbody>
            </table>
            
            <div class="divider"></div>
            
            <table class="payment-table">
                <tr>
                    <td><strong>Total Amount</strong></td>
                    <td style="text-align: right;">Rs. {data['total']:.2f}</td>
                </tr>
                <tr>
                    <td><strong>Discount</strong></td>
                    <td style="text-align: right;">Rs. {data['discount']:.2f}</td>
                </tr>
                <tr>
                    <td><strong>Amount Paid</strong></td>
                    <td style="text-align: right;">Rs. {data['paid']:.2f}</td>
                </tr>
                <tr style="border-top: 2px solid #2c3e50;">
                    <td><strong>Balance Due</strong></td>
                    <td style="text-align: right;" class="balance-due">Rs. {data['balance']:.2f}</td>
                </tr>
            </table>
            
            <div class="divider"></div>
            
            <div class="footer">
                <p>Thank you for your visit!</p>
                <p>Results will be ready after {data['return_time'] or '5:00 PM'}</p>
                <p style="margin-top: 8px; font-size: 10px;">This is a computer-generated receipt. No signature required.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    # LAB RECEIPT HTML
    lab_receipt_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            @media print {{
                body {{ margin: 0; padding: 0; }}
                .receipt {{ width: 210mm; height: 148mm; page-break-after: always; }}
            }}
            .receipt {{
                font-family: Arial, sans-serif;
                width: 100%;
                max-width: 210mm;
                min-height: 148mm;
                margin: 0 auto;
                padding: 15px;
                border: 2px solid #e74c3c;
                background: #fff;
                box-sizing: border-box;
            }}
            .header {{ text-align: center; margin-bottom: 10px; }}
            .header h2 {{ color: #e74c3c; margin: 3px 0; font-size: 18px; }}
            .header p {{ margin: 2px 0; font-size: 12px; }}
            .divider {{ border-top: 1px dashed #e74c3c; margin: 8px 0; }}
            .patient-info {{ margin: 8px 0; }}
            .patient-info p {{ margin: 3px 0; font-size: 13px; }}
            .tests-table {{ width: 100%; border-collapse: collapse; margin: 8px 0; font-size: 12px; }}
            .tests-table th {{ background: #fadbd8; padding: 4px; text-align: left; border-bottom: 1px solid #e74c3c; }}
            .tests-table td {{ padding: 4px; border-bottom: 1px dashed #ccc; }}
            .sub-test {{ color: #555; font-size: 11px; }}
            .payment-table {{ width: 100%; margin-top: 5px; font-size: 13px; }}
            .payment-table td {{ padding: 2px 0; }}
            .balance-due {{ color: {'red' if data['balance'] > 0 else 'green'}; font-weight: bold; }}
            .footer {{ text-align: center; margin-top: 10px; font-size: 11px; color: #7f8c8d; }}
            .badge {{ background: #fadbd8; padding: 2px 8px; border-radius: 3px; font-weight: bold; color: #c0392b; display: inline-block; margin-top: 5px; }}
        </style>
    </head>
    <body>
        <div class="receipt">
            <div class="header">
                <h2>{lab_info['name']}</h2>
                <p>{lab_info['address']}</p>
                <p>📞 {lab_info['phone']}</p>
                <div class="divider"></div>
                <h3>PATIENT RECEIPT</h3>
                <div class="badge">LAB COPY - INTERNAL USE</div>
            </div>
            
            <div class="patient-info">
                <p><strong>Lab No:</strong> {data['labno']}</p>
                <p><strong>Patient No:</strong> {data['patient_no']}</p>
                <p><strong>Date:</strong> {data['date']}</p>
                <p><strong>Patient:</strong> {data['name']}</p>
                <p><strong>Age/Sex:</strong> {data['age']} / {data['sex']}</p>
                <p><strong>Mobile:</strong> {data['mobile']}</p>
                <p><strong>Doctor:</strong> {data['doctor_name']}</p>
                <p><strong>City:</strong> {data['city']}</p>
                <p><strong>Address:</strong> {data['address']}</p>
                <p><strong>Sample Source:</strong> {data['sample_source']}</p>
                <p><strong>Entered By:</strong> {st.session_state.user['user_name']}</p>
            </div>
            
            <div class="divider"></div>
            
            <table class="tests-table">
                <thead>
                    <tr>
                        <th>Display No</th>
                        <th>Test Name</th>
                        <th style="text-align: right;">Amount</th>
                    </tr>
                </thead>
                <tbody>
    """
    
    for test in all_tests:
        display_no = test['display_no'] if not test['is_sub'] else "Sub"
        lab_receipt_html += f"""
                    <tr class="{'sub-test' if test['is_sub'] else ''}">
                        <td>{display_no}</td>
                        <td>{test['name']}</td>
                        <td style="text-align: right;">Rs. {test['rate']:.2f}</td>
                    </tr>
        """
    
    lab_receipt_html += f"""
                </tbody>
            </table>
            
            <div class="divider"></div>
            
            <table class="payment-table">
                <tr>
                    <td><strong>Total Amount</strong></td>
                    <td style="text-align: right;">Rs. {data['total']:.2f}</td>
                </tr>
                <tr>
                    <td><strong>Discount</strong></td>
                    <td style="text-align: right;">Rs. {data['discount']:.2f}</td>
                </tr>
                <tr>
                    <td><strong>Amount Paid</strong></td>
                    <td style="text-align: right;">Rs. {data['paid']:.2f}</td>
                </tr>
                <tr style="border-top: 2px solid #e74c3c;">
                    <td><strong>Balance Due</strong></td>
                    <td style="text-align: right;" class="balance-due">Rs. {data['balance']:.2f}</td>
                </tr>
            </table>
            
            <div class="divider"></div>
            
            <div class="footer">
                <p><strong>INTERNAL COPY - FOR LAB USE ONLY</strong></p>
                <p>Results will be ready after {data['return_time'] or '5:00 PM'}</p>
                <p style="margin-top: 8px; font-size: 10px;">Patient must present this receipt to collect reports. Balance must be cleared before report release.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    st.subheader("📄 Customer Copy (Top Half of A4)")
    st.components.v1.html(customer_receipt_html, height=550, scrolling=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    st.subheader("📄 Lab Copy (Bottom Half of A4)")
    st.components.v1.html(lab_receipt_html, height=550, scrolling=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🏠 Back to Dashboard", use_container_width=True):
            st.session_state.current_page = "dashboard"
            st.rerun()
    with col2:
        st.download_button(
            "💾 Download Customer Receipt (HTML)",
            customer_receipt_html,
            file_name=f"receipt_customer_lab{data['labno']}_patient{data['patient_no']}.html",
            mime="text/html",
            use_container_width=True
        )
    with col3:
        st.download_button(
            "💾 Download Lab Receipt (HTML)",
            lab_receipt_html,
            file_name=f"receipt_lab_lab{data['labno']}_patient{data['patient_no']}.html",
            mime="text/html",
            use_container_width=True
        )

# ============================================================================
# REPORTS MENU SYSTEM (ADMINISTRATIVE REPORTS - NEW)
# ============================================================================

# -----------------------------
# REPORT 1: SEARCH PATIENT RECEIPT (ADMINISTRATIVE)
# -----------------------------
def search_patient_receipt():
    st.subheader("🔍 Search Patient Receipt")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        lab_no = st.text_input("Lab No")
    with col2:
        patient_no = st.text_input("Patient No")
    with col3:
        visit_date = st.date_input("Visit Date", value=datetime.today())
    
    if st.button("🔍 Search Receipt", type="primary", use_container_width=True):
        try:
            con = get_connection()
            cur = con.cursor()
            
            # Get lab info
            cur.execute("SELECT TOP 1 LabName, Address, PhoneNo, Pad_Logo FROM LabInfo")
            lab_info = cur.fetchone()
            
            # Search patient
            query = """
                SELECT 
                    p.Patient_Id, p.LabNo, p.PatientNo, p.Patient_Name, p.Age, p.Sex, 
                    p.Mobile_No, p.Visit_Date, p.ReturnTime, p.City, p.Address,
                    d.DoctorName AS Referred_By,
                    pp.TotalAmount, pp.Discount, pp.AmountPaid,
                    (ISNULL(pp.TotalAmount,0) - ISNULL(pp.Discount,0) - ISNULL(pp.AmountPaid,0)) AS Balance
                FROM patient p
                LEFT JOIN doctor d ON p.Refered_By = d.DoctorID
                LEFT JOIN patientpayment pp ON p.Patient_Id = pp.PatientID
                WHERE 1=1
            """
            params = []
            
            if lab_no:
                query += " AND p.LabNo = ?"
                params.append(lab_no)
            if patient_no:
                query += " AND p.PatientNo = ?"
                params.append(patient_no)
            if visit_date:
                query += " AND CAST(p.Visit_Date AS DATE) = ?"
                params.append(visit_date)
            
            query += " ORDER BY p.Visit_Date DESC"
            
            cur.execute(query, params)
            patient = cur.fetchone()
            
            if not patient:
                st.warning("⚠️ No patient found with the provided criteria")
                return
            
            # Get patient tests
            cur.execute("""
                SELECT 
                    ti.Test_Display_No,
                    t.Test_Name,
                    ti.SRate
                FROM patient_test pt
                JOIN test_identity ti ON pt.Test_ID = ti.Id
                JOIN test t ON ti.Id = t.Id
                WHERE pt.PatientID = ?
                ORDER BY CAST(ti.Test_Display_No AS VARCHAR(50))
            """, (patient.Patient_Id,))
            tests = cur.fetchall()
            
            # Generate dual receipt HTML
            receipt_html = generate_dual_receipt_html(patient, tests, lab_info)
            
            # Display receipt
            st.components.v1.html(receipt_html, height=800, scrolling=True)
            
            # Download buttons
            st.markdown("---")
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                st.download_button(
                    label="💾 Download Receipt (HTML)",
                    data=receipt_html,
                    file_name=f"Receipt_Lab{patient.LabNo}_{patient.PatientNo}_{visit_date}.html",
                    mime="text/html",
                    use_container_width=True
                )
                
        except Exception as e:
            st.error(f"Error generating receipt: {str(e)}")
            st.exception(e)

def generate_dual_receipt_html(patient, tests, lab_info):
    # Format tests list
    tests_list = ", ".join([f"{t.Test_Name}" for t in tests]) if tests else "No tests recorded"
    
    # Format amounts
    total = patient.TotalAmount if patient.TotalAmount else 0
    discount = patient.Discount if patient.Discount else 0
    paid = patient.AmountPaid if patient.AmountPaid else 0
    balance = patient.Balance if patient.Balance else 0
    
    # Format dates
    visit_date = patient.Visit_Date.strftime('%d-%b-%Y') if patient.Visit_Date else ""
    return_time = patient.ReturnTime.strftime('%I:%M %p') if patient.ReturnTime else "N/A"
    
    # Lab logo handling
    logo_html = ""
    if lab_info and lab_info[3]:  # Pad_Logo exists
        try:
            logo_base64 = base64.b64encode(lab_info[3]).decode('utf-8')
            logo_html = f'<img src="data:image/png;base64,{logo_base64}" style="max-height:40px; max-width:150px;">'
        except:
            logo_html = f"<h3>{lab_info[0]}</h3>"
    elif lab_info:
        logo_html = f"<h3>{lab_info[0]}</h3>"
    
    # Generate SINGLE PAGE with TWO RECEIPTS (TOP + BOTTOM)
    receipt_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Receipt - Lab No: {patient.LabNo}</title>
        <style>
            @media print {{
                body {{ margin: 0; padding: 0; }}
                .receipt-page {{ width: 210mm; height: 297mm; margin: 0; padding: 0; }}
                .receipt {{ page-break-inside: avoid; }}
            }}
            body {{
                font-family: Arial, sans-serif;
                margin: 0;
                padding: 0;
                background: #f5f7fa;
            }}
            .receipt-page {{
                width: 210mm;
                height: 297mm;
                margin: 10mm auto;
                background: white;
                box-shadow: 0 0 10px rgba(0,0,0,0.1);
            }}
            .receipt {{
                width: 190mm;
                margin: 10mm;
                padding: 15px;
                border: 1px solid #000;
            }}
            .receipt-top {{
                border-bottom: 1px dashed #000;
                padding-bottom: 10px;
                margin-bottom: 10px;
            }}
            .receipt-bottom {{
                padding-top: 10px;
                margin-top: 10px;
            }}
            .header {{
                text-align: center;
                margin-bottom: 10px;
            }}
            .header h2 {{
                margin: 3px 0;
                font-size: 18px;
                color: #2c3e50;
            }}
            .header p {{
                margin: 2px 0;
                font-size: 12px;
            }}
            .receipt-info {{
                display: flex;
                justify-content: space-between;
                font-size: 13px;
                margin: 8px 0;
            }}
            .patient-info {{
                margin: 10px 0;
                font-size: 13px;
            }}
            .patient-info p {{
                margin: 3px 0;
            }}
            .tests-list {{
                margin: 10px 0;
                font-size: 12px;
                line-height: 1.4;
            }}
            .payment-summary {{
                width: 100%;
                border-collapse: collapse;
                margin: 15px 0;
                font-size: 13px;
            }}
            .payment-summary td {{
                padding: 4px 8px;
                border-bottom: 1px solid #000;
            }}
            .payment-summary tr:last-child td {{
                border-top: 2px solid #000;
                font-weight: bold;
            }}
            .balance-due {{
                color: {'red' if balance > 0 else 'green'};
                font-weight: bold;
            }}
            .footer {{
                text-align: center;
                margin-top: 15px;
                font-size: 11px;
                color: #7f8c8d;
            }}
            .badge {{
                background: #e8f4fc;
                padding: 2px 8px;
                border-radius: 3px;
                font-weight: bold;
                display: inline-block;
                margin-top: 5px;
                font-size: 12px;
            }}
            .lab-badge {{
                background: #fadbd8;
                color: #c0392b;
            }}
        </style>
    </head>
    <body>
        <div class="receipt-page">
            <!-- TOP RECEIPT (CUSTOMER COPY) -->
            <div class="receipt receipt-top">
                <div class="header">
                    {logo_html}
                    <p>{lab_info[1] if lab_info else ''}<br>📞 {lab_info[2] if lab_info else ''}</p>
                    <div class="badge">CUSTOMER COPY</div>
                </div>
                <div class="receipt-info">
                    <div><strong>Lab No:</strong> {patient.LabNo}</div>
                    <div><strong>Date:</strong> {visit_date}</div>
                    <div><strong>Receipt No:</strong> {patient.PatientNo}</div>
                </div>
                <div class="patient-info">
                    <p><strong>Patient:</strong> {patient.Patient_Name}</p>
                    <p><strong>Age/Sex:</strong> {patient.Age} / {patient.Sex}</p>
                    <p><strong>Mobile:</strong> {patient.Mobile_No or 'N/A'}</p>
                    <p><strong>City:</strong> {patient.City or 'N/A'}</p>
                    <p><strong>Referred by:</strong> {patient.Referred_By or 'N/A'}</p>
                    <p><strong>Delivery:</strong> {visit_date} {return_time}</p>
                </div>
                <div class="tests-list">
                    <strong>Tests Performed:</strong><br>
                    {tests_list}
                </div>
                <table class="payment-summary">
                    <tr>
                        <td><strong>Total</strong></td>
                        <td style="text-align: right;">Rs. {total:,.2f}</td>
                    </tr>
                    <tr>
                        <td><strong>Discount</strong></td>
                        <td style="text-align: right;">Rs. {discount:,.2f}</td>
                    </tr>
                    <tr>
                        <td><strong>Paid</strong></td>
                        <td style="text-align: right;">Rs. {paid:,.2f}</td>
                    </tr>
                    <tr>
                        <td><strong>Balance</strong></td>
                        <td style="text-align: right;" class="balance-due">Rs. {balance:,.2f}</td>
                    </tr>
                </table>
                <div class="footer">
                    <p>Received with thanks the sum of Rs. {paid:,.2f} in Cash</p>
                    <p style="margin-top: 8px; font-size: 10px;">Note: Computer generated receipt. No signature required.</p>
                </div>
            </div>
            
            <!-- BOTTOM RECEIPT (LAB COPY) -->
            <div class="receipt receipt-bottom">
                <div class="header">
                    {logo_html}
                    <p>{lab_info[1] if lab_info else ''}<br>📞 {lab_info[2] if lab_info else ''}</p>
                    <div class="badge lab-badge">LAB COPY</div>
                </div>
                <div class="receipt-info">
                    <div><strong>Lab No:</strong> {patient.LabNo}</div>
                    <div><strong>Date:</strong> {visit_date}</div>
                    <div><strong>Receipt No:</strong> {patient.PatientNo}</div>
                </div>
                <div class="patient-info">
                    <p><strong>Patient:</strong> {patient.Patient_Name}</p>
                    <p><strong>Age/Sex:</strong> {patient.Age} / {patient.Sex}</p>
                    <p><strong>Mobile:</strong> {patient.Mobile_No or 'N/A'}</p>
                    <p><strong>City:</strong> {patient.City or 'N/A'}</p>
                    <p><strong>Address:</strong> {patient.Address or 'N/A'}</p>
                    <p><strong>Referred by:</strong> {patient.Referred_By or 'N/A'}</p>
                    <p><strong>Delivery:</strong> {visit_date} {return_time}</p>
                </div>
                <div class="tests-list">
                    <strong>Tests Performed:</strong><br>
                    {tests_list}
                </div>
                <table class="payment-summary">
                    <tr>
                        <td><strong>Total</strong></td>
                        <td style="text-align: right;">Rs. {total:,.2f}</td>
                    </tr>
                    <tr>
                        <td><strong>Discount</strong></td>
                        <td style="text-align: right;">Rs. {discount:,.2f}</td>
                    </tr>
                    <tr>
                        <td><strong>Paid</strong></td>
                        <td style="text-align: right;">Rs. {paid:,.2f}</td>
                    </tr>
                    <tr>
                        <td><strong>Balance</strong></td>
                        <td style="text-align: right;" class="balance-due">Rs. {balance:,.2f}</td>
                    </tr>
                </table>
                <div class="footer">
                    <p><strong>INTERNAL USE ONLY</strong></p>
                    <p>Results ready after {return_time}. Balance must be cleared before report release.</p>
                    <p style="margin-top: 8px; font-size: 10px;">Note: Computer generated receipt. No signature required.</p>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    
    return receipt_html

# -----------------------------
# REPORT 2: DAILY PAYMENT DETAIL
# -----------------------------
def daily_payment_detail_report():
    st.subheader("💰 Daily Payment Detail Report")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        from_date = st.date_input("From Date", value=datetime.today() - timedelta(days=1))
    with col2:
        to_date = st.date_input("To Date", value=datetime.today())
    with col3:
        from_lab = st.number_input("From Lab No", min_value=1, value=1)
    with col4:
        to_lab = st.number_input("To Lab No", min_value=1, value=1000)
    
    if st.button("📊 Generate Report", type="primary", use_container_width=True):
        try:
            con = get_connection()
            
            # Main patient payment data (SQL Server 2012 compatible)
            df = pd.read_sql("""
                SELECT 
                    p.PatientNo AS [Pat#],
                    p.LabNo AS [Lab#],
                    p.Patient_Name AS [Patient Name],
                    STUFF((
                        SELECT ', ' + t2.Test_Name
                        FROM patient_test pt2
                        JOIN test t2 ON pt2.Test_ID = t2.Test_Id
                        WHERE pt2.PatientID = CAST(p.Patient_Id AS VARCHAR(50))
                        FOR XML PATH(''), TYPE
                    ).value('.', 'NVARCHAR(MAX)'), 1, 2, '') AS Tests,
                    CONVERT(VARCHAR, p.Visit_Date, 106) AS [Visit Date],
                    CONVERT(VARCHAR(15), p.Visit_Date, 100) AS [Visit Time],
                    ISNULL(d.DoctorName, 'N/A') AS [Referred By],
                    ISNULL(pp.TotalAmount, 0) AS Total,
                    ISNULL(pp.Discount, 0) AS Discount,
                    ISNULL(pp.AmountPaid, 0) AS Paid,
                    (ISNULL(pp.TotalAmount,0) - ISNULL(pp.Discount,0) - ISNULL(pp.AmountPaid,0)) AS Due
                FROM patient p
                LEFT JOIN doctor d ON p.Refered_By = d.DoctorID
                LEFT JOIN patientpayment pp ON p.Patient_Id = pp.PatientID
                WHERE CAST(p.Visit_Date AS DATE) BETWEEN ? AND ?
                  AND p.LabNo BETWEEN ? AND ?
                ORDER BY p.LabNo
            """, con, params=[from_date, to_date, from_lab, to_lab])
            
            if df.empty:
                st.warning("⚠️ No payment records found for the selected criteria")
                return
            
            # Calculate totals
            total_amount = df['Total'].sum()
            total_discount = df['Discount'].sum()
            total_paid = df['Paid'].sum()
            total_due = df['Due'].sum()
            
            # Previous due calculation
            prev_due_query = """
                SELECT ISNULL(SUM(ISNULL(pp.TotalAmount,0) - ISNULL(pp.Discount,0) - ISNULL(pp.AmountPaid,0)), 0) AS PrevDue
                FROM patient p
                LEFT JOIN patientpayment pp ON p.Patient_Id = pp.PatientID
                WHERE CAST(p.Visit_Date AS DATE) < ?
                  AND (ISNULL(pp.TotalAmount,0) - ISNULL(pp.Discount,0) - ISNULL(pp.AmountPaid,0)) > 0
            """
            prev_due_df = pd.read_sql(prev_due_query, con, params=[from_date])
            prev_due = prev_due_df['PrevDue'].iloc[0] if not prev_due_df.empty else 0
            
            # Monthly sale calculation
            month_start = datetime(to_date.year, to_date.month, 1)
            monthly_query = """
                SELECT ISNULL(SUM(ISNULL(pp.AmountPaid,0)), 0) AS MonthlySale
                FROM patient p
                LEFT JOIN patientpayment pp ON p.Patient_Id = pp.PatientID
                WHERE CAST(p.Visit_Date AS DATE) BETWEEN ? AND ?
            """
            monthly_df = pd.read_sql(monthly_query, con, params=[month_start, to_date])
            monthly_sale = monthly_df['MonthlySale'].iloc[0] if not monthly_df.empty else 0
            
            # Display report header (EXACTLY LIKE YOUR PDF)
            st.markdown(f"""
            <div style="text-align:center; background:#2c3e50; color:white; padding:15px; border-radius:8px; margin-bottom:20px;">
                <h2 style="margin:0; font-size:24px;">DAILY PAYMENT DETAIL</h2>
                <div style="margin-top:8px; font-size:16px;">
                    <span style="margin:0 15px; font-weight:bold;">{from_date.strftime('%d-%b-%Y')}</span>
                    <span style="margin:0 15px;">to</span>
                    <span style="margin:0 15px; font-weight:bold;">{to_date.strftime('%d-%b-%Y')}</span>
                    <span style="margin:0 15px;">|</span>
                    <span style="margin:0 15px;">Lab No: {from_lab} to {to_lab}</span>
                    <span style="margin:0 15px;">|</span>
                    <span style="margin:0 15px; background:#3498db; padding:3px 8px; border-radius:4px;">
                        USER: {st.session_state.user['user_name']}
                    </span>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Display data table
            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True,
                height=400,
                column_config={
                    "Pat#": st.column_config.TextColumn(width="small"),
                    "Lab#": st.column_config.NumberColumn(width="small"),
                    "Patient Name": st.column_config.TextColumn(width="medium"),
                    "Tests": st.column_config.TextColumn(width="large"),
                    "Visit Date": st.column_config.TextColumn(width="small"),
                    "Visit Time": st.column_config.TextColumn(width="small"),
                    "Referred By": st.column_config.TextColumn(width="medium"),
                    "Total": st.column_config.NumberColumn(format="Rs. %.2f", width="small"),
                    "Discount": st.column_config.NumberColumn(format="Rs. %.2f", width="small"),
                    "Paid": st.column_config.NumberColumn(format="Rs. %.2f", width="small"),
                    "Due": st.column_config.NumberColumn(format="Rs. %.2f", width="small"),
                }
            )
            
            # Footer totals (EXACTLY LIKE YOUR PDF)
            st.markdown("---")
            col1, col2, col3, col4, col5, col6 = st.columns(6)
            with col1:
                st.metric("Total Amount", f"Rs. {total_amount:,.2f}")
            with col2:
                st.metric("Total Discount", f"Rs. {total_discount:,.2f}")
            with col3:
                st.metric("Total Paid", f"Rs. {total_paid:,.2f}")
            with col4:
                st.metric("Total Due", f"Rs. {total_due:,.2f}")
            with col5:
                st.metric("Previous Due", f"Rs. {prev_due:,.2f}")
            with col6:
                st.metric("Recovered", f"Rs. {total_paid:,.2f}")
            
            st.markdown("---")
            col1, col2 = st.columns(2)
            with col1:
                st.metric("TOTAL CASH OF TODAY", f"Rs. {total_paid:,.2f}", delta=None, delta_color="off")
            with col2:
                st.metric("TOTAL MONTHLY SALE", f"Rs. {monthly_sale:,.2f}", delta=None, delta_color="off")
            
            # Download button
            st.markdown("---")
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                "💾 Download Report (CSV)",
                csv,
                f"DailyPayment_{from_date}_to_{to_date}.csv",
                "text/csv",
                use_container_width=True,
                type="primary"
            )
                
        except Exception as e:
            st.error(f"Error generating report: {str(e)}")
            st.exception(e)

# -----------------------------
# REPORT 3: DOCTOR WISE PATIENT REPORT
# -----------------------------
def doctor_wise_patient_report():
    st.subheader("👨‍⚕️ Doctor Wise Patient Report")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        from_date = st.date_input("From Date", value=datetime.today().replace(day=1))
    with col2:
        to_date = st.date_input("To Date", value=datetime.today())
    with col3:
        # Get doctor list
        try:
            con = get_connection()
            doctor_df = pd.read_sql("SELECT DoctorID, DoctorName FROM doctor ORDER BY DoctorName", con)
            doctor_list = ["All Doctors"] + doctor_df['DoctorName'].tolist()
        except:
            doctor_list = ["All Doctors"]
        
        doctor_filter = st.selectbox("Select Doctor", doctor_list)
    
    if st.button("📊 Generate Report", type="primary", use_container_width=True):
        try:
            con = get_connection()
            
            # Build query with optional doctor filter
            query = """
                SELECT 
                    d.DoctorName AS [Doctor Name],
                    p.Patient_Name AS [Patient Name],
                    CONVERT(VARCHAR, p.Visit_Date, 106) AS [Date],
                    STUFF((
                        SELECT ', ' + t2.Test_Name
                        FROM patient_test pt2
                        JOIN test t2 ON pt2.Test_ID = t2.Test_Id
                        WHERE pt2.PatientID = CAST(p.Patient_Id AS VARCHAR(50))
                        FOR XML PATH(''), TYPE
                    ).value('.', 'NVARCHAR(MAX)'), 1, 2, '') AS Tests,
                    ISNULL(pp.TotalAmount, 0) AS Total,
                    ISNULL(pp.Discount, 0) AS Discount,
                    ISNULL(pp.AmountPaid, 0) AS Paid,
                    (ISNULL(pp.TotalAmount,0) - ISNULL(pp.Discount,0) - ISNULL(pp.AmountPaid,0)) AS Due
                FROM patient p
                JOIN doctor d ON p.Refered_By = d.DoctorID
                LEFT JOIN patientpayment pp ON p.Patient_Id = pp.PatientID
                WHERE CAST(p.Visit_Date AS DATE) BETWEEN ? AND ?
            """
            params = [from_date, to_date]
            
            if doctor_filter != "All Doctors":
                query += " AND d.DoctorName = ?"
                params.append(doctor_filter)
            
            query += " ORDER BY d.DoctorName, p.Visit_Date DESC"
            
            df = pd.read_sql(query, con, params=params)
            
            if df.empty:
                st.warning("⚠️ No patient records found for the selected criteria")
                return
            
            # Display report header (EXACTLY LIKE YOUR PDF)
            st.markdown(f"""
            <div style="text-align:center; background:#2980b9; color:white; padding:15px; border-radius:8px; margin-bottom:20px;">
                <h2 style="margin:0; font-size:24px;">DOCTOR REFERALS</h2>
                <div style="margin-top:8px; font-size:16px;">
                    <span style="margin:0 15px; font-weight:bold;">{from_date.strftime('%d-%b-%Y')}</span>
                    <span style="margin:0 15px;">to</span>
                    <span style="margin:0 15px; font-weight:bold;">{to_date.strftime('%d-%b-%Y')}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Group by doctor and calculate totals
            doctors = df['Doctor Name'].unique()
            grand_total_patients = 0
            grand_total_amount = 0
            grand_total_paid = 0
            
            for doctor in doctors:
                doctor_df = df[df['Doctor Name'] == doctor]
                total_patients = len(doctor_df)
                total_amount = doctor_df['Total'].sum()
                total_paid = doctor_df['Paid'].sum()
                
                grand_total_patients += total_patients
                grand_total_amount += total_amount
                grand_total_paid += total_paid
                
                # Doctor section header
                st.markdown(f"### 👨‍⚕️ {doctor}")
                
                # Doctor data table
                st.dataframe(
                    doctor_df.drop(columns=['Doctor Name']),
                    use_container_width=True,
                    hide_index=True,
                    height=200,
                    column_config={
                        "Patient Name": st.column_config.TextColumn(width="medium"),
                        "Date": st.column_config.TextColumn(width="small"),
                        "Tests": st.column_config.TextColumn(width="large"),
                        "Total": st.column_config.NumberColumn(format="Rs. %.2f", width="small"),
                        "Discount": st.column_config.NumberColumn(format="Rs. %.2f", width="small"),
                        "Paid": st.column_config.NumberColumn(format="Rs. %.2f", width="small"),
                        "Due": st.column_config.NumberColumn(format="Rs. %.2f", width="small"),
                    }
                )
                
                # Doctor totals
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Total Patients", total_patients)
                with col2:
                    st.metric("Total Amount", f"Rs. {total_amount:,.2f}")
                with col3:
                    st.metric("Total Paid", f"Rs. {total_paid:,.2f}")
                with col4:
                    st.metric("Due Amount", f"Rs. {(total_amount - total_paid):,.2f}")
                st.markdown("---")
            
            # Grand totals (EXACTLY LIKE YOUR PDF)
            st.markdown("## 📊 GRAND TOTALS")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("TOTAL PATIENTS REFERRED", grand_total_patients)
            with col2:
                st.metric("TOTAL AMOUNT", f"Rs. {grand_total_amount:,.2f}")
            with col3:
                st.metric("TOTAL PAID", f"Rs. {grand_total_paid:,.2f}")
            with col4:
                st.metric("TOTAL DUE", f"Rs. {(grand_total_amount - grand_total_paid):,.2f}")
            
            # Download button
            st.markdown("---")
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                "💾 Download Report (CSV)",
                csv,
                f"DoctorReport_{from_date}_to_{to_date}.csv",
                "text/csv",
                use_container_width=True,
                type="primary"
            )
                
        except Exception as e:
            st.error(f"Error generating report: {str(e)}")
            st.exception(e)

# -----------------------------
# REPORT 4: TOP TEST DATE TO DATE
# -----------------------------
def top_test_report():
    st.subheader("📈 Top Test Date to Date Report")
    
    col1, col2 = st.columns(2)
    with col1:
        from_date = st.date_input("From Date", value=datetime.today().replace(day=1))
    with col2:
        to_date = st.date_input("To Date", value=datetime.today())
    
    if st.button("📊 Generate Report", type="primary", use_container_width=True):
        try:
            con = get_connection()
            
            # Get top tests by count and revenue (SQL Server 2012 compatible)
            df = pd.read_sql("""
                SELECT 
                    t.Test_Name AS [Test Name],
                    COUNT(pt.Test_ID) AS [Count],
                    SUM(ti.SRate) AS [Total Amount],
                    AVG(ti.SRate) AS [Avg Rate]
                FROM patient_test pt
                JOIN patient p ON pt.PatientID = p.Patient_Id
                JOIN test t ON pt.Test_ID = t.Test_Id
                JOIN test_identity ti ON t.Id = ti.Id
                WHERE CAST(p.Visit_Date AS DATE) BETWEEN ? AND ?
                GROUP BY t.Test_Name
                ORDER BY [Count] DESC
            """, con, params=[from_date, to_date])
            
            if df.empty:
                st.warning("⚠️ No test records found for the selected date range")
                return
            
            # Add percentage columns
            total_count = df['Count'].sum()
            total_amount = df['Total Amount'].sum()
            
            df['% of Total'] = ((df['Count'] / total_count) * 100).round(1)
            df['% of Revenue'] = ((df['Total Amount'] / total_amount) * 100).round(1)
            
            # Format currency columns
            df_display = df.copy()
            df_display['Total Amount'] = df_display['Total Amount'].apply(lambda x: f"Rs. {x:,.2f}")
            df_display['Avg Rate'] = df_display['Avg Rate'].apply(lambda x: f"Rs. {x:,.2f}")
            
            # Display report header (EXACTLY LIKE YOUR PDF STYLE)
            st.markdown(f"""
            <div style="text-align:center; background:#27ae60; color:white; padding:15px; border-radius:8px; margin-bottom:20px;">
                <h2 style="margin:0; font-size:24px;">TOP TESTS REPORT</h2>
                <div style="margin-top:8px; font-size:16px;">
                    <span style="margin:0 15px; font-weight:bold;">{from_date.strftime('%d-%b-%Y')}</span>
                    <span style="margin:0 15px;">to</span>
                    <span style="margin:0 15px; font-weight:bold;">{to_date.strftime('%d-%b-%Y')}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Display report table
            st.dataframe(
                df_display,
                use_container_width=True,
                hide_index=True,
                height=500,
                column_config={
                    "Test Name": st.column_config.TextColumn(width="medium"),
                    "Count": st.column_config.NumberColumn(width="small"),
                    "Total Amount": st.column_config.TextColumn(width="small"),
                    "Avg Rate": st.column_config.TextColumn(width="small"),
                    "% of Total": st.column_config.NumberColumn(format="%.1f%%", width="small"),
                    "% of Revenue": st.column_config.NumberColumn(format="%.1f%%", width="small"),
                }
            )
            
            # Summary metrics (EXACTLY LIKE YOUR PDF STYLE)
            st.markdown("## 📊 SUMMARY")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("TOTAL TESTS PERFORMED", f"{total_count:,}")
            with col2:
                st.metric("TOTAL REVENUE", f"Rs. {total_amount:,.2f}")
            with col3:
                st.metric("MOST POPULAR TEST", df.iloc[0]['Test Name'])
            with col4:
                st.metric("HIGHEST REVENUE TEST", 
                         df.loc[df['Total Amount'].idxmax()]['Test Name'])
            
            # Chart visualization
            st.markdown("## 📈 TEST DISTRIBUTION")
            chart_data = df.head(10)[['Test Name', 'Count']].set_index('Test Name')
            st.bar_chart(chart_data, height=400)
            
            # Download button
            st.markdown("---")
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                "💾 Download Report (CSV)",
                csv,
                f"TopTests_{from_date}_to_{to_date}.csv",
                "text/csv",
                use_container_width=True,
                type="primary"
            )
                
        except Exception as e:
            st.error(f"Error generating report: {str(e)}")
            st.exception(e)

# -----------------------------
# REPORTS MENU SYSTEM (NEW - MATCHES YOUR PDF SAMPLES)
# -----------------------------
def reports_menu():
    st.title("📑 Laboratory Reports")
    st.caption(f"User: {st.session_state.user['user_name']} | Lab: {st.session_state.lab_info['name']}")
    st.divider()
    
    # Report selection buttons (4 columns matching your requirements)
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("🔍 Search Patient\nReceipt", use_container_width=True,
                    type="primary" if st.session_state.selected_report == "receipt" else "secondary",
                    help="Search & print patient receipts by Lab No, Patient No or Date"):
            st.session_state.selected_report = "receipt"
            st.session_state.report_params = {}
            st.rerun()
    
    with col2:
        if st.button("💰 Daily Payment\nDetail Report", use_container_width=True,
                    type="primary" if st.session_state.selected_report == "daily_payment" else "secondary",
                    help="Daily payment summary with patient details and balances"):
            st.session_state.selected_report = "daily_payment"
            st.session_state.report_params = {}
            st.rerun()
    
    with col3:
        if st.button("👨‍⚕️ Doctor Wise\nPatient Report", use_container_width=True,
                    type="primary" if st.session_state.selected_report == "doctor" else "secondary",
                    help="Patient reports grouped by referring doctor"):
            st.session_state.selected_report = "doctor"
            st.session_state.report_params = {}
            st.rerun()
    
    with col4:
        if st.button("📈 Top Test\nDate to Date", use_container_width=True,
                    type="primary" if st.session_state.selected_report == "top_test" else "secondary",
                    help="Most ordered tests analysis for date range"):
            st.session_state.selected_report = "top_test"
            st.session_state.report_params = {}
            st.rerun()
    
    st.divider()
    
    # Render selected report
    if st.session_state.selected_report == "receipt":
        search_patient_receipt()
    elif st.session_state.selected_report == "daily_payment":
        daily_payment_detail_report()
    elif st.session_state.selected_report == "doctor":
        doctor_wise_patient_report()
    elif st.session_state.selected_report == "top_test":
        top_test_report()
    else:
        st.info("👈 Select a report type from the options above to get started")

# -----------------------------
# MAIN APPLICATION ROUTER
# -----------------------------
def main():
    if not st.session_state.logged_in:
        login_screen()
        return
    
    # Sidebar navigation
    sidebar_menu()
    
    # Page routing
    if st.session_state.current_page == "dashboard":
        dashboard()
    elif st.session_state.current_page == "test_selection":
        test_selection()
    elif st.session_state.current_page == "patient_entry":
        patient_entry_form()
    elif st.session_state.current_page == "test_results":
        test_results_entry()
    elif st.session_state.current_page == "test_report":
        test_report_viewer()
    elif st.session_state.current_page == "patient_update":
        update_patient_form()
    elif st.session_state.current_page == "patient_delete":
        delete_patient_confirmation()
    elif st.session_state.current_page == "receipt":
        receipt_preview()
    elif st.session_state.current_page == "reports_menu":
        reports_menu()
    else:
        st.warning(f"Page '{st.session_state.current_page}' not implemented yet")
        if st.button("🏠 Back to Dashboard"):
            st.session_state.current_page = "dashboard"
            st.rerun()

# -----------------------------
# RUN APPLICATION
# -----------------------------
if __name__ == "__main__":
    st.set_page_config(
        page_title="Laboratory Management System",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    main()