"""
Laboratory Report Generation Module - SUB-TESTS ONLY (NO MAIN TEST RESULTS)
Features: Only sub-tests displayed, grouped by main test, proper hierarchy from Test table
"""
import pyodbc
import base64
from io import BytesIO
from datetime import datetime
import re

# Optional QR Code support
try:
    import qrcode
    QR_AVAILABLE = True
except ImportError:
    QR_AVAILABLE = False

# -----------------------------
# DATABASE CONNECTION
# -----------------------------
def get_connection():
    return pyodbc.connect(
        "DRIVER={ODBC Driver 17 for SQL Server};"
        "SERVER=dbserver\\sqlexpress;"
        "DATABASE=Lab;"
        "UID=sa;"
        "PWD=aielitetechsims2000"
    )

# -----------------------------
# QR CODE GENERATION
# -----------------------------
def generate_qr_code(data):
    """Generate QR code as base64 string"""
    if not QR_AVAILABLE:
        return None
    
    try:
        qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=8, border=2)
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode()
    except:
        return None

# -----------------------------
# CHECK ABNORMAL VALUE
# -----------------------------
def is_abnormal(result_value, reference_range):
    """Check if result is outside reference range"""
    if not result_value or not reference_range:
        return False
    
    result_num = re.search(r'[\d.]+', str(result_value))
    if not result_num:
        return False
    
    result_val = float(result_num.group())
    ref_clean = reference_range.strip().lower()
    
    if '-' in ref_clean:
        try:
            parts = ref_clean.split('-')
            low = float(parts[0].strip())
            high = float(parts[1].strip())
            return result_val < low or result_val > high
        except:
            return False
    
    if ref_clean.startswith('<'):
        try:
            limit = float(ref_clean.replace('<', '').strip())
            return result_val > limit
        except:
            return False
    
    if ref_clean.startswith('>'):
        try:
            limit = float(ref_clean.replace('>', '').strip())
            return result_val < limit
        except:
            return False
    
    return False

