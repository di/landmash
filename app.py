import os
from flask import Flask
import landmash

if __name__ == '__main__' :
    app = landmash.app
    port = int(os.environ.get('PORT', 5000))
    app.run(host="0.0.0.0", port=port, debug=True, use_debugger=True, use_reloader=True)
