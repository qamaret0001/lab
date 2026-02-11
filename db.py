import pyodbc

def get_connection():
    conn = pyodbc.connect(
        "DRIVER={ODBC Driver 17 for SQL Server};"
        "SERVER=dbserver\sqlexpress;"          # change if needed
        "DATABASE=Lab;"        # <-- your database name
        "UID=sa;"                    # or SQL user
        "PWD=aielitetechsims2000;"          # <-- change
    )
    return conn

