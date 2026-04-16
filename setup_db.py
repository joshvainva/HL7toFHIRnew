import psycopg2
import os
from urllib.parse import quote_plus
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

if __name__ == '__main__':
    print('------------------------------------------------------')
    print('  PostgreSQL Auto-Setup for Innova FHIR')
    print('------------------------------------------------------')
    pw = input('Please enter your PostgreSQL password (for user postgres): ').strip()
    try:
        # Create database
        conn = psycopg2.connect(user='postgres', password=pw, host='localhost', port='5432', database='postgres')
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        # Check if database exists
        cursor.execute("SELECT 1 FROM pg_database WHERE datname='innova_fhir'")
        if not cursor.fetchone():
            cursor.execute('CREATE DATABASE innova_fhir;')
            print('\n[SUCCESS] Database innova_fhir created!')
        else:
            print('\n[SUCCESS] Database innova_fhir already exists!')
            
        cursor.close()
        conn.close()
        
        # Update .env
        env_file = '.env'
        lines = []
        if os.path.exists(env_file):
            with open(env_file, 'r') as f:
                lines = f.readlines()
                
        # Remove old DATABASE_URL lines if they exist
        new_lines = [l for l in lines if not l.startswith('DATABASE_URL=')]
        
        encoded_pw = quote_plus(pw)
        db_url = f'DATABASE_URL=postgresql://postgres:{encoded_pw}@localhost:5432/innova_fhir\n'
        new_lines.append('\n' + db_url)
        
        with open(env_file, 'w') as f:
            f.writelines(new_lines)
            
        print('[SUCCESS] Successfully updated .env with your credentials!')
        print('          You can now restart your application.')
        
    except Exception as e:
        print(f'\n[ERROR] Could not connect or create database. Issue: {e}')
        print('Did you type the correct postgres password? Please try again.')
