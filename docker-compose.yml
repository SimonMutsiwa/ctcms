version: '3.8'

services:
  mysql:
    image: mysql:8.0
    container_name: forensic-mysql
    environment:
      MYSQL_ROOT_PASSWORD: 2003sadoo
      MYSQL_DATABASE: forensic_test_db
      MYSQL_USER: samar
      MYSQL_PASSWORD: 2003sadoo
    ports:
      - "3306:3306"
    volumes:
      - mysql_data:/var/lib/mysql
    command: --default-authentication-plugin=mysql_native_password
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost"]
      timeout: 20s
      retries: 10

  redis:
    image: redis:7-alpine
    container_name: forensic-redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      timeout: 10s
      retries: 5

  app:
    build: .
    container_name: forensic-app
    ports:
      - "5000:5000"
    environment:
      FLASK_ENV: development
      DATABASE_URL: mysql+pymysql://forensic_user:forensic_pass@mysql:3306/forensic_db
      REDIS_URL: redis://redis:6379/0
      JWT_SECRET_KEY: your-secret-key-change-in-production
    depends_on:
      mysql:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ./:/app
    command: flask run --host=0.0.0.0 --port=5000

  celery_worker:
    build: .
    container_name: forensic-celery
    environment:
      FLASK_ENV: development
      DATABASE_URL: mysql+pymysql://forensic_user:forensic_pass@mysql:3306/forensic_db
      REDIS_URL: redis://redis:6379/0
    depends_on:
      mysql:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ./:/app
    command: celery -A forensic.celery worker --loglevel=info

volumes:
  mysql_data:
  redis_data: