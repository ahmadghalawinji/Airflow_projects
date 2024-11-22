from airflow import DAG
from airflow.providers.http.hooks.http import HttpHook
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.decorators import task
from airflow.utils.dates import days_ago

LATTITUDE = '51.5074'
LONGITUDE = '0.1278'
POSTGRES_CONN_ID = 'postgres_default'
API_CONN_ID = 'open_meteo_api'

default_args = {
    'owner': 'airflow',
    'start_date': days_ago(2),
    'retries': 3,
}

with DAG(
    dag_id='weather_etl_pipeline',
    default_args=default_args,
    schedule_interval='@daily',
    catchup=False,
) as dag:

    @task()
    def extract_weather_data():
        http_hook = HttpHook(http_conn_id=API_CONN_ID, method='GET')
        endpoint = f'https://api.open-meteo.com/v1/forecast?latitude={LATTITUDE}&longitude={LONGITUDE}&current_weather=true'
        response = http_hook.run(endpoint)

        if response.status_code == 200:
            return response.json()
        else:
            raise ValueError(f'Failed to fetch weather data. Status code: {response.status_code}')

    @task()
    def transform_weather_data(weather_data):
        # Transform weather data here
        current_weather = weather_data['current_weather']
        transformed_weather_data = {
            'latitude': LATTITUDE,
            'longitude': LONGITUDE,
            'temperature': current_weather['temperature'],
            'wind_speed': current_weather['wind_speed'],
            'wind_direction': current_weather['wind_direction'],
        }
        return transformed_weather_data

    @task()
    def load_weather_data(transformed_weather_data):
        postgres_hook = PostgresHook(postgres_conn_id=POSTGRES_CONN_ID)
        conn = postgres_hook.get_conn()
        cursor = conn.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS weather_data (
            id SERIAL PRIMARY KEY,
            latitude FLOAT,
            longitude FLOAT,
            temperature FLOAT,
            wind_speed FLOAT,
            wind_direction VARCHAR(255)
        );
        """)

        cursor.execute("""
        INSERT INTO weather_data (latitude, longitude, temperature, wind_speed, wind_direction)
        VALUES (%s, %s, %s, %s, %s);
        """, (
            transformed_weather_data['latitude'],
            transformed_weather_data['longitude'],
            transformed_weather_data['temperature'],
            transformed_weather_data['wind_speed'],
            transformed_weather_data['wind_direction'],
        ))

        conn.commit()
        cursor.close()

    # Define task dependencies
    weather_data = extract_weather_data()
    transformed_data = transform_weather_data(weather_data)
    load_weather_data(transformed_data)