# -----------------------------
# FETCH PATIENT REPORT DATA (SUB-TESTS ONLY - GROUPED BY MAIN TEST)
# -----------------------------
def get_patient_report_data(patient_id):
    """Fetch ONLY sub-tests grouped by their main test (General_Test_Id)"""
    con = get_connection()
    cur = con.cursor()
    
    # Get patient details with logo
    cur.execute("""
        SELECT 
            p.LabNo,
            p.PatientNo,
            p.Patient_Name,
            p.Age,
            p.Sex,
            p.Mobile_No,
            p.City,
            p.Address,
            p.Visit_Date,
            d.DoctorName,
            l.LabName,
            l.Address AS LabAddress,
            l.PhoneNo,
            l.Pad_Logo,
            (SELECT TOP 1 ti.ReportID FROM test_identity ti 
             JOIN test t ON ti.Id = t.Id 
             JOIN patient_test pt ON t.Test_Id = pt.Test_ID
             WHERE pt.PatientID = CAST(p.Patient_Id AS VARCHAR(50))
             ORDER BY ti.ReportID) AS ReportID
        FROM patient p
        LEFT JOIN doctor d ON p.Refered_By = d.DoctorID
        CROSS JOIN LabInfo l
        WHERE p.Patient_Id = ?
    """, (patient_id,))
    
    patient_row = cur.fetchone()
    if not patient_row:
        con.close()
        return None
    
    # Convert binary logo to base64
    logo_base64 = None
    if patient_row[13]:
        try:
            logo_base64 = base64.b64encode(patient_row[13]).decode('utf-8')
        except:
            logo_base64 = None
    
    patient_data = {
        "lab_no": patient_row[0],
        "patient_no": patient_row[1],
        "name": patient_row[2],
        "age": patient_row[3],
        "sex": patient_row[4],
        "mobile": patient_row[5],
        "city": patient_row[6],
        "address": patient_row[7],
        "visit_date": patient_row[8].strftime('%d-%b-%Y %I:%M %p') if patient_row[8] else "",
        "doctor": patient_row[9] if patient_row[9] else "N/A",
        "lab_name": patient_row[10],
        "lab_address": patient_row[11],
        "lab_phone": patient_row[12],
        "logo_base64": logo_base64,
        "report_id": patient_row[14] if patient_row[14] else 1
    }
    
    # 🔑 CRITICAL FIX: Fetch ONLY SUB-TESTS (General_Test_Id NOT NULL) grouped by MAIN TEST
    # Structure matches your Test table exactly:
    #   - Main Test = test where other tests have General_Test_Id = this test's Test_Id
    #   - Sub-test = test where General_Test_Id points to main test's Test_Id
    cur.execute("""
        SELECT 
            main_t.Test_Name AS MainTestName,
            main_t.Test_Id AS MainTestId,
            ti_sub.Test_Display_No AS SubTestDisplayNo,
            sub_t.Test_Name AS SubTestName,
            sub_t.Id AS SubTestId,
            ptr.Test_Values,
            COALESCE(
                CASE 
                    WHEN nr.Inital_Value IS NOT NULL AND nr.Final_Value IS NOT NULL 
                    THEN CONCAT(nr.Inital_Value, ' - ', nr.Final_Value)
                    ELSE COALESCE(nr.Inital_Value, nr.Final_Value, ptr.Remarks)
                END,
                ptr.Remarks
            ) AS ReferenceRange,
            sub_t.Unit
        FROM patient_test_results ptr
        -- Sub-test table (has General_Test_Id pointing to main test)
        JOIN test sub_t ON ptr.Test_No = sub_t.Test_Id
        -- Main test table (parent of sub-test)
        JOIN test main_t ON sub_t.General_Test_Id = main_t.Test_Id
        -- Get display number for SUB-TEST from test_identity
        LEFT JOIN test_identity ti_sub ON sub_t.Id = ti_sub.Id
        -- Get reference ranges for SUB-TEST
        LEFT JOIN (
            SELECT Test_Id, Inital_Value, Final_Value,
                   ROW_NUMBER() OVER (PARTITION BY Test_Id ORDER BY Ref_Id) as rn
            FROM Normal_Ranges
        ) nr ON sub_t.Test_Id = nr.Test_Id AND nr.rn = 1
        WHERE ptr.Patient_No = ?
          AND sub_t.General_Test_Id IS NOT NULL 
          AND sub_t.General_Test_Id != 0  -- ONLY SUB-TESTS (no main tests)
        ORDER BY 
            main_t.Test_Id,  -- Group by main test
            CASE 
                WHEN ti_sub.Test_Display_No IS NOT NULL THEN CAST(ti_sub.Test_Display_No AS VARCHAR(50)) 
                ELSE 'ZZZ' 
            END,
            sub_t.Test_Name
    """, (str(patient_id),))
    
    # Group sub-tests by main test
    grouped_tests = {}
    for row in cur.fetchall():
        main_test_id = row[1]
        if main_test_id not in grouped_tests:
            grouped_tests[main_test_id] = {
                "main_test_name": row[0],
                "sub_tests": []
            }
        
        # Add sub-test to group
        grouped_tests[main_test_id]["sub_tests"].append({
            "display_no": row[2] if row[2] else "None",  # Show "None" if no display number
            "test_name": row[3],
            "result": row[5] if row[5] else "",
            "reference_range": row[6] if row[6] else "N/A",
            "unit": row[7] if row[7] else "",
            "is_abnormal": is_abnormal(row[5], row[6]) if row[5] and row[6] else False
        })
    
    con.close()
    
    # Convert to ordered list for consistent display
    test_groups = []
    for main_id in sorted(grouped_tests.keys()):
        test_groups.append({
            "main_test_name": grouped_tests[main_id]["main_test_name"],
            "sub_tests": grouped_tests[main_id]["sub_tests"]
        })
    
    return {
        "patient": patient_data,
        "tests": test_groups,  # List of {main_test_name, sub_tests[]}
        "report_generated": datetime.now().strftime('%d-%b-%Y %I:%M %p')
    }

