module.exports = {
  apps: [
    {
      name: 'smartpark-api',
      cwd: '/var/www/smart-parking/backend',
      script: '/var/www/smart-parking/backend/venv/bin/uvicorn',
      args: 'main:app --host 127.0.0.1 --port 8000 --workers 2 --loop uvloop',
      interpreter: 'none',
      autorestart: true,
      restart_delay: 3000,
      max_memory_restart: '512M',
      error_file: '/var/log/smartpark/api-error.log',
      out_file: '/var/log/smartpark/api-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      env: {
        PYTHONPATH: '/var/www/smart-parking/backend',
        PYTHONUNBUFFERED: '1',
      },
    },
  ],
}
