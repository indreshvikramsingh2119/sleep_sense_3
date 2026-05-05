"""
Database Manager - SQLite Operations for Sleep Sense Application
Handles patient data storage and retrieval
"""

import sqlite3
import os
from datetime import datetime


class DatabaseManager:
    """Manages SQLite database operations for patient data"""
    
    def __init__(self, db_path=None):
        """Initialize database manager with database path"""
        if db_path is None:
            # Default database path in data directory
            script_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            db_path = os.path.join(script_dir, "data", "sleep_sense.db")
        
        self.db_path = db_path
        self.init_database()
    
    def get_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable row factory for dict-like access
        return conn
    
    def init_database(self):
        """Initialize database with required tables"""
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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (patient_id) REFERENCES patients(id)
            )
        """)
        
        conn.commit()
        conn.close()
    
    def save_patient(self, patient_data):
        """Save patient data to database"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
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
    
    def get_all_patients(self):
        """Get all patients from database"""
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
        """Get patient by database ID"""
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
        """Save medical report data to database"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO reports (
                    patient_id, patient_name, report_date, findings, diagnosis,
                    recommendations, doctor_name, specialization
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                report_data.get('patient_id'),
                report_data.get('patient_name'),
                report_data.get('report_date'),
                report_data.get('findings'),
                report_data.get('diagnosis'),
                report_data.get('recommendations'),
                report_data.get('doctor_name'),
                report_data.get('specialization')
            ))
            
            conn.commit()
            print(f"Medical report saved successfully for patient: {report_data.get('patient_name')}")
            return True
        except Exception as e:
            conn.rollback()
            print(f"Error saving medical report: {e}")
            return False
        finally:
            conn.close()
    
    def get_all_reports(self):
        """Get all medical reports from database"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT id, patient_id, patient_name, report_date, doctor_name, specialization
                FROM reports
                ORDER BY created_at DESC
            """)
            
            reports = []
            for row in cursor.fetchall():
                reports.append({
                    'id': row['id'],
                    'patient_id': row['patient_id'],
                    'patient_name': row['patient_name'],
                    'report_date': row['report_date'],
                    'doctor_name': row['doctor_name'],
                    'specialization': row['specialization']
                })
            
            return reports
        except Exception as e:
            print(f"Error getting reports: {e}")
            return []
        finally:
            conn.close()
    
    def get_patient_reports(self, patient_id):
        """Get all reports for a specific patient"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT id, patient_id, patient_name, report_date, findings, diagnosis,
                    recommendations, doctor_name, specialization, created_at
                FROM reports
                WHERE patient_id = ?
                ORDER BY created_at DESC
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
