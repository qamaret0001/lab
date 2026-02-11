import streamlit as st
from db import get_connection
import pandas as pd

def dashboard():
    st.title(st.session_state.lab_name)
    st.subheader("Today Patients")

    conn = get_connection()

    query = """
    SELECT 
        p.LabNo,
        p.Patient_Name,
        STRING_AGG(ti.Test_Display_Name, ', ') AS Tests,
        (pp.TotalAmount - pp.AmountPaid) AS Balance,
        CASE 
            WHEN EXISTS (
                SELECT 1 FROM patient_test_results r
                WHERE r.Patient_No = p.PatientNo
            ) THEN 'Ready'
            ELSE 'Waiting'
        END AS Status
    FROM patient p
    JOIN patient_test pt ON p.Patient_Id = pt.PatientID
    JOIN Test_identity ti ON pt.Test_ID = ti.Id
    LEFT JOIN patientpayment pp ON p.Patient_Id = pp.PatientID
    WHERE 
        CAST(p.Visit_Date AS DATE) = CAST(GETDATE() AS DATE)
        AND p.LabID = ?
    GROUP BY 
        p.LabNo, p.Patient_Name, pp.TotalAmount, pp.AmountPaid
    ORDER BY p.LabNo DESC
    """

    df = pd.read_sql(query, conn, params=[st.session_state.lab_id])
    st.dataframe(df, use_container_width=True)
