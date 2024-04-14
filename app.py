import base64
from flask import Flask, render_template, request
import cx_Oracle
from dotenv import load_dotenv
import os
from io import BytesIO
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas

load_dotenv()

app = Flask(__name__, static_folder='static')

def get_db_connection():
    DB_USER = os.getenv('DB_USER')
    DB_PASSWORD = os.getenv('DB_PASSWORD')
    DB_HOST = os.getenv('DB_HOST')
    DB_SERVICE_NAME = os.getenv('DB_SERVICE_NAME')

    # Database connection parameters
    dsn_tns = cx_Oracle.makedsn(DB_HOST, '1521', service_name=DB_SERVICE_NAME)
    return cx_Oracle.connect(user=DB_USER, password=DB_PASSWORD, dsn=dsn_tns)

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/2020Population')
def population():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    rows_per_page = 100
    offset = (page - 1) * rows_per_page

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        if search:
            cur.execute("""
                SELECT * FROM (
                    SELECT city, state, population, latitude, longitude, ROWNUM as rn
                    FROM POPULATION_2020
                    WHERE UPPER(city) LIKE UPPER(:search)
                    ORDER BY city
                )
                WHERE rn > :offset AND rn <= :last_row
            """, {'search': f'%{search}%', 'offset': offset, 'last_row': offset + rows_per_page})
        else:
            cur.execute("""
                SELECT * FROM (
                    SELECT city, state, population, latitude, longitude, ROWNUM as rn
                    FROM POPULATION_2020
                    ORDER BY city
                )
                WHERE rn > :offset AND rn <= :last_row
            """, {'offset': offset, 'last_row': offset + rows_per_page})
        rows = cur.fetchall()
        return render_template('2020Population.html', rows=rows, page=page, search=search)
    finally:
        cur.close()
        conn.close()

@app.route('/haunted', methods=['GET', 'POST'])
def haunted_places():
    page = request.args.get('page', 1, type=int)
    city_name = request.args.get('city_name', '')
    action = request.args.get('action', '')
    rows_per_page = 100
    start_row = (page - 1) * rows_per_page + 1
    end_row = page * rows_per_page

    with get_db_connection() as conn, conn.cursor() as cur:
        sql = """
            SELECT * FROM (
                SELECT CITY, STATE, LOCATION, LONGITUDE, LATITUDE, ROWNUM as rnum
                FROM haunted_places
                WHERE UPPER(CITY) LIKE UPPER(:city)
                ORDER BY CITY DESC
            ) WHERE rnum >= :start_row AND rnum <= :end_row
            """
        params = {'city': f'%{city_name}%', 'start_row': start_row, 'end_row': end_row}
        if action == 'join_population':
            sql = """
                SELECT * FROM (
                    SELECT h.CITY, h.STATE, h.LOCATION, h.LONGITUDE, h.LATITUDE, p.POPULATION, ROWNUM rnum
                    FROM haunted_places h
                    JOIN POPULATION_2020 p ON UPPER(h.CITY) = UPPER(p.CITY)
                    WHERE UPPER(h.CITY) LIKE UPPER(:city)
                    ORDER BY h.CITY
                ) WHERE rnum >= :start_row AND rnum <= :end_row
                """

        cur.execute(sql, params)
        rows = cur.fetchall()
        return render_template('haunted_places.html', rows=rows, page=page)

@app.route('/ufos', methods=['GET', 'POST'])
def ufo_sightings():
    page = request.args.get('page', 1, type=int)
    city_name = request.args.get('city_name', '')
    action = request.args.get('action', '')
    rows_per_page = 100
    start_row = (page - 1) * rows_per_page + 1
    end_row = page * rows_per_page

    base_query = """
        SELECT CITY, STATE, LATITUDE, LONGITUDE, UFO_SHAPE, ENCOUNTER_DURATION, YEAR_SIGHTING, MONTH_SIGHTING, DAY_SIGHTING
        FROM UFO_Sightings
        WHERE UPPER(CITY) LIKE UPPER(:city)
    """
    
    if action == 'join_details':
        base_query = """
            SELECT u.CITY, u.STATE, u.LATITUDE, u.LONGITUDE, u.UFO_SHAPE, u.ENCOUNTER_DURATION, u.YEAR_SIGHTING, u.MONTH_SIGHTING, u.DAY_SIGHTING, d.DETAIL_DESCRIPTION
            FROM UFO_Sightings u
            LEFT JOIN UFO_Details d ON u.CITY = d.CITY AND u.YEAR_SIGHTING = d.YEAR_SIGHTING
            WHERE UPPER(u.CITY) LIKE UPPER(:city)
        """

    # Apply ordering and pagination using a wrapper query around the base query
    final_query = f"""
        SELECT * FROM (
            SELECT a.*, ROWNUM rnum FROM ({base_query}) a ORDER BY CITY, YEAR_SIGHTING DESC, MONTH_SIGHTING DESC, DAY_SIGHTING DESC
        ) WHERE rnum >= :start_row AND rnum <= :end_row
    """

    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(final_query, {'city': f'%{city_name}%', 'start_row': start_row, 'end_row': end_row})
        rows = cur.fetchall()
        
    return render_template('ufo_sightings.html', rows=rows, page=page)

    
@app.route('/graphs', methods=['GET', 'POST'])
def graphs():
    if request.method == 'POST':
        city_name = request.form.get('city_name', '')
        print(city_name)

        with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM haunted_places WHERE UPPER(CITY) LIKE UPPER(:city)", {'city': f"%{city_name}%"})

                haunted_count = cursor.fetchone()
                print(f"Haunted Count: {haunted_count}")

                cursor.execute("SELECT COUNT(*) FROM ufo_sightings WHERE UPPER(CITY) LIKE UPPER(:city)", {'city': f"%{city_name}%"})
                ufo_count = cursor.fetchone()
                print(f"UFO Count: {ufo_count}")

                total_incidents = int(haunted_count[0]) + int(ufo_count[0])
                print(f"Total Incidents: {total_incidents}")

        if total_incidents == 0:
            return render_template('graphs.html', message="No incidents found.")

        fig = Figure()
        ax = fig.subplots()
        ax.bar(['Total Incidents'], [total_incidents])
        ax.bar(['Total Haunted'], [int(haunted_count[0])])
        ax.bar(['Total UFO Sightings'], [int(ufo_count[0])])


        ax.set_title(f'Total Incidents in {city_name}')
        ax.set_xlabel('City')
        ax.set_ylabel('Incident Count')

        buf = BytesIO()
        fig.savefig(buf, format='png')
        buf.seek(0)

        base64_image = base64.b64encode(buf.getvalue()).decode('utf-8')
        image_data = f"data:image/png;base64,{base64_image}"

        return render_template('graphs.html', image_data=image_data)

    return render_template('graphs.html')


if __name__ == '__main__':
    app.run(debug=True)
