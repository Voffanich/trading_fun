import sqlite3
import csv

def export_to_csv(db_file, table_name, csv_file):
    # Connect to the SQLite database
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    # Execute a query to select all data from the specified table
    cursor.execute(f"SELECT * FROM {table_name}")

    # Fetch all rows from the executed query
    rows = cursor.fetchall()

    # Get column names from the table for headers in CSV
    column_names = [description[0] for description in cursor.description]

    # Open a CSV file and write data into it
    with open(csv_file, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)

        # Write the column headers first
        writer.writerow(column_names)

        # Write all rows of data
        writer.writerows(rows)

    # Close the database connection
    conn.close()

# Example usage:
db_filename = 'deals_5m.sqlite'
table_name = 'deals'
csv_filename = 'deals_5m.csv'

export_to_csv(db_filename, table_name, csv_filename)