# -----------------------------
# GENERATE REPORT HTML (SUB-TESTS ONLY - EXACTLY YOUR FORMAT)
# -----------------------------
def generate_standard_report_html(report_data):
    """Report showing ONLY sub-tests grouped under main test headers"""
    patient = report_data["patient"]
    test_groups = report_data["tests"]
    report_time = report_data["report_generated"]
    
    # Generate QR code
    qr_data = f"Lab:{patient['lab_name']}|LabNo:{patient['lab_no']}|Patient:{patient['name']}|Date:{patient['visit_date']}|ReportTime:{report_time}"
    qr_base64 = generate_qr_code(qr_data) if QR_AVAILABLE else None
    
    # Build HTML report
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Test Report - Lab No: {patient['lab_no']}</title>
    <style>
        @media print {{
            body {{ margin: 0; padding: 0; }}
            .report {{ width: 210mm; min-height: 297mm; padding: 10mm; }}
            .no-print {{ display: none; }}
        }}
        * {{ box-sizing: border-box; }}
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 0;
            color: #333;
            line-height: 1.4;
        }}
        .report {{
            width: 210mm;
            min-height: 297mm;
            margin: 10mm auto;
            background: white;
            padding: 15px;
            position: relative;
            box-shadow: 0 0 10px rgba(0,0,0,0.1);
        }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            border-bottom: 2px solid #2c3e50;
            padding-bottom: 8px;
            margin-bottom: 12px;
        }}
        .logo-section {{
            display: flex;
            align-items: center;
        }}
        .logo-img {{
            max-height: 50px;
            max-width: 160px;
            object-fit: contain;
        }}
        .lab-info {{
            margin-left: 12px;
        }}
        .lab-name {{
            font-size: 20px;
            color: #2c3e50;
            font-weight: bold;
            margin: 2px 0;
        }}
        .lab-address {{
            font-size: 12px;
            color: #555;
            line-height: 1.3;
        }}
        .report-title {{
            font-size: 19px;
            color: #e74c3c;
            text-align: center;
            margin: 6px 0 4px;
            font-weight: bold;
        }}
        .report-subtitle {{
            text-align: center;
            color: #7f8c8d;
            font-size: 13px;
            margin-bottom: 12px;
            font-weight: 500;
        }}
        .patient-section {{
            display: flex;
            justify-content: space-between;
            background: #f8f9fa;
            border-radius: 6px;
            padding: 10px;
            margin-bottom: 12px;
            border: 1px solid #e9ecef;
            font-size: 12px;
        }}
        .patient-details {{
            flex: 1;
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 3px 8px;
        }}
        .patient-item {{
            margin: 1px 0;
        }}
        .patient-label {{
            font-weight: 600;
            color: #2c3e50;
            display: inline-block;
            width: 65px;
            font-size: 11px;
        }}
        .patient-value {{
            color: #2c3e50;
            font-weight: 500;
            font-size: 11px;
        }}
        .qr-container {{
            text-align: right;
            flex: 0 0 100px;
            padding-left: 8px;
            border-left: 1px dashed #ccc;
        }}
        .qr-code {{
            width: 90px;
            height: 90px;
            border: 2px solid white;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin: 0 auto;
        }}
        .qr-label {{
            font-size: 9px;
            color: #7f8c8d;
            margin-top: 4px;
            font-weight: 500;
        }}
        .tests-container {{
            width: 100%;
            margin-top: 10px;
        }}
        .tests-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 12px;
        }}
        .tests-table th {{
            background: #2c3e50;
            color: white;
            padding: 8px 10px;
            text-align: left;
            font-weight: 600;
        }}
        .tests-table td {{
            padding: 7px 10px;
            border-bottom: 1px solid #e9ecef;
        }}
        .tests-table tr:nth-child(even) {{
            background: #f9fbfd;
        }}
        .tests-table tr:hover {{
            background: #e8f4fc;
        }}
        .section-header {{
            font-weight: bold;
            font-size: 14px;
            color: #2980b9;
            padding: 6px 0;
            background: #f1f8ff;
        }}
        .result-value {{
            font-weight: 600;
            color: #27ae60;
            font-size: 13px;
        }}
        .abnormal {{
            color: #e74c3c !important;
            text-decoration: underline wavy #e74c3c;
            font-weight: 600;
        }}
        .unit {{
            color: #7f8c8d;
            font-style: italic;
            margin-left: 3px;
            font-size: 11px;
        }}
        .reference-range {{
            color: #e67e22;
            background: #fff9f0;
            padding: 1px 5px;
            border-radius: 2px;
            display: inline-block;
            font-size: 11px;
            margin-top: 1px;
        }}
        .footer {{
            text-align: center;
            margin-top: 20px;
            padding-top: 12px;
            border-top: 2px solid #2c3e50;
            color: #7f8c8d;
            font-size: 11px;
            line-height: 1.4;
        }}
        .report-id {{
            position: absolute;
            top: 8px;
            right: 12px;
            background: #e74c3c;
            color: white;
            padding: 2px 7px;
            border-radius: 10px;
            font-weight: bold;
            font-size: 11px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.2);
        }}
        .disclaimer {{
            background: #e3f2fd;
            border-left: 3px solid #2196f3;
            padding: 8px 12px;
            margin: 15px 0;
            border-radius: 0 3px 3px 0;
            font-size: 11px;
            line-height: 1.4;
        }}
        .report-meta {{
            text-align: right;
            font-size: 10px;
            color: #7f8c8d;
            margin-top: 4px;
            font-style: italic;
        }}
    </style>
