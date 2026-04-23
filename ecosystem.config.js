module.exports = {
  apps: [
    // Backend API
    {
      name: 'smartpark-api',
      cwd: '/home/revanth/projects/smart_parking_lot/backend',
      script: '/home/revanth/projects/smart_parking_lot/backend/venv/bin/uvicorn',
      args: 'main:app --host 0.0.0.0 --port 6626 --workers 1 --loop uvloop',
      interpreter: 'none',
      autorestart: true,
      restart_delay: 3000,
      max_memory_restart: '512M',
      error_file: '/tmp/smartpark-api-error.log',
      out_file: '/tmp/smartpark-api-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      env: {
        PYTHONPATH: '/home/revanth/projects/smart_parking_lot/backend',
        PYTHONUNBUFFERED: '1',
      },
    },
    // Frontend User App
    {
      name: 'smartpark-frontend',
      cwd: '/home/revanth/projects/smart_parking_lot/frontend',
      script: 'npm',
      args: 'start',
      autorestart: true,
      restart_delay: 3000,
      max_memory_restart: '256M',
      error_file: '/tmp/smartpark-frontend-error.log',
      out_file: '/tmp/smartpark-frontend-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      env: {
        NODE_ENV: 'production',
      },
    },
    // Admin App
    {
      name: 'smartpark-admin',
      cwd: '/home/revanth/projects/smart_parking_lot/admin-app',
      script: 'npm',
      args: 'start',
      autorestart: true,
      restart_delay: 3000,
      max_memory_restart: '256M',
      error_file: '/tmp/smartpark-admin-error.log',
      out_file: '/tmp/smartpark-admin-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      env: {
        NODE_ENV: 'production',
      },
    },
  ],
};