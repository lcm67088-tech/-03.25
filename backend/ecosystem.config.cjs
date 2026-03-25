module.exports = {
  apps: [
    {
      name: 'placeopt-backend',
      script: 'uvicorn',
      args: 'app.main:app --host 0.0.0.0 --port 8000 --reload',
      cwd: '/home/user/placeopt/backend',
      interpreter: 'none',
      env: {
        NODE_ENV: 'development',
        PATH: '/usr/local/bin:/usr/bin:/bin',
      },
      watch: false,
      instances: 1,
      exec_mode: 'fork'
    }
  ]
}
