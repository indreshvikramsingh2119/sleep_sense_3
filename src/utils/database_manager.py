"""
Database Manager - SQLite operations for the Sleep Sense application.
Handles patient data storage and retrieval.
"""

import sqlite3
import os
from datetime import datetime

from src.utils.db_utils import get_db_path


class DatabaseManager:
    """Manage SQLite database operations for patient data."""
    
    def __init__(self, db_path=None):
        """Initialize the database manager with an optional database path."""
        if db_path is None:
            db_path = get_db_path()
        
        self.db_path = db_path
        self.init_database()
    
    def get_connection(self):
        """Get a database connection."""
        from pathlib import Path

        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable row factory for dict-like access
        return conn
    
    def init_database(self):
        """Initialize the database with required tables."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Create patients table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS patients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                last_name TEXT NOT NULL,
                first_name TEXT,
                dob TEXT NOT NULL,
                patient_id TEXT,
                gender TEXT,
                title TEXT,
                street TEXT,
                name_suffix TEXT,
                zip_code TEXT,
                phone TEXT,
                city_state TEXT,
                fax TEXT,
                country TEXT,
                clinic TEXT,
                cost_unit TEXT,
                department TEXT,
                ins_no TEXT,
                physician TEXT,
                policyholder_no TEXT,
                valid_until TEXT,
                status TEXT,
                weight TEXT,
                bmi TEXT,
                height TEXT,
                blood_pressure TEXT,
                referred_by TEXT,
                history TEXT,
                comments TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create records table for patient recordings
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER,
                last_name TEXT,
                first_name TEXT,
                recording_date TEXT,
                start_time TEXT,
                duration TEXT,
                archived BOOLEAN DEFAULT 0,
                file_path TEXT,
                FOREIGN KEY (patient_id) REFERENCES patients(id)
            )
        """)
        
        # Create reports table for medical reports
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER,
                patient_name TEXT,
                report_date TEXT,
                findings TEXT,
                diagnosis TEXT,
                recommendations TEXT,
                doctor_name TEXT,
                specialization TEXT,
                pdf_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (patient_id) REFERENCES patients(id)
            )
        """)

        self._ensure_reports_columns(cursor)
        
        conn.commit()
        conn.close()

    def _ensure_reports_columns(self, cursor):
        """Add missing columns to older reports tables while preserving data."""
        cursor.execute("PRAGMA table_info(reports)")
        columns = {row[1] for row in cursor.fetchall()}
        if "pdf_path" not in columns:
            cursor.execute("ALTER TABLE reports ADD COLUMN pdf_path TEXT")
    
    def save_patient(self, patient_data):
        """Save patient data to the database."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            last_name = str(patient_data.get('last_name', '')).strip()
            first_name = str(patient_data.get('first_name', '')).strip()
            dob = str(patient_data.get('dob', '')).strip()
            existing_patient = self.get_patient_by_name_dob(last_name, first_name, dob)
            if existing_patient:
                print(
                    f"Duplicate patient not saved: {last_name} {first_name} ({dob}) already exists with ID {existing_patient['id']}"
                )
                return None

            cursor.execute("""
                INSERT INTO patients (
                    last_name, first_name, dob, patient_id, gender, title,
                    street, name_suffix, zip_code, phone, city_state, fax, country,
                    clinic, cost_unit, department, ins_no, physician, policyholder_no,
                    valid_until, status, weight, bmi, height, blood_pressure,
                    referred_by, history, comments
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                patient_data.get('last_name', ''),
                patient_data.get('first_name', ''),
                patient_data.get('dob', ''),
                patient_data.get('patient_id', ''),
                patient_data.get('gender', ''),
                patient_data.get('title', ''),
                patient_data.get('street', ''),
                patient_data.get('name_suffix', ''),
                patient_data.get('zip_code', ''),
                patient_data.get('phone', ''),
                patient_data.get('city_state', ''),
                patient_data.get('fax', ''),
                patient_data.get('country', ''),
                patient_data.get('clinic', ''),
                patient_data.get('cost_unit', ''),
                patient_data.get('department', ''),
                patient_data.get('ins_no', ''),
                patient_data.get('physician', ''),
                patient_data.get('policyholder_no', ''),
                patient_data.get('valid_until', ''),
                patient_data.get('status', ''),
                patient_data.get('weight', ''),
                patient_data.get('bmi', ''),
                patient_data.get('height', ''),
                patient_data.get('blood_pressure', ''),
                patient_data.get('referred_by', ''),
                patient_data.get('history', ''),
                patient_data.get('comments', '')
            ))
            
            conn.commit()
            patient_id = cursor.lastrowid
            print(f"Patient saved with ID: {patient_id}")
            return patient_id
        except Exception as e:
            conn.rollback()
            print(f"Error saving patient: {e}")
            return None
        finally:
            conn.close()

    # All editable columns from the patient form (except id / created_at)
    PATIENT_FIELDS = (
        'last_name', 'first_name', 'dob', 'patient_id', 'gender', 'title',
        'street', 'name_suffix', 'zip_code', 'phone', 'city_state', 'fax',
        'country', 'clinic', 'cost_unit', 'department', 'ins_no', 'physician',
        'policyholder_no', 'valid_until', 'status', 'weight', 'bmi', 'height',
        'blood_pressure', 'referred_by', 'history', 'comments',
    )

    def update_patient(self, patient_db_id, patient_data):
        """Update an existing patient row by its database ID."""
        if not patient_db_id:
            print("update_patient called without a patient ID")
            return False

        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            last_name = str(patient_data.get('last_name', '')).strip()
            first_name = str(patient_data.get('first_name', '')).strip()
            dob = str(patient_data.get('dob', '')).strip()
            existing_patient = self.get_patient_by_name_dob(last_name, first_name, dob)
            if existing_patient and existing_patient.get('id') != patient_db_id:
                print(
                    f"Duplicate patient update blocked: {last_name} {first_name} ({dob}) already exists with ID {existing_patient['id']}"
                )
                return False

            assignments = ", ".join(f"{name} = ?" for name in self.PATIENT_FIELDS)
            values = [patient_data.get(name, '') for name in self.PATIENT_FIELDS]
            values.append(patient_db_id)

            cursor.execute(f"UPDATE patients SET {assignments} WHERE id = ?", values)
            conn.commit()

            if cursor.rowcount == 0:
                print(f"No patient found with ID {patient_db_id}")
                return False

            print(f"Patient {patient_db_id} updated successfully")
            return True
        except Exception as e:
            conn.rollback()
            print(f"Error updating patient: {e}")
            return False
        finally:
            conn.close()
    
    def get_all_patients(self):
        """Get all patients from the database."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT id, last_name, first_name, dob, patient_id
                FROM patients
                ORDER BY created_at DESC, last_name, first_name
            """)
            
            patients = []
            for row in cursor.fetchall():
                patients.append({
                    'id': row['id'],
                    'last_name': row['last_name'],
                    'first_name': row['first_name'],
                    'dob': row['dob'],
                    'patient_id': row['patient_id']
                })
            
            return patients
        except Exception as e:
            print(f"Error getting patients: {e}")
            return []
        finally:
            conn.close()
    
    def get_patient_by_id(self, patient_id):
        """Get a patient by database ID."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT * FROM patients WHERE id = ?
            """, (patient_id,))
            
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
        except Exception as e:
            print(f"Error getting patient by ID: {e}")
            return None
        finally:
            conn.close()
    
    def get_patient_by_name_dob(self, last_name, first_name, dob):
        """Get patient by name and date of birth"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT * FROM patients 
                WHERE last_name = ? AND first_name = ? AND dob = ?
            """, (last_name, first_name, dob))
            
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
        except Exception as e:
            print(f"Error getting patient by name/DOB: {e}")
            return None
        finally:
            conn.close()
    
    def save_record(self, record_data):
        """Save patient recording record"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO records (
                    patient_id, last_name, first_name, recording_date,
                    start_time, duration, archived, file_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record_data.get('patient_id'),
                record_data.get('last_name', ''),
                record_data.get('first_name', ''),
                record_data.get('recording_date', ''),
                record_data.get('start_time', ''),
                record_data.get('duration', ''),
                record_data.get('archived', False),
                record_data.get('file_path', '')
            ))
            
            conn.commit()
            record_id = cursor.lastrowid
            print(f"Record saved with ID: {record_id}")
            return record_id
        except Exception as e:
            conn.rollback()
            print(f"Error saving record: {e}")
            return None
        finally:
            conn.close()
    
    def get_records_by_patient(self, patient_db_id):
        """Get all records for a specific patient"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT * FROM records 
                WHERE patient_id = ?
                ORDER BY recording_date DESC
            """, (patient_db_id,))
            
            records = []
            for row in cursor.fetchall():
                records.append(dict(row))
            
            return records
        except Exception as e:
            print(f"Error getting records: {e}")
            return []
        finally:
            conn.close()
    
    def save_report(self, report_data):
        """Save medical report data to the database."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            self._ensure_reports_columns(cursor)
            cursor.execute("""
                INSERT INTO reports (
                    patient_id, patient_name, report_date, findings, diagnosis,
                    recommendations, doctor_name, specialization, pdf_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                report_data.get('patient_id'),
                report_data.get('patient_name'),
                report_data.get('report_date'),
                report_data.get('findings'),
                report_data.get('diagnosis'),
                report_data.get('recommendations'),
                report_data.get('doctor_name'),
                report_data.get('specialization'),
                report_data.get('pdf_path')
            ))
            
            conn.commit()
            report_id = cursor.lastrowid
            print(f"Medical report saved (id={report_id}) for patient: {report_data.get('patient_name')}")
            return report_id
        except Exception as e:
            conn.rollback()
            print(f"Error saving medical report: {e}")
            return None
        finally:
            conn.close()
    
    def get_all_reports(self):
        """Get all medical reports from the database."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            self._ensure_reports_columns(cursor)
            cursor.execute("""
                SELECT id, patient_id, patient_name, report_date, doctor_name,
                       specialization, pdf_path
                FROM reports
                ORDER BY created_at DESC, id DESC
            """)
            
            reports = []
            for row in cursor.fetchall():
                reports.append({
                    'id': row['id'],
                    'patient_id': row['patient_id'],
                    'patient_name': row['patient_name'],
                    'report_date': row['report_date'],
                    'doctor_name': row['doctor_name'],
                    'specialization': row['specialization'],
                    'pdf_path': row['pdf_path']
                })
            
            return reports
        except Exception as e:
            print(f"Error getting reports: {e}")
            return []
        finally:
            conn.close()
    
    def get_patient_reports(self, patient_id):
        """Get all reports for a specific patient."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            self._ensure_reports_columns(cursor)
            cursor.execute("""
                SELECT id, patient_id, patient_name, report_date, findings, diagnosis,
                    recommendations, doctor_name, specialization, pdf_path, created_at
                FROM reports
                WHERE patient_id = ?
                ORDER BY created_at DESC, id DESC
            """, (patient_id,))
            
            reports = []
            for row in cursor.fetchall():
                reports.append({
                    'id': row['id'],
                    'patient_id': row['patient_id'],
                    'patient_name': row['patient_name'],
                    'report_date': row['report_date'],
                    'findings': row['findings'],
                    'diagnosis': row['diagnosis'],
                    'recommendations': row['recommendations'],
                    'doctor_name': row['doctor_name'],
                    'specialization': row['specialization'],
                    'pdf_path': row['pdf_path'],
                    'created_at': row['created_at']
                })
            
            return reports
        except Exception as e:
            print(f"Error getting patient reports: {e}")
            return []
        finally:
            conn.close()
    
    def delete_patient(self, patient_id):
        """Delete a patient and their associated records"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # First delete associated records
            cursor.execute("DELETE FROM records WHERE patient_id = ?", (patient_id,))
            
            # Then delete the patient
            cursor.execute("DELETE FROM patients WHERE id = ?", (patient_id,))
            
            conn.commit()
            print(f"Patient {patient_id} and associated records deleted successfully")
            return True
        except Exception as e:
            conn.rollback()
            print(f"Error deleting patient: {e}")
            return False
        finally:
            conn.close()