</head>
<body>
    <div class="report">
        <div class="report-id">RPT-{patient['report_id']}</div>
        
        <div class="header">
            <div class="logo-section">
                {f'<img src="image/png;base64,{patient["logo_base64"]}" class="logo-img" alt="Lab Logo">' if patient.get('logo_base64') else f'<div class="lab-name">{patient["lab_name"]}</div>'}
                <div class="lab-info">
                    {f'<div class="lab-name">{patient["lab_name"]}</div>' if not patient.get('logo_base64') else ''}
                    <div class="lab-address">{patient['lab_address']}</div>
                    <div class="lab-address">📞 {patient['lab_phone']}</div>
                </div>
            </div>
            <div class="report-title">LABORATORY TEST REPORT</div>
        </div>
        
        <div class="report-subtitle">Diagnostic Test Results</div>
        
        <div class="patient-section">
            <div class="patient-details">
                <div class="patient-item"><span class="patient-label">Lab No:</span> <span class="patient-value">{patient['lab_no']}</span></div>
                <div class="patient-item"><span class="patient-label">Patient No:</span> <span class="patient-value">{patient['patient_no']}</span></div>
                <div class="patient-item"><span class="patient-label">Name:</span> <span class="patient-value">{patient['name']}</span></div>
                <div class="patient-item"><span class="patient-label">Age/Sex:</span> <span class="patient-value">{patient['age']} / {patient['sex']}</span></div>
                <div class="patient-item"><span class="patient-label">Doctor:</span> <span class="patient-value">{patient['doctor']}</span></div>
                <div class="patient-item"><span class="patient-label">City:</span> <span class="patient-value">{patient['city']}</span></div>
                <div class="patient-item"><span class="patient-label">Mobile:</span> <span class="patient-value">{patient['mobile']}</span></div>
                <div class="patient-item"><span class="patient-label">Date:</span> <span class="patient-value">{patient['visit_date']}</span></div>
            </div>
            <div class="qr-container">
                {f'<img src="image/png;base64,{qr_base64}" class="qr-code" alt="QR Code">' if qr_base64 else '<div style="height:90px"></div>'}
                <div class="qr-label">Scan to Verify</div>
            </div>
        </div>
        
        <div class="disclaimer">
            <strong>Note:</strong> Results with <span style="color:#e74c3c;text-decoration:underline wavy">wavy underline</span> are outside reference range. 
            Consult your physician for interpretation. Report valid only for specimen tested on reported date.
        </div>
        
        <div class="tests-container">
            <table class="tests-table">
                <thead>
                    <tr>
                        <th width="10%">Test No</th>
                        <th width="40%">Test Name</th>
                        <th width="25%">Result</th>
                        <th width="25%">Reference Range</th>
                    </tr>
                </thead>
                <tbody>
    """
    
    # Add test groups: ONLY SUB-TESTS under MAIN TEST headers
    if not test_groups:
        html += """
                    <tr>
                        <td colspan="4" style="text-align:center; padding:20px; color:#7f8c8d;">
                            No sub-test results available for this patient
                        </td>
                    </tr>
        """
    else:
        for group in test_groups:
            main_test_name = group["main_test_name"]
            sub_tests = group["sub_tests"]
            
            # SECTION HEADER: Main test name (parent of sub-tests)
            html += f"""
                    <tr>
                        <td colspan="4" class="section-header">
                            🔬 {main_test_name}
                        </td>
                    </tr>
            """
            
            # SUB-TESTS ONLY (NO main test row)
            for sub in sub_tests:
                # Format result with unit inline
                result_display = sub['result']
                if sub['unit']:
                    result_display += f" <span class='unit'>{sub['unit']}</span>"
                
                html += f"""
                    <tr>
                        <td>{sub['display_no']}</td>
                        <td>  ▫️ {sub['test_name']}</td>
                        <td>
                            <span class="result-value {'abnormal' if sub['is_abnormal'] else ''}">
                                {result_display}
                            </span>
                        </td>
                        <td><div class="reference-range">{sub['reference_range']}</div></td>
                    </tr>
                """
    
    html += f"""
                </tbody>
            </table>
        </div>
        
        <div class="report-meta">
            Generated: {report_time} | Page 1 of 1
        </div>
        
        <div class="footer">
            <div>Thank you for trusting {patient['lab_name']}</div>
            <div style="margin-top: 2px; font-weight: bold;">Precision in Every Test • Excellence in Every Report</div>
            <div style="margin-top: 4px; font-size: 10px;">
                Computer-generated report. No signature required. Report ID: RPT-{patient['report_id']}
            </div>
        </div>
    </div>
    
    <div class="no-print" style="text-align: center; margin: 18px 0; padding: 10px; background: #e3f2fd; border-radius: 6px; border: 1px solid #2196f3;">
        <button onclick="window.print()" style="
            background: #2196f3; 
            color: white; 
            border: none; 
            padding: 8px 22px; 
            font-size: 15px; 
            border-radius: 5px; 
            cursor: pointer;
            margin: 0 6px;
            font-weight: 600;
            box-shadow: 0 2px 3px rgba(0,0,0,0.2);
        ">🖨️ Print Report</button>
        <button onclick="downloadPDF()" style="
            background: #4caf50; 
            color: white; 
            border: none; 
            padding: 8px 22px; 
            font-size: 15px; 
            border-radius: 5px; 
            cursor: pointer;
            margin: 0 6px;
            font-weight: 600;
            box-shadow: 0 2px 3px rgba(0,0,0,0.2);
        ">💾 Save as PDF</button>
    </div>
    
    <script>
    function downloadPDF() {{
        alert('For best quality PDF:\\n1. Click OK\\n2. In print dialog, choose "Save as PDF"\\n3. Set margins to "Default"\\n4. Check "Background graphics"\\n5. Click Save');
        window.print();
    }}
    </script>
</body>
</html>
    """
    
    return html

# -----------------------------
# PUBLIC API
# -----------------------------
def generate_report(patient_id, format_type="standard"):
    """
    Generate report showing ONLY sub-tests grouped by main test
    
    Args:
        patient_id: Patient ID from database
        format_type: "standard" (only format currently supported)
    
    Returns:
        HTML string of generated report
    """
    report_data = get_patient_report_data(patient_id)
    if not report_data:
        return "<h2 style='text-align:center;color:#e74c3c;padding:40px;'>Error: Patient data not found</h2>"
    
    if format_type == "standard":
        return generate_standard_report_html(report_data)
    else:
        return generate_standard_report_html(report_data)